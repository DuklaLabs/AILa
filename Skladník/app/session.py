from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = "sqlite+aiosqlite:///./procurement.db"

engine = create_async_engine(
    DATABASE_URL, echo=False
)

async_session = async_sessionmaker(engine, expire_on_commit=False)
