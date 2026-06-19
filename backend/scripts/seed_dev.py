import asyncio

from app.db.seed import seed
from app.db.session import SessionFactory


async def main() -> None:
    async with SessionFactory() as s:
        await seed(s)


if __name__ == "__main__":
    asyncio.run(main())
