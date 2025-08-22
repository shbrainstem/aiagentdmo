import logging
import psycopg2
from pydantic import BaseModel
from fastapi import   HTTPException
from rag.model_manager import model_manager,config

# 使用嵌入模型
embeddings = model_manager.embeddings
rerank_model = model_manager.rerank_model

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 新增Pydantic模型
class QueryRequest(BaseModel):
    knowledge_base_name: str = "default2"
    query_text: str
    top_k: int = 5
    rerank_top_k: int = 3


DB_CONFIG = config['database']
MODEL_CONFIG = config['model']
APP_CONFIG = config['app']

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

async def query_knowledge_base(request: QueryRequest):
    """执行知识库查询"""
    try:
        # 1. 获取知识库ID
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT uuid FROM langchain_pg_collection WHERE name = %s",
                    (request.knowledge_base_name,)
                )
                collection_id = cursor.fetchone()
                if not collection_id:
                    raise HTTPException(status_code=404, detail="知识库不存在")
                collection_id = collection_id[0]

        # 2. 向量检索
        query_vector = embeddings.embed_query(request.query_text)

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT document, cmetadata, embedding <-> %s::vector AS similarity
                    FROM langchain_pg_embedding
                    WHERE collection_id = %s
                    ORDER BY embedding <-> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, collection_id, query_vector, request.top_k)
                )
                results = cursor.fetchall()

        # 3. 结果重排
        if results and len(results) > 1:
            pairs = [(request.query_text, row[0]) for row in results]
            rerank_scores = rerank_model.predict(pairs)

            # 组合分数并排序
            combined_results = []
            for i, row in enumerate(results):
                rerank_score_float = float(rerank_scores[i])  # 转换为Python float
                similarity_float = float(row[2])  # 确保为Python float
                combined_score = (rerank_score_float + (1 - similarity_float)) / 2
                combined_results.append({
                    "content": row[0],
                    "metadata": row[1],  # 直接使用字典
                    "similarity": similarity_float,
                    "rerank_score": rerank_score_float,  # 使用转换后的值
                    "combined_score": combined_score
                })
            # 按组合分数排序
            combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
            results = combined_results[:request.rerank_top_k]
        return {"results": results}
    except Exception as e:
        import traceback  # 新增导入traceback模块
        traceback.print_exc()  # 将异常堆栈打印到标准错误输出
        logger.exception("查询知识库错误")
        raise HTTPException(status_code=500, detail=f"查询知识库错误: {str(e)}")

async def get_knowledge_bases():
    """获取所有知识库名称列表"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT name FROM langchain_pg_collection")
                knowledge_bases = [row[0] for row in cursor.fetchall()]
        return {"knowledge_bases": knowledge_bases}
    except Exception as e:
        logger.exception("获取知识库列表错误")
        raise HTTPException(status_code=500, detail=f"获取知识库列表错误: {str(e)}")

async def query_knowledge(request: QueryRequest):
    try:
        # 1. 获取知识库ID
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT uuid FROM langchain_pg_collection WHERE name = %s",
                    (request.knowledge_base_name,)
                )
                collection_id = cursor.fetchone()
                if not collection_id:
                    raise HTTPException(status_code=404, detail="知识库不存在")
                collection_id = collection_id[0]

        # 2. 向量检索
        query_vector = embeddings.embed_query(request.query_text)

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT document, cmetadata, embedding <-> %s::vector AS similarity
                    FROM langchain_pg_embedding
                    WHERE collection_id = %s
                    ORDER BY embedding <-> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, collection_id, query_vector, request.top_k)
                )
                results = cursor.fetchall()

        # 3. 结果重排
        if results and len(results) > 1:
            pairs = [(request.query_text, row[0]) for row in results]
            rerank_scores = rerank_model.predict(pairs)

            # 组合分数并排序
            combined_results = []
            for i, row in enumerate(results):
                rerank_score_float = float(rerank_scores[i])  # 转换为Python float
                similarity_float = float(row[2])  # 确保为Python float
                combined_score = (rerank_score_float + (1 - similarity_float)) / 2
                combined_results.append({
                    "content": row[0],
                    "metadata": row[1],  # 直接使用字典
                    "similarity": similarity_float,
                    "rerank_score": rerank_score_float,  # 使用转换后的值
                    "combined_score": combined_score
                })
            # 按组合分数排序
            combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
            results = combined_results[:request.rerank_top_k]

        return {"results": results}

    except Exception as e:
        import traceback  # 新增导入traceback模块
        traceback.print_exc()  # 将异常堆栈打印到标准错误输出
        logger.exception("查询知识库错误")
        raise HTTPException(status_code=500, detail=f"查询知识库错误: {str(e)}")