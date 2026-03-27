import os

import pytest
import redis


RUN_REDIS_TESTS = os.getenv("RUN_REDIS_TESTS", "").lower() in {"1", "true", "t", "yes", "y", "on"}


@pytest.mark.skipif(not RUN_REDIS_TESTS, reason="set RUN_REDIS_TESTS=1 to enable")
def test_redis_ping():
    client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", "6379")))
    assert client.ping() is True


@pytest.mark.skipif(not RUN_REDIS_TESTS, reason="set RUN_REDIS_TESTS=1 to enable")
def test_redis_set_get_roundtrip():
    client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", "6379")))
    key = "healthcheck:roundtrip"
    assert client.set(key, "1", ex=10) is True
    assert client.get(key) == b"1"
