"""
Pytest configuration and fixtures.
"""
import pytest
import os
import asyncio

# Set test environment variables before importing app modules
os.environ.setdefault("WEBHOOK_SECRET", "testsecret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Initialize test database before each test."""
    from app.storage import init_db
    await init_db()
    yield
