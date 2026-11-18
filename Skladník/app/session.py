import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

SKLADNIK_DB_PATH = os.getenv("SKLADNIK_DB_PATH", "./procurement.db")
DATABASE_URL = f"sqlite+aiosqlite:///{SKLADNIK_DB_PATH}"

engine = create_async_engine(
    DATABASE_URL, echo=False
)

async_session = async_sessionmaker(engine, expire_on_commit=False)
