# AI Agent Demo 

# 环境信息
## python
- 版本 3.11.9 
- requirements.txt
## 数据库初始化
- 0_DOC/SQL 目录下是mysql数据库和postgresql数据库的初始化脚本
- mysql用于用户管理 版本 8.0.36
- postgresql用于知识库 版本 4.9.6
- redis 用于会话存储 版本 4.9.6

# 功能说明
## 账号管理
- 主程序 main.py 端口8000
- 支持登录，登出
- 默认用户 admin/123 （可以添加知识库） ; user/123
## 对话上下文管理+流式输出
- talkwithContext.py 实现上下文管理,利用redis存储会话的上下文
- talkwitRagContext.py 集成知识库的对话，利用reids存储会话上下文

## 知识库功能
- 入口程序 rag_router.py
- 使用postgresql作为向量库
- embedding模型和reranker模型用huggingface方式加载 模型文件本地存储，配置信息参考config/config.json
- intiRAGDB_local_model_wf.py 初始化本地知识库
- queryRagInfo.py 查询本地知识库

## 集成MCP
- 入口程序 mcp_router.py
- 主要方法在mcp.py
- 上传csv/excel文件，然后输出希望处理的描述

## 对话上下文管理
- 目录 sessionManage；
- 主要用redisSession.py实现

