"""Project 37 桌面启动器

打包后的可执行文件入口。负责：
1. 切换到生产模式；
2. 确保用户数据目录与 .env 存在；
3. 启动 Uvicorn；
4. 自动打开浏览器。
"""
import os
import sys
import threading
import time
import webbrowser


def _ensure_environment():
    os.environ.setdefault("ENV", "prod")
    # 关键：在导入任何读取 settings 的模块前确保用户 .env 已生成
    from core import config_store

    config_store.ensure_user_config()


def _open_browser_when_ready(port: int, delay: float = 1.5):
    time.sleep(delay)
    url = f"http://127.0.0.1:{port}/"
    webbrowser.open(url)


def main():
    _ensure_environment()

    from core import paths
    from core.logging import setup_logging

    setup_logging()

    # 此时 settings 会加载用户目录 .env
    from main import app
    from config import settings

    port = int(os.environ.get("PORT", settings.PORT))

    # 隐藏控制台时，仍把未捕获异常写进日志
    def log_exception(exc_type, exc_value, exc_tb):
        import logging
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = log_exception

    browser_thread = threading.Thread(
        target=_open_browser_when_ready, args=(port,), daemon=True
    )
    browser_thread.start()

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
