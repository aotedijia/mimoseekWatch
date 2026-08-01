from mimoseekwatch.database import Database, utc_now


def test_database_roundtrip(tmp_path):
    db = Database(tmp_path / "test.db")
    db.record_usage({
        "created_at": utc_now(), "provider": "deepseek", "model": "deepseek-v4-flash",
        "endpoint": "/chat/completions", "status_code": 200, "latency_ms": 12,
        "input_tokens": 10, "cached_tokens": 2, "uncached_tokens": 8,
        "output_tokens": 4, "total_tokens": 14, "cost": 0.001,
        "currency": "CNY", "priced": 1, "request_count": 1,
        "source_id": "deepseek-official:2026-08-01:deepseek-v4-flash:CNY",
    })
    result = db.summary()
    assert result["providers"][0]["total_tokens"] == 14
    assert result["recent"][0]["model"] == "deepseek-v4-flash"


def test_old_proxy_rows_are_hidden(tmp_path):
    db = Database(tmp_path / "test.db")
    db.record_usage({
        "created_at": utc_now(), "provider": "mimo", "model": "mimo-v2",
        "endpoint": "/chat/completions", "status_code": 200, "latency_ms": 12,
        "input_tokens": 10, "cached_tokens": 0, "uncached_tokens": 10,
        "output_tokens": 4, "total_tokens": 14, "cost": 0.001,
        "currency": "CNY", "priced": 1,
    })
    result = db.summary()
    assert result["providers"] == []
    assert result["recent"] == []
