from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uuid import UUID, uuid4
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from userManage.onebankUser import get_users_info, close_pool
import logging
from sessionManage.redisSession import RedisBackend
from sessionManage.sessionObj import SessionData
from fastapi.responses import StreamingResponse
from llmNoContextManage.dsTalkStream import stream_generator
from llmWithContextManage.talkWithContext import stream_generator_ctx
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, Request
import os
from rag_routes import create_rag_router  # 导入RAG路由
from mcp_routes import create_mcp_router  # 导入RAG路由

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redis_session")

# 初始化应用
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 会话配置
cookie_params = CookieParameters(secure=False)
cookie = SessionCookie(
    cookie_name="session_cookie",
    identifier="session_verifier",
    auto_error=True,
    secret_key="DONOTUSE-IN-PRODUCTION",
    cookie_params=cookie_params
)

# 使用Redis作为会话存储后端
backend = RedisBackend()

# 应用生命周期事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await backend.close()
    await close_pool()
    logger.info("应用资源已清理")


# 会话验证依赖
async def get_session_data(
        session_id: UUID = Depends(cookie)
) -> SessionData:
    data = await backend.read(session_id)
    if data is None:
        raise HTTPException(status_code=401, detail="未登录")
    return data

async def verify_admin(
    session_data: SessionData = Depends(get_session_data)
) -> SessionData:
    """验证用户是否为管理员角色"""
    logger.info(f"role={session_data.role}")
    if session_data.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="无权限访问该资源"
        )
    return session_data

# 创建并挂载RAG路由

# 登录页面
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# 登录处理
@app.post("/login")
async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...)
):
    try:
        # 获取用户信息并验证密码
        user = await get_users_info(username, password)
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "系统错误，请重试"}
        )

    if not user or not user["auth"]:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "用户名或密码错误"}
        )

    session_id = uuid4()
    session_data = SessionData(
        username=username,
        name=username,
        address=user['address'],
        phone=user['phone'],
        showname=user['showname'],
        role=user['role'],
    )

    await backend.create(session_id, session_data)
    response = RedirectResponse(url="/profile", status_code=303)
    cookie.attach_to_response(response, session_id)
    return response

# 用户登录跳转页
@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
        request: Request,
        session_data: SessionData = Depends(get_session_data)
):
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "username": session_data.username,
            "name": session_data.name,
            "address": session_data.address,
            "phone": session_data.phone,
            "showname": session_data.showname,
            "role":session_data.role
        }
    )

# 注销
@app.post("/logout")
async def logout(request: Request, session_id: UUID = Depends(cookie)):
    await backend.delete(session_id)
    response = RedirectResponse(url="/", status_code=303)
    cookie.delete_from_response(response)
    return response


@app.get("/api/chat", response_class=HTMLResponse)
async def chat_stream(question: str,
        session_data: SessionData = Depends(get_session_data)):
    """流式聊天接口"""
    return StreamingResponse(
        stream_generator(question),
        media_type="text/event-stream"
    )

@app.get("/chat", response_class=HTMLResponse)
async def index(request: Request,
        session_data: SessionData = Depends(get_session_data)):
    """主页面"""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/api/chat_ctx", response_class=HTMLResponse)
async def chat_stream(question: str,
                      session_id: str = Depends(cookie),
                      session_data: SessionData = Depends(get_session_data)):
    """流式聊天接口,可保留上下文"""
    return StreamingResponse(
        stream_generator_ctx(question,session_id,session_data,backend),
        media_type="text/event-stream"
    )

@app.get("/chat_ctx", response_class=HTMLResponse)
async def index(request: Request,
        session_data: SessionData = Depends(get_session_data)):
    """主页面"""
    return templates.TemplateResponse("chat_ctx.html", {"request": request})


@app.get("/api/chat_ddgs", response_class=HTMLResponse)
async def chat_stream(question: str,
                      session_id: str = Depends(cookie),
        session_data: SessionData = Depends(get_session_data)):
    """流式聊天接口,可保留上下文"""
    if not question:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    from llmWithddgs.llmWithddgs import generate_stream_response
    return StreamingResponse(
        generate_stream_response(question,session_id,session_data,backend),
        media_type="text/event-stream"
    )

@app.get("/chat_ddgs", response_class=HTMLResponse)
async def index(request: Request,
        session_data: SessionData = Depends(get_session_data)):
    """主页面"""
    return templates.TemplateResponse("chat_ddgs.html", {"request": request})


rag_router = create_rag_router(templates, get_session_data,verify_admin, cookie ,backend)
app.include_router(rag_router)

mcp_router = create_mcp_router(templates, get_session_data, cookie ,backend)
app.include_router(mcp_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)