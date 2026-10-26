"""本地开发启动器。

Windows 上 psycopg 异步模式不支持默认的 ProactorEventLoop，
这里统一切到 SelectorEventLoop；Linux 部署直接用 uvicorn 命令即可。
"""

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
        "edu_cs.main:app",
        host=_arg("--host", "127.0.0.1"),
        port=int(_arg("--port", "8000")),
        reload="--reload" in sys.argv[1:],
        # uvicorn 0.36+ 在 Windows 上强制 ProactorEventLoop，会破坏 psycopg 异步；
        # 传 loop="none" 让它沿用上面设置的 SelectorEventLoop。
        loop="none",
    )
