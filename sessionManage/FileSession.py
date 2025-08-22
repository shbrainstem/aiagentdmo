
from uuid import UUID, uuid4
import os
import json
import aiofiles
import asyncio
from fastapi_sessions.backends.session_backend import SessionBackend
from typing import Dict, Optional
from sessionManage.sessionObj import SessionData

# 自定义文件存储后端（支持异步和并发安全）
class FileBackend(SessionBackend[UUID, SessionData]):
    def __init__(self, file_path: str = "sessions/session_store.json"):
        self.file_path = file_path
        self.lock = asyncio.Lock()
        # 确保目录存在（同步操作，仅在初始化时执行）
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        # 如果文件不存在则创建空文件（异步）
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump({}, f)

    async def _load_data(self) -> Dict[str, dict]:
        async with self.lock:
            try:
                async with aiofiles.open(self.file_path, 'r') as f:
                    content = await f.read()
                    return json.loads(content) if content else {}
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    async def _save_data(self, data: Dict[str, dict]):
        async with self.lock:
            async with aiofiles.open(self.file_path, 'w') as f:
                await f.write(json.dumps(data, ensure_ascii=False))

    async def create(self, session_id: UUID, data: SessionData):
        sessions = await self._load_data()
        sessions[str(session_id)] = data.dict()
        await self._save_data(sessions)

    async def read(self, session_id: UUID) -> Optional[SessionData]:
        sessions = await self._load_data()
        data = sessions.get(str(session_id))
        return SessionData(**data) if data else None

    async def update(self, session_id: UUID, data: SessionData):
        sessions = await self._load_data()
        sessions[str(session_id)] = data.dict()
        await self._save_data(sessions)

    async def delete(self, session_id: UUID):
        sessions = await self._load_data()
        if str(session_id) in sessions:
            del sessions[str(session_id)]
            await self._save_data(sessions)
