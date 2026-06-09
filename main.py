"""
Flarum AI Agent - 智能论坛回复机器人入口文件
FastAPI 主应用启动文件
"""

import logging
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse

import config
from api.webhook_listener import router as webhook_router

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用实例
app = FastAPI(
    title="Flarum AI Agent",
    description="基于大模型的 Flarum 论坛智能回复机器人",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 注册路由
app.include_router(webhook_router, prefix="/api", tags=["webhook"])


@app.get("/")
async def root():
    """根路由 - 健康检查"""
    return {
        "status": "ok",
        "message": "Hello Flarum AI Agent",
        "service": "Flarum AI Agent",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": logging.Formatter().formatTime(logging.LogRecord(
            name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
        ))
    }


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("=" * 50)
    logger.info("🚀 Flarum AI Agent 启动成功")
    logger.info(f"📡 Webhook 监听端口: {config.WEBHOOK_PORT}")
    logger.info(f"🧠 世界书路径: {config.WORLD_BOOK_PATH}")
    logger.info(f"💾 ChromaDB 路径: {config.CHROMA_DB_PATH}")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("🛑 Flarum AI Agent 正在关闭...")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.WEBHOOK_PORT,
        reload=True,
        log_level=config.LOG_LEVEL.lower()
    )