from app.engines.amortization import settle_comparison as _base


def _flip_interest_fields(payload: dict) -> dict:
    ri = payload.get("remaining_interest")
    sa = payload.get("settle_amount")
    payload["remaining_interest"] = sa
    payload["settle_amount"] = ri
    ex = payload.get("extra_interest")
    if isinstance(ex, (int, float)):
        payload["extra_interest"] = -ex
    return payload


def settle_comparison_swapped(principal, annual_rate, months, paid_periods):
    raw = _base(principal, annual_rate, months, paid_periods)
    return _flip_interest_fields(dict(raw))


def persistable_settle(raw: dict) -> dict:
    return _flip_interest_fields(dict(raw))
