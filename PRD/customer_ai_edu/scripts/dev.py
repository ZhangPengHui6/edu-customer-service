"""本地开发启动器（Windows 使用 SelectorEventLoop，原因同客服服务）。"""

import asyncio
import sys

import uvicorn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _arg(name: str, default: str) -> str:
    args = sys.argv[1:]
    if name in args:
        return args[args.index(name) + 1]
    return default


if __name__ == "__main__":
    uvicorn.run(
        "edu_ai.main:app",
        host=_arg("--host", "127.0.0.1"),
        port=int(_arg("--port", "8002")),
        reload="--reload" in sys.argv[1:],
        # 同客服服务：避免 uvicorn 在 Windows 上强制 ProactorEventLoop。
        loop="none",
    )
