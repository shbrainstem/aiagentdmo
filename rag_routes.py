from fastapi import APIRouter, UploadFile, Form, File, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from uuid import UUID
import os
import logging
from sessionManage.sessionObj import SessionData
from rag.queryRagInfo import get_knowledge_bases,QueryRequest,query_knowledge_base
from rag.initRAGDB_local_model_wf import save_upload_file, read_file, process_content
from llmWithContextManage.talkWithRagContext import stream_generator_rag_ctx

# 配置日志
logger = logging.getLogger("rag_routes")

def create_rag_router(templates, get_session_data,verify_admin, cookie, backend):
    router = APIRouter()

    @router.get("/create_rag", response_class=HTMLResponse)
    async def create_rag(request: Request,
            session_data: SessionData = Depends(verify_admin)):
        """创建RAG页面"""
        return templates.TemplateResponse("rag/createrag.html", {"request": request})

    @router.post("/uploadragfile")
    async def uploadragfile(
            file: UploadFile = File(...),
            chunk_size: int = Form(1000),
            chunk_overlap: int = Form(200),
            separators: str = Form(""),
            user: str = Form("anonymous"),
            knowledge_base: str = Form("default"),
            session_data: SessionData = Depends(verify_admin)
    ):
        """提交md文件，创建知识库"""
        try:
            file_path = save_upload_file(file)
            content = read_file(file_path)

            result = process_content(
                content=content,
                source=file.filename,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=separators,
                user=user,
                knowledge_base_name=knowledge_base
            )

            os.remove(file_path)
            return result
        except Exception as e:
            logger.error(f"文件处理错误: {str(e)}")
            raise HTTPException(status_code=500, detail=f"文件处理错误: {str(e)}")

    @router.get("/knowledge-bases")
    async def api_get_knowledge_bases():
        """获取所有知识库名称列表"""
        bases = await get_knowledge_bases()
        logger.info(f"返回的知识库列表: {bases}")
        return bases


    @router.post("/query_rag")
    async def query_rag_list(request: QueryRequest,
            session_data: SessionData = Depends(verify_admin)):
        """查询知识库记录"""
        try:
           return await query_knowledge_base(request)
        except Exception as e:
            import traceback  # 新增导入traceback模块
            traceback.print_exc()  # 将异常堆栈打印到标准错误输出
            logger.exception("查询知识库错误")
            raise HTTPException(status_code=500, detail=f"查询知识库错误: {str(e)}")

    @router.get("/api/chat_rag_ctx", response_class=HTMLResponse)
    async def chat_rag_stream(
            question: str,
            knowledge_base: str,
            session_id: UUID = Depends(cookie),
            session_data: SessionData = Depends(get_session_data)):
        """流式RAG聊天接口"""
        return StreamingResponse(
            stream_generator_rag_ctx(question, session_id, session_data,backend, knowledge_base),
            media_type="text/event-stream"
        )

    @router.get("/chat_rag_ctx", response_class=HTMLResponse)
    async def chat_rag_page(request: Request,
            session_data: SessionData = Depends(get_session_data)):
        """RAG聊天页面"""
        return templates.TemplateResponse("chat_rag_ctx.html", {"request": request})

    return router
