import io
import zipfile

from mimoseekwatch.usage_import import parse_usage_export


def test_imports_official_usage_zip():
    amount = "UTCDate,Model,Type,Amount,Price\n20260801,deepseek-v4-flash,InputCacheHitTokens,100,0.00000002\n20260801,deepseek-v4-flash,InputCacheMissTokens,50,0.000001\n20260801,deepseek-v4-flash,OutputTokens,20,0.000002\n20260801,deepseek-v4-flash,RequestCount,3,0\n"
    cost = "UTCDate,Model,Cost,Currency\n20260801,deepseek-v4-flash,0.000092,CNY\n"
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("amount.csv", amount)
        archive.writestr("cost.csv", cost)

    records = parse_usage_export("usage.zip", data.getvalue())
    assert len(records) == 1
    record = records[0]
    assert record["cached_tokens"] == 100
    assert record["uncached_tokens"] == 50
    assert record["output_tokens"] == 20
    assert record["total_tokens"] == 170
    assert record["request_count"] == 3
    assert record["cost"] == 0.000092


def test_rejects_unrecognized_csv():
    try:
        parse_usage_export("other.csv", b"foo,bar\na,b\n")
    except ValueError as error:
        assert "没有识别到" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_does_not_calculate_cost_from_amount_price():
    amount = b"UTCDate,Model,Type,Amount,Price\n20260801,deepseek-v4-flash,OutputTokens,20,99\n"
    record = parse_usage_export("amount.csv", amount)[0]
    assert record["cost"] == 0
    assert record["priced"] == 0
