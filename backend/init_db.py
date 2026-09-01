import asyncio
import app.models
from app.database.session import engine, Base

async def init_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_tables())
