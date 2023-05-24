import struct

import asyncio


class Test:
    def __init__(self) -> None:
        self.future = asyncio.ensure_future(self.optimistic_unchoking_choice())

    async def optimistic_unchoking_choice(self):
        assert(False)


Test()