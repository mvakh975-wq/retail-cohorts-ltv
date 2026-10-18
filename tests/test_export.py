import pandas as pd

from scripts.export import export_all
from src.cohorts import assign_cohorts
from tests.test_cohorts import MONTHS


def test_export_writes_aggregates(tmp_path):
    rows = [
        ("1", 1, "2009-12-10", "United Kingdom", False, 50.0),
        ("2", 2, "2010-01-20", "France", False, 100.0),
        ("3", 2, "2010-02-03", "France", False, 40.0),
        ("4", 3, "2010-02-10", "United Kingdom", False, 30.0),
    ]
    df = pd.DataFrame(
        rows, columns=["invoice", "customer_id", "ts", "country", "is_return", "revenue"]
    )
    df["ts"] = pd.to_datetime(df["ts"])
    paths = export_all(assign_cohorts(df), MONTHS, tmp_path, lookback=1, horizon=1)
    assert sorted(p.name for p in paths) == [
        "ltv.csv",
        "new_customers.csv",
        "retention.csv",
        "segments.csv",
    ]
    for path in paths:
        out = pd.read_csv(path)
        assert len(out) > 0
        assert not any("customer" in c.lower() or "id" == c.lower() for c in out.columns)
    seg = pd.read_csv(tmp_path / "segments.csv")
    assert set(seg["Разрез"]) == {"Первый заказ", "Страна"}
    assert "После первого заказа, £" in seg.columns
    assert all(not c.isascii() for c in seg.columns)  # служебных английских имён не осталось
