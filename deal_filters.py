"""Shared deal filter logic for Deal Finder and Email Builder."""

import re
from datetime import datetime, timezone

from config import STEAM_LABEL_MIN_PERCENT
from on_sale import _discount_pct, _price_for_currency, _sale_end_ms


_ONE_DAY_MS = 86400 * 1000


def _date_str_to_start_of_day_ms(s: str) -> int | None:
    """Parse YYYY-MM-DD to start-of-day (midnight) UTC timestamp in ms, or None if invalid."""
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = datetime(y, mo, d, 0, 0, 0, 0, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, OSError):
        return None


def _date_str_to_end_of_day_ms(s: str) -> int | None:
    """Parse YYYY-MM-DD to end-of-day UTC timestamp in ms, or None if invalid."""
    start = _date_str_to_start_of_day_ms(s)
    if start is None:
        return None
    return start + _ONE_DAY_MS - 1


def parse_sale_end_value(value_str: str) -> tuple[str, int | None, int | None]:
    """
    Parse sale end filter value. Returns (mode, a, b) where:
    - mode "op": a = single date (end-of-day ms), b = None. Use with operator.
    - mode "range": a = min ms, b = max ms (both end-of-day).
    - mode "": no filter (a=b=None).
    """
    s = (value_str or "").strip()
    if not s:
        return "", None, None
    # Range: 2026-02-01..2026-02-28 or 2026-02-01 to 2026-02-28 (sale end in [min day, max day])
    range_match = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(?:\.\.|to)\s*(\d{4}-\d{2}-\d{2})$", s, re.I)
    if range_match:
        lo = _date_str_to_start_of_day_ms(range_match.group(1))
        hi = _date_str_to_end_of_day_ms(range_match.group(2))
        if lo is not None and hi is not None and lo <= hi:
            return "range", lo, hi
        return "", None, None
    # Operator + date: <2026-03-01, >=2026-02-15
    op_match = re.match(r"^(>=?|<=?|==?|!=)\s*(\d{4}-\d{2}-\d{2})$", s)
    if op_match:
        date_ms = _date_str_to_end_of_day_ms(op_match.group(2))
        if date_ms is not None:
            return "op", date_ms, None
    return "", None, None


def apply_score_filter(
    rows: list[dict],
    filter_type: str,
    score_value: str,
    label_value: str,
) -> list[dict]:
    """Filter rows by score: All, Exact %, Operator (e.g. >75), or Label."""
    if filter_type == "All" or not filter_type:
        return rows
    if filter_type == "Exact %":
        try:
            target = int(score_value.strip())
        except (ValueError, TypeError):
            return rows
        return [
            r
            for r in rows
            if r.get("steam_percent_positive") is not None
            and abs(r["steam_percent_positive"] - target) <= 1
        ]
    if filter_type == "Operator":
        s = (score_value or "").strip()
        m = re.match(r"^(>=?|<=?|==?|!=)\s*(\d+)$", s)
        if not m:
            return rows
        op, num = m.group(1), int(m.group(2))

        def ok(pct):
            if pct is None:
                return False
            if op == ">":
                return pct > num
            if op == ">=":
                return pct >= num
            if op == "<":
                return pct < num
            if op == "<=":
                return pct <= num
            if op == "==":
                return pct == num
            if op == "!=":
                return pct != num
            return False

        return [r for r in rows if ok(r.get("steam_percent_positive"))]
    if filter_type == "Label" and label_value:
        min_pct = STEAM_LABEL_MIN_PERCENT.get(label_value)
        if min_pct is None:
            return rows
        return [
            r
            for r in rows
            if r.get("steam_percent_positive") is not None
            and r["steam_percent_positive"] >= min_pct
            and (r.get("steam_review_desc") or "") == label_value
        ]
    return rows


def apply_reviews_filter(rows: list[dict], min_reviews: str) -> list[dict]:
    """Filter rows by minimum total reviews."""
    try:
        n = int((min_reviews or "").strip())
    except (ValueError, TypeError):
        return rows
    if n <= 0:
        return rows
    return [r for r in rows if (r.get("steam_total_reviews") or 0) >= n]


def apply_discount_filter(rows: list[dict], value_str: str) -> list[dict]:
    """Filter rows by discount %: operator + number (e.g. >50, >=30). Empty = no filter."""
    s = (value_str or "").strip()
    if not s:
        return rows
    m = re.match(r"^(>=?|<=?|==?|!=)\s*(\d+)$", s)
    if not m:
        return rows
    op, num = m.group(1), int(m.group(2))

    def ok(row):
        pct = _discount_pct(row)
        if pct is None:
            return False
        if op == ">":
            return pct > num
        if op == ">=":
            return pct >= num
        if op == "<":
            return pct < num
        if op == "<=":
            return pct <= num
        if op == "==":
            return pct == num
        if op == "!=":
            return pct != num
        return False

    return [r for r in rows if ok(r)]


def apply_price_filter(rows: list[dict], value_str: str, currency: str = "USD") -> list[dict]:
    """Filter rows by current price (discount or original) in currency. Operator + number (e.g. <6, <=10). Empty = no filter."""
    s = (value_str or "").strip()
    if not s:
        return rows
    m = re.match(r"^(>=?|<=?|==?|!=)\s*(\d+(?:\.\d+)?)$", s)
    if not m:
        return rows
    op, num = m.group(1), float(m.group(2))

    def ok(row):
        price = _price_for_currency(row, currency)
        if price is None:
            return False
        if op == ">":
            return price > num
        if op == ">=":
            return price >= num
        if op == "<":
            return price < num
        if op == "<=":
            return price <= num
        if op == "==":
            return price == num
        if op == "!=":
            return price != num
        return False

    return [r for r in rows if ok(r)]


def apply_sale_end_filter(
    rows: list[dict],
    filter_type: str,
    value_str: str,
) -> list[dict]:
    """
    Filter/sort by sale end. filter_type: All, Ending Soon, Ending Latest, By date.
    value_str used when By date: e.g. <2026-03-01 or 2026-02-01..2026-02-28.
    Rows without sale end (None) are excluded from sort and from By date; for All they stay.
    """
    if not filter_type or filter_type == "All":
        return rows
    if filter_type == "Ending Soon":
        return sorted(rows, key=lambda r: (_sale_end_ms(r) is None, _sale_end_ms(r) or 0))
    if filter_type == "Ending Latest":
        return sorted(rows, key=lambda r: (_sale_end_ms(r) is None, -(_sale_end_ms(r) or 0)))
    if filter_type == "By date":
        mode, a, b = parse_sale_end_value(value_str)
        if mode == "":
            return rows
        if mode == "op":
            op_match = re.match(
                r"^(>=?|<=?|==?|!=)\s*(\d{4}-\d{2}-\d{2})$", (value_str or "").strip()
            )
            op = op_match.group(1) if op_match else "=="
            start_ms = (
                _date_str_to_start_of_day_ms(op_match.group(2)) if op_match else None
            )
            if start_ms is None:
                return rows
            end_ms = start_ms + _ONE_DAY_MS - 1
            next_day_ms = start_ms + _ONE_DAY_MS

            def ok(row):
                ms = _sale_end_ms(row)
                if ms is None:
                    return False
                if op == "<":
                    return ms < start_ms
                if op == "<=":
                    return ms <= end_ms
                if op == ">":
                    return ms >= next_day_ms
                if op == ">=":
                    return ms >= start_ms
                if op == "==":
                    return start_ms <= ms <= end_ms
                if op == "!=":
                    return not (start_ms <= ms <= end_ms)
                return False

            return [r for r in rows if ok(r)]
        if mode == "range":

            def ok(row):
                ms = _sale_end_ms(row)
                if ms is None:
                    return False
                return a <= ms <= b

            return [r for r in rows if ok(r)]
    return rows


def apply_deal_filters(
    rows: list[dict],
    *,
    score_type: str = "All",
    score_value: str = "",
    label_value: str = "",
    min_reviews: str = "",
    discount_value: str = "",
    price_value: str = "",
    currency: str = "USD",
    sale_end_type: str = "All",
    sale_end_value: str = "",
) -> list[dict]:
    """
    Apply all deal filters in sequence. Used by Deal Finder and Email Builder.
    """
    rows = apply_score_filter(rows, score_type, score_value, label_value)
    rows = apply_reviews_filter(rows, min_reviews)
    rows = apply_discount_filter(rows, discount_value)
    rows = apply_price_filter(rows, price_value, currency)
    rows = apply_sale_end_filter(rows, sale_end_type, sale_end_value)
    return rows


# Expose for release-date filter in main (same date parsing)
date_str_to_start_of_day_ms = _date_str_to_start_of_day_ms
ONE_DAY_MS = _ONE_DAY_MS
