"""Project-wide pytest fixtures."""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """캐시(Redis/LocMemCache) 상태가 테스트 사이에 새어나가지 않도록 매 테스트 전후로 비운다."""
    cache.clear()
    yield
    cache.clear()
