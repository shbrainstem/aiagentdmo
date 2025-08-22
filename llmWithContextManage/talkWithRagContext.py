from typing import AsyncGenerator, List, Dict, Optional
from langchain_deepseek import ChatDeepSeek
import os
import asyncio
import logging
from langchain_core.messages import HumanMessage, AIMessage
from sessionManage.sessionObj import SessionData
from sessionManage.redisSession import RedisBackend
from rag.queryRagInfo import query_knowledge_base, QueryRequest  # 替换为实际模块路径
from uuid import UUID, uuid4
from llms.DeepSeekLLM import getDeepSeek
# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 使用环境变量管理API密钥

llm = getDeepSeek()

def build_knowledge_prompt(knowledge_results: List[Dict]) -> str:
    """构建知识库上下文提示语"""
    if not knowledge_results:
        return ""

    context = "## 知识库参考信息：\n"
    for i, result in enumerate(knowledge_results[:3]):  # 最多使用3条
        content = result.get("content", "")
        metadata = result.get("metadata", {})
        source = metadata.get("source", "未知来源")

        context += (
            f"### 参考片段 {i + 1} (来源: {source})\n"
            f"{content}\n\n"
        )

    return context + "\n请根据以上参考信息回答用户问题：\n"


async def stream_generator_rag_ctx(
        question: str,
        session_id: UUID,
        session_data: SessionData,
        backend: RedisBackend,
        knowledge_base_name: Optional[str] = "default2"
) -> AsyncGenerator[str, None]:
    """增强版流式响应生成器（集成知识库查询）"""
    # 1. 知识库查询
    knowledge_context = ""
    if knowledge_base_name:
        try:
            request = QueryRequest(
                knowledge_base_name=knowledge_base_name,
                query_text=question,
                top_k=5,
                rerank_top_k=3
            )
            response = await query_knowledge_base(request)
            if response and "results" in response:
                knowledge_context = build_knowledge_prompt(response["results"])
                logger.info(f"知识库查询成功，找到{len(response['results'])}条相关结果")
        except Exception as e:
            logger.error(f"知识库查询失败: {str(e)}")

    # 2. 准备对话历史
    history = session_data.conversation_history
    messages = [
        {"role": "system", "content": f"你是一个AI助理。请结合以下内容：{knowledge_context},回答问题"},
        *history
    ]

    # 3. 添加知识库上下文（如果存在）
    # if knowledge_context:
    #     messages.append({"role": "system", "content": knowledge_context})

    messages.append({"role": "user", "content": question})

    # 4. 更新会话历史（先添加用户问题）
    session_data.conversation_history.append({"role": "user", "content": question})

    # 5. 流式生成响应
    collected_chunks = []
    try:
        async for chunk in llm.astream(messages):
            if isinstance(chunk, AIMessage) and chunk.content:
                await asyncio.sleep(0.02)  # 控制输出速度
                collected_chunks.append(chunk.content)
                yield f"data: {chunk.content}\n\n"

        # 6. 更新会话历史（添加AI回复）
        ai_reply = ''.join(collected_chunks)
        session_data.conversation_history.append({"role": "ai", "content": ai_reply})
        await backend.update(session_id, session_data)
        yield "event: end\ndata: {\"end\": true}\n\n"

    except Exception as e:
        logger.exception("流式生成异常")
        yield f"event: error\ndata: {str(e)}\n\n"

async def stream_with_context(
        question: str,
        history: List[Dict[str, str]],
        session_id: str,
        knowledge_base_name: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    增强版带上下文的流式生成器（集成知识库查询）

    参数:
        question: 用户问题
        history: 对话历史记录
        session_id: 会话ID
        knowledge_base_name: 知识库名称（可选）
    """
    # 1. 知识库查询
    knowledge_context = ""
    if knowledge_base_name:
        try:
            request = QueryRequest(
                knowledge_base_name=knowledge_base_name,
                query_text=question,
                top_k=5,
                rerank_top_k=3
            )
            response = await query_knowledge_base(request)
            if response and "results" in response:
                knowledge_context = build_knowledge_prompt(response["results"])
                logger.info(f"会话 {session_id[:8]} - 知识库查询成功")
        except Exception as e:
            logger.error(f"会话 {session_id[:8]} - 知识库查询失败: {str(e)}")

    # 2. 准备消息
    messages = [
        {"role": "system", "content": "你是一个AI助理。"},
        *history
    ]

    # 3. 添加知识库上下文（如果存在）
    if knowledge_context:
        messages.append({"role": "system", "content": knowledge_context})

    messages.append({"role": "user", "content": question})

    logger.debug(f"会话 {session_id[:8]} - 完整消息: {messages}")

    # 4. 流式处理
    collected_chunks = []
    try:
        async for chunk in llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content is not None:
                content_chunk = chunk.content
                collected_chunks.append(content_chunk)
                yield content_chunk
    except Exception as e:
        logger.error(f"会话 {session_id[:8]} - 流式处理错误: {str(e)}")
        yield "⚠️ 服务暂时不可用，请稍后再试"
        return

    # 5. 生成完整回复并添加历史标记
    ai_reply = ''.join(collected_chunks)
    if ai_reply:
        yield f"\n|||HISTORY_UPDATE|||\nuser:{question}\nassistant:{ai_reply}\n|||END|||"
    else:
        logger.warning(f"会话 {session_id[:8]} - 收到空回复")
        yield "\n|||HISTORY_UPDATE|||\n|||END|||"


# 使用示例
if __name__ == "__main__":
    async def test_enhanced_stream():
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮您的？"}
        ]

        print("--- 带知识库查询的测试 ---")
        async for chunk in stream_with_context(
                "公司请假政策是什么？",
                history,
                "test-session",
                knowledge_base_name="员工手册"
        ):
            print(chunk, end="", flush=True)

        print("\n\n--- 普通查询测试 ---")
        async for chunk in stream_with_context(
                "我之前问了什么问题？",
                history,
                "test-session"
        ):
            print(chunk, end="", flush=True)


    asyncio.run(test_enhanced_stream())