from __future__ import annotations

import asyncio

from app.agent.checkpointer import setup_checkpointer


async def main() -> None:
    print("Setting up LangGraph PostgreSQL checkpoints...")

    await setup_checkpointer()

    print("LangGraph PostgreSQL checkpoints ready.")


if __name__ == "__main__":
    asyncio.run(main())