


USER_DB = {
    "admin": {
        "password": "123",
        "name": "管理员",
        "address": "北京市海淀区",
        "phone": "13800138000",
        'auth':False
    },
    "user": {
        "password": "123",
        "name": "普通用户",
        "address": "上海市浦东新区",
        "phone": "13900139000",
        'auth':False
    }
}
def get_users_info(username: str, password: str) -> dict:
    user_data = USER_DB.get(username)
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