import pandas as pd
import pytest

from src.cohorts import assign_cohorts, full_months, ltv_curve, retention_matrix, segment_summary

M = pd.Period
MONTHS = [M("2009-12", "M"), M("2010-01", "M"), M("2010-02", "M"), M("2010-03", "M")]


@pytest.fixture
def orders():
    rows = [
        # invoice, customer, ts, country, is_return, revenue
        ("1", 1, "2009-12-10", "United Kingdom", False, 50.0),  # первый заказ до окна когорт
        ("2", 1, "2010-01-15", "United Kingdom", False, 60.0),
        ("3", 2, "2010-01-20", "France", False, 100.0),
        ("4", 2, "2010-02-03", "France", False, 40.0),
        ("C5", 2, "2010-03-04", "France", True, -10.0),  # возврат: выручка есть, активности нет
        ("6", 3, "2010-02-10", "United Kingdom", False, 30.0),
        ("7", 3, "2010-03-10", "United Kingdom", False, 30.0),
        ("8", 4, "2010-04-02", "Germany", False, 80.0),  # неполный месяц
    ]
    df = pd.DataFrame(
        rows, columns=["invoice", "customer_id", "ts", "country", "is_return", "revenue"]
    )
    df["ts"] = pd.to_datetime(df["ts"])
    return assign_cohorts(df)


def test_full_months_drop_partial_last_month():
    months = full_months(pd.Timestamp("2009-12-01 07:45"), pd.Timestamp("2011-12-09 12:50"))
    assert months[0] == M("2009-12", "M")
    assert months[-1] == M("2011-11", "M")
    assert len(months) == 24


def test_cohort_is_first_purchase_month(orders):
    first = orders.groupby("customer_id")["cohort"].first()
    assert first.to_dict() == {
        1: M("2009-12", "M"),
        2: M("2010-01", "M"),
        3: M("2010-02", "M"),
        4: M("2010-04", "M"),
    }


def test_retention_counts_purchases_not_returns(orders):
    rm = retention_matrix(orders, MONTHS, lookback=1)
    cols = ["cohort", "cohort_size", "month_offset", "active"]
    got = [tuple(r) for r in rm[cols].itertuples(False)]
    # клиент 1 — в когорте декабря 2009 (вне окна), клиент 4 — в неполном месяце;
    # возврат клиента 2 в марте не считается активностью
    assert got == [
        (M("2010-01", "M"), 1, 0, 1),
        (M("2010-01", "M"), 1, 1, 1),
        (M("2010-01", "M"), 1, 2, 0),
        (M("2010-02", "M"), 1, 0, 1),
        (M("2010-02", "M"), 1, 1, 1),
    ]


def test_ltv_is_cumulative_net_revenue_per_customer(orders):
    ltv = ltv_curve(orders, MONTHS, lookback=1)
    assert ltv["cum_revenue_per_customer"].tolist() == pytest.approx([100, 140, 130, 30, 60])


def test_segment_summary(orders):
    s = segment_summary(orders, MONTHS, by="region", retention_month=1, ltv_month=1, lookback=1)
    s = s.set_index("segment")
    assert s.loc["Великобритания", "customers"] == 1
    assert s.loc["Другие страны", "ltv"] == pytest.approx(140)
    assert s.loc["Великобритания", "retention"] == pytest.approx(1.0)
    # клиент 3: первый заказ 30, за месяцы 0–1 ещё 30 → после первого заказа 30
    assert s.loc["Великобритания", "after_first"] == pytest.approx(30)
    assert s.loc["Другие страны", "after_first"] == pytest.approx(40)


def test_first_order_tier(orders):
    from src.cohorts import add_first_order_tier

    tiers = add_first_order_tier(orders).groupby("customer_id")["first_order"].first()
    # первые заказы: 50, 100, 30, 80 → медиана 65
    assert tiers.to_dict() == {
        1: "До медианы",
        2: "Выше медианы",
        3: "До медианы",
        4: "Выше медианы",
    }


def test_first_order_tier_is_deterministic_on_ties():
    from src.cohorts import add_first_order_tier

    rows = [
        ("9", 7, "2010-02-01 10:00", "United Kingdom", False, 500.0),
        ("8", 7, "2010-02-01 10:00", "United Kingdom", False, 10.0),
        ("5", 8, "2010-02-02 10:00", "United Kingdom", False, 100.0),
    ]
    df = pd.DataFrame(
        rows, columns=["invoice", "customer_id", "ts", "country", "is_return", "revenue"]
    )
    df["ts"] = pd.to_datetime(df["ts"])
    for order in (df, df.iloc[::-1]):
        tiers = add_first_order_tier(order).groupby("customer_id")["first_order"].first()
        # при равном времени первым считается заказ с меньшим номером накладной: «8» на 10
        assert tiers.to_dict() == {7: "До медианы", 8: "Выше медианы"}


def test_customer_with_return_before_first_purchase_is_not_new():
    rows = [
        ("C1", 9, "2010-01-05", "United Kingdom", True, -20.0),  # возврат раньше покупки
        ("2", 9, "2010-02-05", "United Kingdom", False, 100.0),
        ("3", 10, "2010-02-06", "United Kingdom", False, 50.0),
    ]
    df = pd.DataFrame(
        rows, columns=["invoice", "customer_id", "ts", "country", "is_return", "revenue"]
    )
    df["ts"] = pd.to_datetime(df["ts"])
    # возврат до первой покупки значит, что клиент покупал до начала данных
    assert assign_cohorts(df)["customer_id"].unique().tolist() == [10]


def test_segment_ltv_ignores_rows_before_cohort(orders):
    extra = orders.iloc[[0]].copy()
    extra["month_offset"] = -1
    extra["region"] = "Великобритания"
    extra["cohort"] = M("2010-02", "M")
    extra["customer_id"] = 3
    extra["revenue"] = -1000.0
    s = segment_summary(
        pd.concat([orders, extra]), MONTHS, by="region", retention_month=1, ltv_month=1, lookback=1
    ).set_index("segment")
    assert s.loc["Великобритания", "ltv"] == pytest.approx(60)
