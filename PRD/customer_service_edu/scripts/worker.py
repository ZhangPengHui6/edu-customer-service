"""后台 worker 启动器。

默认同时运行 AI 轮次消费者和 Outbox 投递器；
生产环境也可以拆成两个进程：``python scripts/worker.py --only turn``。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys

from edu_cs.db import engine
from edu_cs.redis_client import get_async_redis
from edu_cs.workers.outbox_worker import OutboxPublisher
from edu_cs.workers.turn_worker import TurnWorker

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="edu-cs background workers")
    parser.add_argument(
        "--only",
        choices=("all", "turn", "outbox"),
        default="all",
        help="只启动指定 worker",
    )
    return parser.parse_args()


async def _run(only: str) -> None:
    workers = []
    if only in ("all", "turn"):
        workers.append(TurnWorker())
    if only in ("all", "outbox"):
        workers.append(OutboxPublisher())

    tasks = [
        asyncio.create_task(worker.run_forever(), name=type(worker).__name__)
        for worker in workers
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await get_async_redis().aclose()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _parse_args()
    try:
        asyncio.run(_run(args.only))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
