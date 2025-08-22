import asyncio
import logging
import os
import sys
import aiomysql

# 日志配置（保持不变）
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(".\debug\mcp_debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("mysql_server")

# 环境变量配置（保持不变）
os.environ["MYSQL_HOST"] = "localhost"
os.environ["MYSQL_PORT"] = "3306"
os.environ["MYSQL_USER"] = "root"
os.environ["MYSQL_PASSWORD"] = "oneapimmysql"
os.environ["MYSQL_DATABASE"] = "oneapi"

# 全局连接池（避免频繁创建连接）
_pool = None


def get_db_config():
    """获取数据库配置（增加连接池参数）"""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
        "minsize": 3,
        "maxsize": 10
    }


async def get_pool():
    """创建全局连接池（单例模式）"""
    global _pool
    if not _pool or _pool.closed:
        config = get_db_config()
        _pool = await aiomysql.create_pool(**config)
    return _pool


async def close_pool():
    """安全关闭连接池"""
    global _pool
    if _pool and not _pool.closed:
        _pool.close()
        await _pool.wait_closed()
        logger.info("数据库连接池已安全关闭")
        _pool = None


async def get_users_info(username: str, password: str) -> dict:
    """通过username获取用户信息并验证密码"""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 查询用户信息（包含密码字段）
                query = "SELECT id, username, password, showname, age, address, phone, role FROM userinfo WHERE username = %s"
                await cursor.execute(query, (username,))
                user_data = await cursor.fetchone() or {}

                # 添加auth字段验证密码匹配
                if user_data:
                    # 比较传入密码与数据库密码
                    auth_result = (password == user_data['password'])

                    # 从结果中移除密码字段（安全考虑）[4,8](@ref)
                    user_data.pop('password', None)

                    # 添加auth验证字段[1,3](@ref)
                    user_data['auth'] = auth_result
                else:
                    # 用户不存在时返回空字典并设置auth=False
                    user_data = {'auth': False}

                return user_data

    except Exception as e:
        logger.error(f"查询失败: {username} | 错误: {str(e)}")
        # 返回包含auth=False的字典[4](@ref)
        return {'auth': False}

async def main():
    try:
        # 直接调用异步函数
        user_data = await get_users_info("admin", "123")
        print(user_data)
    finally:
        # 程序退出前关闭连接池
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
