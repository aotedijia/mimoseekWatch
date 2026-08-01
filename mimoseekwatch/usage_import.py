from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation


def _key(value: str) -> str:
    return re.sub(r"[\s_\-./()（）]", "", value.strip().lower().lstrip("\ufeff"))


def _integer(value: str) -> int:
    try:
        return int(Decimal(value.replace(",", "").strip() or "0"))
    except InvalidOperation:
        return 0


def _decimal(value: str) -> Decimal:
    cleaned = value.replace(",", "").replace("¥", "").replace("￥", "").replace("$", "").strip()
    try:
        return Decimal(cleaned or "0")
    except InvalidOperation:
        return Decimal(0)


def _rows(data: bytes) -> list[dict[str, str]]:
    text = None
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("无法识别 CSV 编码")
    reader = csv.DictReader(io.StringIO(text))
    return [{_key(key): value or "" for key, value in row.items() if key} for row in reader]


def _value(row: dict[str, str], *names: str) -> str:
    for name in names:
        target = _key(name)
        for key, value in row.items():
            if target in key:
                return value
    return ""


def _date(value: str) -> str:
    digits = re.sub(r"\D", "", value)[:8]
    if len(digits) != 8:
        return ""
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def _model(value: str) -> str:
    name = value.strip().lower()
    if "pro" in name or "reasoner" in name:
        return "deepseek-v4-pro"
    if "flash" in name or "chat" in name:
        return "deepseek-v4-flash"
    return name or "unknown"


def parse_usage_export(filename: str, data: bytes) -> list[dict]:
    files: dict[str, bytes] = {}
    if filename.lower().endswith(".zip") or data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
                if base.endswith(".csv"):
                    files[base] = archive.read(name)
    else:
        files[filename.lower()] = data

    amount_files = [value for name, value in files.items() if "amount" in name]
    cost_files = [value for name, value in files.items() if "cost" in name]
    if not amount_files and not cost_files:
        # A standalone CSV may have either schema; inspect it as amount first.
        amount_files = list(files.values())

    aggregates = defaultdict(lambda: {
        "input_tokens": 0, "cached_tokens": 0, "uncached_tokens": 0,
        "output_tokens": 0, "total_tokens": 0, "request_count": 0,
        "costs": defaultdict(Decimal),
    })

    for content in amount_files:
        for row in _rows(content):
            date = _date(_value(row, "utcdate", "date", "日期"))
            model = _model(_value(row, "model", "模型"))
            if not date or model == "unknown":
                continue
            kind = _key(_value(row, "type", "类型"))
            amount = _integer(_value(row, "amount", "数量"))
            item = aggregates[(date, model)]
            if "requestcount" in kind or "请求次数" in kind:
                item["request_count"] += amount
                continue
            if "token" not in kind and "令牌" not in kind:
                continue
            if "output" in kind or "输出" in kind:
                item["output_tokens"] += amount
            elif "cachehit" in kind or "缓存命中" in kind:
                item["input_tokens"] += amount
                item["cached_tokens"] += amount
            else:
                item["input_tokens"] += amount
                item["uncached_tokens"] += amount
            item["total_tokens"] += amount

    for content in cost_files:
        for row in _rows(content):
            date = _date(_value(row, "utcdate", "date", "日期"))
            model = _model(_value(row, "model", "模型"))
            if not date or model == "unknown":
                continue
            currency = (_value(row, "currency", "币种", "货币") or "CNY").strip().upper()
            aggregates[(date, model)]["costs"][currency] += _decimal(_value(row, "cost", "费用", "金额"))

    records = []
    for (date, model), item in sorted(aggregates.items()):
        currencies = item["costs"] or {"CNY": Decimal(0)}
        has_official_cost = bool(item["costs"])
        for currency, cost in currencies.items():
            if not item["total_tokens"] and not cost and not item["request_count"]:
                continue
            records.append({
                "created_at": f"{date}T12:00:00+00:00", "provider": "deepseek", "model": model,
                "endpoint": "import:official-usage", "status_code": 200, "latency_ms": 0,
                "input_tokens": item["input_tokens"], "cached_tokens": item["cached_tokens"],
                "uncached_tokens": item["uncached_tokens"], "output_tokens": item["output_tokens"],
                "total_tokens": item["total_tokens"], "cost": float(cost), "currency": currency,
                "priced": int(has_official_cost), "request_count": item["request_count"],
                "source_id": f"deepseek-official:{date}:{model}:{currency}",
            })
    if not records:
        raise ValueError("文件中没有识别到 DeepSeek 用量记录")
    return records
