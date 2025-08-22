from typing import AsyncGenerator, List, Dict
from langchain_deepseek import ChatDeepSeek
import os
import asyncio
import logging
from langchain_core.messages import HumanMessage, AIMessage
from sessionManage.sessionObj import SessionData
from sessionManage.redisSession import RedisBackend
from llms.DeepSeekLLM import getDeepSeek

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 使用环境变量管理API密钥
# 初始化模型
llm = getDeepSeek()

async def stream_generator_ctx(question: str,session_id,session_data: SessionData,backend: RedisBackend):
    """流式响应生成器"""
    history = session_data.conversation_history
    messages = [
        {"role": "system", "content": "你是一个AI助理。"},
        *history,
        {"role": "user", "content": question}
    ]
    session_data.conversation_history.append({"role": "user", "content": question})
    collected_chunks = []
    try:
        async for chunk in llm.astream(messages):
            if isinstance(chunk, AIMessage) and chunk.content:
                await asyncio.sleep(0.02)  # 控制输出速度
                collected_chunks.append(chunk.content)
                yield f"data: {chunk.content}\n\n"
        session_data.conversation_history.append({"role": "ai", "content": ''.join(map(str, collected_chunks))})
        await backend.update(session_id, session_data)
        yield "event: end\ndata: {\"end\": true}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {str(e)}\n\n"


async def stream_with_context(
        question: str,
        history: List[Dict[str, str]],
        session_id: str
) -> AsyncGenerator[str, None]:
    """
    带上下文的流式生成器（优化版）

    参数:
        question: 用户问题
        history: 对话历史记录
        session_id: 会话ID（用于日志记录）

    返回:
        异步生成器，产生文本块
    """
    # 1. 准备消息
    messages = [
        {"role": "system", "content": "你是一个AI助理。"},
        *history,
        {"role": "user", "content": question}
    ]

    logger.debug(f"会话 {session_id[:8]} - 消息: {messages}")

    # 3. 流式处理
    collected_chunks = []
    try:
        async for chunk in llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content is not None:
                content_chunk = chunk.content
                # 注意：由于流式传输，每次content_chunk可能只是一个字符或一个词
                collected_chunks.append(content_chunk)
                yield content_chunk
    except Exception as e:
        logger.error(f"会话 {session_id[:8]} - 流式处理错误: {str(e)}")
        yield "⚠️ 服务暂时不可用，请稍后再试"
        return

    # 4. 生成完整回复并添加历史标记
    ai_reply = ''.join(collected_chunks)
    if ai_reply:
        # 使用更可靠的分隔符
        yield f"\n|||HISTORY_UPDATE|||\nuser:{question}\nassistant:{ai_reply}\n|||END|||"
    else:
        logger.warning(f"会话 {session_id[:8]} - 收到空回复")
        yield "\n|||HISTORY_UPDATE|||\n|||END|||"  # 空更新标记


# 使用示例
if __name__ == "__main__":
    async def test_stream():
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮您的？"}
        ]
        async for chunk in stream_with_context("今天天气如何？", history, "test-session"):
            print(chunk, end="", flush=True)

        async for chunk in stream_with_context("我之前问了什么问题？", history, "test-session"):
            print(chunk, end="", flush=True)

    asyncio.run(test_stream())