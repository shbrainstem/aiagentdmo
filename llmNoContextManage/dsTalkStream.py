import os
import asyncio
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, AIMessage
from llms.DeepSeekLLM import getDeepSeek
# 初始化模型
llm = getDeepSeek()

async def stream_generator(question: str):
    """流式响应生成器"""
    try:
        async for chunk in llm.astream([HumanMessage(content=question)]):
            if isinstance(chunk, AIMessage) and chunk.content:
                # 逐个字符发送
                # for char in chunk.content:
                await asyncio.sleep(0.02)  # 控制输出速度
                # yield f"data: {char}\n\n"
                # 逐个token发送
                yield f"data: {chunk.content}\n\n"
        yield "event: end\ndata: {\"end\": true}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {str(e)}\n\n"