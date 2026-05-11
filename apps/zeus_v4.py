from __future__ import annotations

import asyncio

from nexus_core.v4.core import ZeusCognitiveCoreV4


async def main() -> None:
    core = ZeusCognitiveCoreV4()
    await core.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
