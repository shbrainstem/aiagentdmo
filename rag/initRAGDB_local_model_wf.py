import uuid
import logging
import psycopg2
from datetime import datetime
from langchain_core.documents import Document
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
from pathlib import Path
from fastapi import UploadFile
import shutil
from rag.model_manager import model_manager,config
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 使用嵌入模型
embeddings = model_manager.embeddings
rerank_model = model_manager.rerank_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = config['database']
MODEL_CONFIG = config['model']
APP_CONFIG = config['app']
CONNECTION_STRING = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['name']}"

upload_dir = Path(APP_CONFIG.get('upload_dir', 'uploads'))
upload_dir.mkdir(exist_ok=True, parents=True)

# 使用Pydantic定义状态
class ProcessingState(BaseModel):
    text: Optional[str] = None
    chunks: List[Document] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)
    results: Dict = Field(default_factory=dict)
    user: str = "anonymous"  # 默认匿名用户
    knowledge_base_name: str = "default"  # 默认知识库名称

# LangGraph工作流定义
def extract_metadata(state: ProcessingState) -> dict:
    """从文本中提取元数据"""
    logger.info("提取元数据...")
    text_len = len(state.text) if state.text else 0
    collection_id = str(uuid.uuid4())
    try:
        # 使用正确的连接参数 [1,7](@ref)
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                          INSERT INTO langchain_pg_collection (uuid, name, user_id, cmetadata)
                          VALUES (%s, %s, %s, %s)
                          ON CONFLICT (name, user_id) DO UPDATE SET name = EXCLUDED.name
                          RETURNING uuid
                      """, (collection_id, state.knowledge_base_name, state.user, json.dumps(state.metadata)))
                collection_id = cursor.fetchone()[0]
                conn.commit()
    except Exception as e:
        logger.exception("数据库操作失败")  # 记录完整堆栈信息
        raise

    new_metadata = {
        **state.metadata,
        "created_at": datetime.now().isoformat(),
        "document_id": collection_id,
        "text_length": text_len,
        "user": state.user,  # 添加用户信息
        "knowledge_base": state.knowledge_base_name  # 添加知识库名称
    }

    if "source" not in new_metadata:
        new_metadata["source"] = "user_input"

    return {"metadata": new_metadata}

def split_text(state: ProcessingState) -> dict:
    """分割文本为块"""
    logger.info("分割文本...")
    if not state.text:
        return {"chunks": []}

    # 获取自定义分割符或使用默认值
    custom_separators = state.metadata.get("separators", "").split(',') if state.metadata.get("separators") else None
    separators = custom_separators or ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " "]

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=state.metadata.get("chunk_size", 1000),
        chunk_overlap=state.metadata.get("chunk_overlap", 200),
        separators=separators  # 使用自定义分割符
    )

    chunks = text_splitter.split_text(state.text)
    chunks_list = [Document(
        page_content=chunk,
        metadata={
            "custom_id": state.metadata.get("user", "null"),
            **{k: v for k, v in state.metadata.items() if k != "separators"},
             # 显式设置自定义ID
        }

    ) for chunk in chunks]
    return {"chunks": chunks_list}

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 创建引擎
engine = create_engine(CONNECTION_STRING)
# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def generate_embeddings(state: ProcessingState) -> dict:
    """生成嵌入向量"""
    logger.info("生成嵌入向量...")
    try:
        # 创建向量存储
        insert_chunks(state)

        return {
            "results": {
                "status": "success",
                "num_chunks": len(state.chunks),
                "document_id": state.metadata.get("document_id", "")
            }
        }
    except Exception as e:
        logger.error(f"生成嵌入时出错: {str(e)}")
        return {
            "results": {
                "status": "error",
                "message": str(e)
            }
        }

# 构建工作流
workflow = StateGraph(ProcessingState)

workflow.add_node("extract_metadata", extract_metadata)
workflow.add_node("split_text", split_text)
workflow.add_node("generate_embeddings", generate_embeddings)

workflow.set_entry_point("extract_metadata")
workflow.add_edge("extract_metadata", "split_text")
workflow.add_edge("split_text", "generate_embeddings")
workflow.add_edge("generate_embeddings", END)

knowledge_workflow = workflow.compile()


def save_upload_file(upload_file: UploadFile) -> str:
    """保存上传的文件并返回文件路径"""
    try:
        file_path = upload_dir / upload_file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return str(file_path)
    finally:
        upload_file.file.close()


def read_file(file_path: str) -> str:
    """读取文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # 尝试其他编码
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


def process_content(
        content: str,
        source: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: str = "",  # 新增
        user: str = "anonymous",  # 新增
        knowledge_base_name: str = "default"  # 新增
) -> dict:
    state = ProcessingState(
        text=content,
        user=user,  # 传递用户信息
        knowledge_base_name=knowledge_base_name,  # 传递知识库名称
        metadata={
            "source": source,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "separators": separators  # 传递分割字符串
        }
    )

    result = knowledge_workflow.invoke(state)
    return result["results"]

PSYCOPG2_CONN_PARAMS = {
    'dbname': DB_CONFIG['name'],
    'user': DB_CONFIG['user'],
    'password': DB_CONFIG['password'],
    'host': DB_CONFIG['host'],
    'port': DB_CONFIG['port']
}

# 数据库连接辅助函数 [7,10](@ref)
def get_db_connection():
    return psycopg2.connect(**PSYCOPG2_CONN_PARAMS)

def insert_chunks(state: ProcessingState):
    """
    优化后的函数，批量插入文档块到数据库，并生成嵌入向量

    参数:
    chunks: Document对象列表
    embedding_model: 嵌入模型实例，用于生成文本向量
    """
    chunks = state.chunks
    try:
        # 1. 批量生成所有文档块的嵌入向量
        texts = [chunk.page_content for chunk in chunks]
        embeddingss = embeddings.embed_documents(texts)

        # 2. 准备批量插入数据
        data_to_insert = []
        for i, chunk in enumerate(chunks):
            # 处理元数据中的特殊值（如datetime对象）
            processed_metadata = {}
            for key, value in chunk.metadata.items():
                if hasattr(value, 'isoformat'):  # 处理datetime对象
                    processed_metadata[key] = value.isoformat()
                else:
                    processed_metadata[key] = value

            # 构建插入数据元组
            data_tuple = (
                state.metadata.get("document_id"),
                embeddingss[i],  # 嵌入向量
                chunk.page_content,  # 文档文本
                json.dumps(processed_metadata),  # 使用Psycopg2的Json适配器
                chunk.metadata.get("custom_id", str(uuid.uuid4())),
                str(uuid.uuid4())  # 新的UUID
            )
            data_to_insert.append(data_tuple)

        # 3. 批量插入数据
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 使用executemany进行批量插入
                cursor.executemany("""
                    INSERT INTO langchain_pg_embedding (
                        collection_id, embedding, document, 
                        cmetadata, custom_id, uuid
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, data_to_insert)
                conn.commit()

        logger.info(f"成功插入 {len(chunks)} 个文档块")
        return len(chunks)

    except Exception as e:
        logger.exception("数据库操作失败")
        raise