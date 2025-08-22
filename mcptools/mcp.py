from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
import asyncio
import os
from langchain_deepseek import ChatDeepSeek
from fastapi import UploadFile
from pathlib import Path
import shutil
from uuid import UUID
from pydantic import BaseModel
from llms.DeepSeekLLM import getDeepSeek

class PandasQueryRequest(BaseModel):
    query_text: str

# 初始化模型
llm = getDeepSeek()

upload_dir = Path('./mcptools/tmp')
upload_dir.mkdir(exist_ok=True, parents=True)

# Initialize the model
async def call_tools(inputstr :str , filepath :str):  # 创建异步主函数
    # Set up MCP client
    client = MultiServerMCPClient(
        {
            "math": {
                "command": "python",
                # Make sure to update to the full absolute path to your math_server.py file
                "args": ["./mcptools/tools/math_server.py"],
                "transport": "stdio",
            },
            "pandas": {
                "command": "python",
                "args": ["./mcptools/tools/pandasMcp.py"],
                "transport": "stdio",
            }
        }
    )
    tools = await client.get_tools()

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    # Create ToolNode
    tool_node = ToolNode(tools)

    def should_continue(state: MessagesState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END

    # Define call_model function
    async def call_model(state: MessagesState):
        messages = state["messages"]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # Build the graph
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        should_continue,
    )
    builder.add_edge("tools", "call_model")

    # Compile the graph
    graph = builder.compile()

    # Test the graph

    pandas_response = await graph.ainvoke(
        {"messages": [{"role": "user", "content": f"{inputstr}；待处理的文件路径:{filepath}"}]}
    )

    return pandas_response

def save_upload_file(upload_file: UploadFile, sessionId: UUID) -> str:
    """保存上传的文件并返回文件路径"""
    try:
        # 将 sessionId 转换为字符串
        session_id_str = str(sessionId)
        sesion_upload_dir = upload_dir / session_id_str

        # 确保目录存在
        sesion_upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = sesion_upload_dir / upload_file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return str(file_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e  # 重新抛出异常以便调用方处理
    finally:
        upload_file.file.close()

# 启动事件循环
if __name__ == "__main__":

    print("Weather Response:")