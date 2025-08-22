from redis.asyncio import Redis
from uuid import UUID, uuid4
from fastapi_sessions.backends.session_backend import SessionBackend
from typing import Dict, Optional
import logging
import asyncio
import os
from sessionManage.sessionObj import SessionData

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redis_session")

#redis的key
os.environ["REDIS_PASSWORD"] = "mypassword"
os.environ["REDIS_URL"] ="localhost:6379"
my_redis_url =  f"redis://:{os.getenv('REDIS_PASSWORD', '')}@{os.getenv('REDIS_URL', '')}"


# Redis会话存储后端（支持异步和并发安全）
class RedisBackend(SessionBackend[UUID, SessionData]):
    def __init__(self, redis_url: str =  my_redis_url, expire_seconds: int = 1800):
        self.redis_url = redis_url
        self.expire_seconds = expire_seconds  # 会话过期时间（30分钟）
        self.redis_pool = None
        logger.info(f"初始化Redis会话存储，URL: {redis_url}，过期时间: {expire_seconds}秒")

    async def connect(self):
        """创建Redis连接池"""
        if not self.redis_pool:
            self.redis_pool = Redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Redis连接池创建成功")

    async def _get_key(self, session_id: UUID) -> str:
        """生成Redis键名"""
        return f"session:{session_id}"

    async def create(self, session_id: UUID, data: SessionData):
        """创建新会话"""
        await self.connect()
        key = await self._get_key(session_id)
        # 使用 model_dump_json() 替代弃用的 json() 方法
        await self.redis_pool.setex(
            key,
            self.expire_seconds,
            data.model_dump_json()
        )
        logger.info(f"创建会话: {session_id}")

    async def read(self, session_id: UUID) -> Optional[SessionData]:
        """读取会话数据"""
        await self.connect()
        key = await self._get_key(session_id)
        data_json = await self.redis_pool.get(key)

        if data_json:
            # 更新过期时间（滑动过期）
            await self.redis_pool.expire(key, self.expire_seconds)
            logger.info(f"读取并更新会话: {session_id}")
            return SessionData.model_validate_json(data_json)  # 使用 model_validate_json()
        return None

    async def update(self, session_id: UUID, data: SessionData):
        """更新会话数据"""
        await self.connect()
        key = await self._get_key(session_id)
        # 使用 model_dump_json() 替代弃用的 json() 方法
        await self.redis_pool.setex(
            key,
            self.expire_seconds,
            data.model_dump_json()
        )
        logger.info(f"更新会话: {session_id}")

    async def delete(self, session_id: UUID):
        """删除会话"""
        await self.connect()
        key = await self._get_key(session_id)
        await self.redis_pool.delete(key)
        logger.info(f"删除会话: {session_id}")

    async def close(self):
        """关闭Redis连接"""
        if self.redis_pool:
            await self.redis_pool.close()
            logger.info("Redis连接已关闭")

# 测试函数
async def test_redis_backend():
    """测试Redis会话后端功能"""
    logger.info("=" * 50)
    logger.info("开始测试Redis会话后端")
    logger.info("=" * 50)

    # 检查Redis密码环境变量
    redis_password = os.getenv("REDIS_PASSWORD", None)
    if redis_password:
        redis_url = f"redis://:{redis_password}@localhost:6379"
        logger.info("使用带密码的Redis连接")
    else:
        redis_url = "redis://localhost:6379"
        logger.info("使用无密码的Redis连接（如果服务器需要密码会失败）")

    # 创建后端实例（使用较短过期时间便于测试）
    backend = RedisBackend(redis_url=redis_url, expire_seconds=10)

    # 生成测试会话ID
    session_id = uuid4()
    logger.info(f"生成的测试会话ID: {session_id}")

    # 创建测试数据
    test_data = SessionData(
        username="john_doe",
        name="John Doe",
        address="123 Main St",
        phone="555-1234",
        showname="Johnny"
    )

    try:
        # 测试1: 创建会话
        logger.info("\n测试1: 创建会话")
        await backend.create(session_id, test_data)

        # 测试2: 读取会话
        logger.info("\n测试2: 读取会话")
        read_data = await backend.read(session_id)
        if read_data:
            logger.info(f"读取成功: {read_data}")
            assert read_data == test_data, "读取数据与原始数据不一致"
        else:
            logger.error("读取失败: 未找到会话数据")
            return

        # 测试3: 更新会话
        logger.info("\n测试3: 更新会话")
        updated_data = SessionData(
            username="jane_smith",
            name="Jane Smith",
            address="456 Oak Ave",
            phone="555-5678",
            showname="Janey"
        )
        await backend.update(session_id, updated_data)

        # 验证更新
        read_updated = await backend.read(session_id)
        if read_updated:
            logger.info(f"更新后数据: {read_updated}")
            assert read_updated == updated_data, "更新后数据不一致"
        else:
            logger.error("更新后读取失败")
            return

        # 测试4: 删除会话
        logger.info("\n测试4: 删除会话")
        await backend.delete(session_id)

        # 验证删除
        deleted_data = await backend.read(session_id)
        if deleted_data is None:
            logger.info("删除验证成功: 会话已不存在")
        else:
            logger.error(f"删除失败: 仍能读取到数据 {deleted_data}")
            return

        logger.info("\n所有测试通过！")
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        if "Authentication required" in str(e):
            logger.error("请设置 REDIS_PASSWORD 环境变量并提供正确的Redis密码")
            logger.error("例如: export REDIS_PASSWORD=yourpassword")
    finally:
        # 清理资源
        await backend.close()

# 主入口
if __name__ == "__main__":
    asyncio.run(test_redis_backend())