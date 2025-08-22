from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from typing import TypedDict, Annotated, Sequence, List, Dict, Any
import operator
import os
from langchain_core.messages import HumanMessage, AIMessage,SystemMessage
from sessionManage.sessionObj import SessionData
from sessionManage.redisSession import RedisBackend
from ddgs import DDGS
import asyncio

from llms.DeepSeekLLM import getDeepSeek
# 初始化模型
llm = getDeepSeek()

@tool
def web_search(query: str) -> str:
    """使用DuckDuckGo搜索最新信息。"""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            # 简化结果格式，避免特殊字符
            return "\n".join([f"{res['title']}: {res['body'][:150]}..." for res in results])
    except Exception as e:
        return f"搜索错误: {str(e)}"

tools = [web_search]
llm_with_tools = llm.bind_tools(tools)

# 2. 定义Agent状态
class AgentState(TypedDict):
    messages: Annotated[Sequence[HumanMessage], operator.add]
    tool_calls: List[Dict] = []
    current_step: Annotated[int, lambda x, y: x + 1] = 0

# 3. 定义工作流节点
def should_continue(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "invoke_tool"
    return "end"

def call_model(state: AgentState) -> dict:
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)

    if hasattr(response, "tool_calls") and response.tool_calls:
        return {
            "messages": [response],
            "tool_calls": response.tool_calls
        }
    return {"messages": [response]}

def call_tool(state: AgentState) -> dict:
    tool_calls = state["tool_calls"]
    tool_responses = []

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_input = tool_call["args"]

        # 查找并执行对应工具
        selected_tool = next((t for t in tools if t.name == tool_name), None)
        if not selected_tool:
            result = f"未知工具: {tool_name}"
        else:
            try:
                result = selected_tool.invoke(tool_input)
            except Exception as e:
                result = f"工具执行错误: {str(e)}"

        tool_responses.append(ToolMessage(
            tool_call_id=tool_call["id"],
            content=str(result),
            name=tool_name
        ))

        # 打印工具调用日志
        print(f"\n🔧 工具调用: {tool_name}({tool_input})")
        print(f"  结果: {str(result)[:200]}...")

    return {"messages": tool_responses, "tool_calls": []}


# 4. 构建工作流
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tool", call_tool)
workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "invoke_tool": "tool",
        "end": END
    }
)
workflow.add_edge("tool", "agent")
agent_workflow = workflow.compile()

# 6. 流式响应生成器
async def generate_stream_response(input_text: str,session_id : str ,session_data: SessionData,backend: RedisBackend):
    history = session_data.conversation_history
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "ai":
            messages.append(AIMessage(content=msg["content"]))
        elif msg["role"] == "system":
            messages.append(SystemMessage(content=msg["content"]))
    messages.append(HumanMessage(content=input_text))

    # 初始化状态
    state = {"messages": messages}
    session_data.conversation_history.append({"role": "user", "content": input_text})
    collected_chunks = []

    # 运行工作流
    async for step in agent_workflow.astream(state):
        for node, node_state in step.items():
            if node == "agent" and node_state.get("messages"):
                last_msg = node_state["messages"][-1]

                # 流式处理最终AI响应
                if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
                    if hasattr(last_msg, "content"):
                        for token in last_msg.content:
                            await asyncio.sleep(0.02)  # 控制流式速度
                            collected_chunks.append(token)
                            yield f"data: {token}\n\n"
                    session_data.conversation_history.append(
                        {"role": "ai", "content": ''.join(map(str, collected_chunks))})
                    await backend.update(session_id, session_data)
                    # 发送结束信号
                    yield "data: [DONE]\n\n"
                    return
