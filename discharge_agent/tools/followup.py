from dateutil.parser import parse as dtparse


def followup_gap(discharge_date: str, appts: list) -> dict:
    d0 = dtparse(discharge_date).date()
    gaps = []
    for a in appts:
        try:
            d = dtparse(a.get("date")).date()
            gaps.append((d - d0).days)
        except Exception:
            pass
    days = min(gaps) if gaps else None
    return {
        "days_to_earliest_followup": days,
        "meets_goal": (days is not None and days <= 7),
    }
