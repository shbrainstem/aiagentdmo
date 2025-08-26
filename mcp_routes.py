from fastapi import APIRouter, UploadFile, Form, File, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
import logging
from sessionManage.sessionObj import SessionData
from mcptools.mcp import save_upload_file,call_tools,PandasQueryRequest
import os
# 配置日志
logger = logging.getLogger("mcp_routes")

def create_mcp_router(templates, get_session_data, cookie, backend):
    router = APIRouter()

    @router.get("/call_mcp", response_class=HTMLResponse)
    async def create_rag(request: Request,
            session_data: SessionData = Depends(get_session_data)):
        """创建RAG页面"""
        return templates.TemplateResponse("mcp/mcppandas.html", {"request": request})

    @router.post("/uploadcsvfile")
    async def uploadcsvfile(
            file: UploadFile = File(...),
            session_id: str = Depends(cookie),
            session_data: SessionData = Depends(get_session_data)
    ):
        """提交md文件，创建知识库"""
        try:
            file_path = save_upload_file(file,session_id)
            session_data.tmpfilepath = file_path
            await backend.update(session_id, session_data)
            result = {"filepath":file_path,"status":'success'}
            return result
        except Exception as e:
            logger.error(f"文件处理错误: {str(e)}")
            result = {"filepath":str(e),"status":'fail'}
            raise HTTPException(status_code=500, detail=f"文件处理错误: {str(e)}")

    @router.post("/query_pandas")
    async def query_rag_list(request: PandasQueryRequest,
                             session_data: SessionData = Depends(get_session_data)):
        try:
            # 返回流式响应
            return StreamingResponse(
                call_tools(request.query_text, session_data.tmpfilepath),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        except Exception as e :
            import traceback
            traceback.print_exc()
            result = {"info": str(e), "status": 'fail'}
            return result
        finally:
            if session_data.tmpfilepath and os.path.exists(session_data.tmpfilepath):
                try:
                    # 获取文件所在目录路径
                    # dir_path = os.path.dirname(session_data.tmpfilepath)
                    # # 删除临时文件
                    # os.remove(session_data.tmpfilepath)
                    print(f"已删除临时文件: {session_data.tmpfilepath}")
                    # 尝试删除所在目录（如果目录为空）
                    # if os.path.exists(dir_path) and not os.listdir(dir_path):
                    #     os.rmdir(dir_path)
                    #     print(f"已删除空目录: {dir_path}")
                    # elif os.path.exists(dir_path):
                    #     print(f"目录非空，保留目录: {dir_path}")
                except Exception as e:
                    print(f"操作过程中出错: {e}")

    return router
