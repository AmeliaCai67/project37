"""系统级接口：原生目录选择器（桌面打包版挂载本地文件夹用）"""
import asyncio
import multiprocessing as mp
import subprocess
import sys

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_user
from models.user import User
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# 目录选择最长等待时间（秒），超时视为用户取消并回收子进程
_PICKER_TIMEOUT = 180


def _pick_directory_macos() -> str:
    """
    macOS：用 osascript 调起 Finder 原生「选择文件夹」对话框。

    相比 tkinter 的优势：对话框由系统进程承载，始终显示在最前
    （tkinter 对话框属于无 Dock 图标的后台进程，macOS 会把它埋在浏览器后面，
    用户根本看不到）。用户取消时 osascript 以非零码退出。
    """
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'POSIX path of (choose folder with prompt "选择要挂载的数据文件夹")',
        ],
        capture_output=True,
        text=True,
        timeout=_PICKER_TIMEOUT,
    )
    if result.returncode != 0:
        # "User canceled. (-128)" 及其他取消/错误情形都按取消处理
        logger.info(f"Directory picker cancelled or failed: {result.stderr.strip()}")
        return ""
    return result.stdout.strip().rstrip("/")


def _picker_child_tkinter(conn):
    """
    Windows/Linux 目录选择器子进程入口（spawn 独立进程，必须模块级可 pickle）。

    独立进程原因：某些平台 Tk 要求窗口在进程主线程创建，直接调会阻塞
    uvicorn 事件循环；子进程有自己的主线程，两全。
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        try:
            root.withdraw()
            # 确保对话框出现在最前
            root.attributes("-topmost", True)
            path = filedialog.askdirectory(parent=root) or None
        finally:
            root.destroy()
        conn.send(("ok", path))
    except Exception as e:  # tkinter 缺失 / 无显示环境等
        conn.send(("err", str(e)))
    finally:
        conn.close()


def _run_picker_tkinter(timeout: int = _PICKER_TIMEOUT):
    """同步起 tkinter 子进程并等待结果，返回 ("ok", path|None) 或 ("err", message)。"""
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_picker_child_tkinter, args=(child_conn,))
    proc.start()
    child_conn.close()
    try:
        if parent_conn.poll(timeout):
            return parent_conn.recv()
        logger.warning(f"Directory picker timed out after {timeout}s")
        return ("ok", None)  # 超时按用户取消处理
    except (EOFError, OSError) as e:
        # 子进程异常退出（如 tkinter 导入即崩溃）
        return ("err", str(e))
    finally:
        if proc.is_alive():
            proc.terminate()
        proc.join()


def _run_picker():
    """按平台选择目录选择器实现，统一返回 ("ok", path|None) / ("err", message)。"""
    if sys.platform == "darwin":
        try:
            return ("ok", _pick_directory_macos() or None)
        except subprocess.TimeoutExpired:
            logger.warning("Directory picker (osascript) timed out")
            return ("ok", None)
        except Exception as e:
            return ("err", str(e))
    return _run_picker_tkinter()


@router.post("/pick-directory")
async def pick_directory(current_user: User = Depends(get_current_user)):
    """
    调起系统原生目录选择器。

    - 成功：{"path": "/Users/..."}
    - 用户取消 / 超时：{"path": None}
    - 环境不支持：503，前端回退到手动输入路径
    """
    loop = asyncio.get_running_loop()
    result_status, payload = await loop.run_in_executor(None, _run_picker)
    if result_status == "err":
        logger.warning(f"Native directory picker unavailable: {payload}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="当前环境不支持系统目录选择器，请手动输入路径",
        )
    return {"path": payload}
