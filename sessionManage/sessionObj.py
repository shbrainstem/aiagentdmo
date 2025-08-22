from pydantic import BaseModel
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional

# 定义会话数据结构
class SessionData(BaseModel):
    username: str
    name: str
    address: str
    phone: str
    showname: str
    role: str
    # 新增对话历史字段
    conversation_history: List[Dict[str, str]] = []
    tool_calls: List[Dict] = []
    current_step: Annotated[int, lambda x, y: x + 1] = 0
    knowledge_base_name: Optional[str] = None
    tmpfilepath: Optional[str] = None