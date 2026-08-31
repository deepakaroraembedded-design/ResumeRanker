from __future__ import annotations

from resume_ranker.llm.cache import Cache


class TestCache:
    def test_key_is_stable(self) -> None:
        cache = Cache(":memory:")
        key1 = cache.key(
            model_id="m",
            template_version="E-PARSE-v1",
            prompt="hello",
            sample_index=0,
        )
        key2 = cache.key(
            model_id="m",
            template_version="E-PARSE-v1",
            prompt="hello",
            sample_index=0,
        )
        assert key1 == key2
        assert len(key1) == 64

    def test_key_changes_with_sample_index(self) -> None:
        cache = Cache(":memory:")
        key1 = cache.key(
            model_id="m", template_version="E-PARSE-v1", prompt="hello", sample_index=0
        )
        key2 = cache.key(
            model_id="m", template_version="E-PARSE-v1", prompt="hello", sample_index=1
        )
        assert key1 != key2

    def test_round_trip(self, cache: Cache) -> None:
        key = cache.key(model_id="m", template_version="E-PARSE-v1", prompt="hello", sample_index=0)
        assert cache.get_sync(key) is None
        cache.put_sync(key, b"value")
        assert cache.get_sync(key) == b"value"

    def test_async_round_trip(self, cache: Cache) -> None:
        key = cache.key(model_id="m", template_version="E-PARSE-v1", prompt="hello", sample_index=0)

        async def _test() -> None:
            assert await cache.get(key) is None
            await cache.put(key, b"value")
            assert await cache.get(key) == b"value"
            await cache.clear()
            assert await cache.get(key) is None

        import asyncio

        asyncio.run(_test())

    def test_len(self, cache: Cache) -> None:
        assert len(cache) == 0
        key = cache.key(model_id="m", template_version="E-PARSE-v1", prompt="hello", sample_index=0)
        cache.put_sync(key, b"value")
        assert len(cache) == 1

    def test_replace(self, cache: Cache) -> None:
        key = cache.key(model_id="m", template_version="E-PARSE-v1", prompt="hello", sample_index=0)
        cache.put_sync(key, b"first")
        cache.put_sync(key, b"second")
        assert cache.get_sync(key) == b"second"
