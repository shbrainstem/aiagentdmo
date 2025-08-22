import logging
from langchain_community.vectorstores.pgvector import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from psycopg2.pool import SimpleConnectionPool
from functools import wraps
import os
from rag.queryRagInfo import DB_CONFIG,config
from rag.model_manager import model_manager,config

# 使用嵌入模型
embeddings = model_manager.embeddings
rerank_model = model_manager.rerank_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_CONFIG = config['model']
APP_CONFIG = config['app']

#向量数据库配置
CONNECTION_STRING = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['name']}"

db_pool = SimpleConnectionPool(
    DB_CONFIG['min_connections'],
    DB_CONFIG['max_connections'],
    host=DB_CONFIG['host'],
    port=DB_CONFIG['port'],
    dbname=DB_CONFIG['name'],
    user=DB_CONFIG['user'],
    password=DB_CONFIG['password']
)

# 初始化数据库
def init_database():
    """初始化数据库和向量存储"""
    try:
        # 创建集合
        PGVector.from_documents(
            documents=[Document(page_content="init")],
            embedding=embeddings,
            collection_name=DB_CONFIG['collection_name'],
            connection_string=CONNECTION_STRING,
            pre_delete_collection=False
        )
        create_tables()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise

# 创建数据库表
def create_tables():
    """创建必要的数据库表"""
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()

        # 创建知识记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_records (
            id SERIAL PRIMARY KEY,
            document_id UUID NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            CONSTRAINT unique_document_id UNIQUE (document_id)
        );
        """)

        # 创建元数据表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_metadata (
            id SERIAL PRIMARY KEY,
            document_id UUID NOT NULL,
            chunk_id UUID NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_chunk UNIQUE (document_id, chunk_id),
            CONSTRAINT fk_document
                FOREIGN KEY(document_id)
                REFERENCES knowledge_records(document_id)
                ON DELETE CASCADE
        );
        """)

        # 创建索引
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_records_created_at 
        ON knowledge_records(created_at DESC);
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_metadata_document_id 
        ON document_metadata(document_id);
        """)

        conn.commit()
        logger.info("数据库表创建成功")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"创建数据库表失败: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

# 设置模型环境
os.environ['TRANSFORMERS_CACHE'] = MODEL_CONFIG['cache_path']
os.environ['HF_HUB_OFFLINE'] = '1'  # 启用离线模式（强制使用本地缓存）


# 数据库连接上下文管理器
def get_db_connection():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

# 初始化文本分割器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    is_separator_regex=False,
)
