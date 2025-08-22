
from sessionManage.redisSession import RedisBackend
import json
from langgraph.checkpoint.base import Checkpoint
from redis import Redis
from typing import Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_deepseek import ChatDeepSeek
import os
from typing import TypedDict, Annotated, Sequence
import operator

# 使用Redis作为会话存储后端
os.environ["REDIS_PASSWORD"] = "mypassword"
os.environ["REDIS_URL"] ="localhost:6379"
my_redis_url =  f"redis://:{os.getenv('REDIS_PASSWORD', '')}@{os.getenv('REDIS_URL', '')}"

class RedisCheckpointer:
    def __init__(self, redis_url=my_redis_url):
        self.redis = Redis.from_url(redis_url)

    def save(self, session_id: str, checkpoint: Checkpoint) -> None:
        self.redis.set(f"checkpoint:{session_id}", json.dumps(checkpoint))

    def load(self, session_id: str) -> Optional[Checkpoint]:
        data = self.redis.get(f"checkpoint:{session_id}")
        return json.loads(data) if data else None

    def delete(self, session_id: str):
        self.redis.delete(f"checkpoint:{session_id}")

# 环境变量设置
from llms.DeepSeekLLM import getDeepSeek
# 初始化模型


class MyMessageState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    userStr: str

def get_model():
    llm = getDeepSeek()


def model_node(state: MyMessageState):
    model = get_model()
    response = model.invoke(state["messages"])
    return {"messages": [AIMessage(content=response.content)]}

def user_node(state: MyMessageState):
    return {"messages": [HumanMessage(content=state["messages"][-1]["content"])]}


def create_graph():
    builder = StateGraph(MyMessageState)
    builder.add_node("model", model_node)
    builder.add_node("user", user_node)

    builder.set_entry_point("user")
    builder.add_edge("user", "model")
    builder.add_edge("model", END)

    return builder.compile()
