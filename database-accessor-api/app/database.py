import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DB_USER = os.getenv("TIMESCALEDB_USER")
DB_PASSWORD = os.getenv("TIMESCALEDB_PASSWORD")
DB_HOST = os.getenv("TIMESCALEDB_HOST")
DB_PORT = os.getenv("TIMESCALEDB_PORT")
DB_NAME = os.getenv("TIMESCALEDB_DB")
DB_ECHO = os.getenv("TIMESCALEDB_ECHO", "false").lower() == "true"

# Construct URL
DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_async_engine(DATABASE_URL, echo=DB_ECHO)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
