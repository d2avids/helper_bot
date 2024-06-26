import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)

from database.models import Base

load_dotenv()

engine = create_async_engine(os.getenv('DATABASE_PATH'), echo=False)

session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
