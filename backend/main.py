"""问数 API - 主入口"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from models.base import Base, engine, ensure_columns
from models import File  # 导入模型以确保表被创建
from api import api_router
from core.logging import setup_logging, get_logger
from core import paths

# 配置日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENV} mode")

    # 创建数据库表并为老库补列
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    logger.info("Database tables initialized")

    yield

    # 关闭时
    logger.info(f"Shutting down {settings.APP_NAME}")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    description="问数平台 API - 支持数据分析、文件上传和 AI 对话",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url="/redoc" if settings.ENV != "prod" else None,
)

# CORS 配置
if settings.ENV == "prod" or paths.is_frozen():
    allow_origins = []
else:
    allow_origins = ["http://localhost:3000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
    }


class SPAStaticFiles(StaticFiles):
    """SPA 静态资源：未知路径回退到 index.html（前端 history 路由需要）。"""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


# 生产模式下挂载前端静态资源
if (settings.ENV == "prod" or paths.is_frozen()) and paths.get_frontend_dist_dir():
    dist_dir = paths.get_frontend_dist_dir()
    logger.info(f"Serving frontend static files from {dist_dir}")
    app.mount("/", SPAStaticFiles(directory=dist_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,  # reload 在后台运行不稳定，开发时请手动重启
    )
