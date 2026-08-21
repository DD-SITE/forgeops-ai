import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


TEST_DATABASE_URL = (
    "postgresql+asyncpg://"
    "forgeops:forgeops_dev_password@localhost:5433/forgeops_test"
)


@pytest.fixture
async def test_engine():
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    yield test_engine

    await test_engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session