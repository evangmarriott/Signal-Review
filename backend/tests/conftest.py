from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.config import get_settings
from src.main import create_app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())
