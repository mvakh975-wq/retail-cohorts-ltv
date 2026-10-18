"""Месячные когорты клиентов: retention, LTV и сравнение сегментов.

Когорта — месяц первой покупки (возвраты покупкой не считаются). Активность — покупка в месяце.
LTV — накопленная чистая выручка (покупки минус возвраты) на клиента когорты.
В расчёт идут только полные месяцы данных. Первые LOOKBACK месяцев — окно истории:
клиент, впервые купивший в нём, мог быть давним клиентом, который просто редко заказывает.
"""

import pandas as pd

UK = "United Kingdom"
LOOKBACK = 12


def full_months(first_ts: pd.Timestamp, last_ts: pd.Timestamp) -> list[pd.Period]:
    """Месяцы, целиком покрытые данными (первый месяц засчитывается с 1-го числа)."""
    first = first_ts.to_period("M")
    if first_ts.day > 1:
        first += 1
    last = last_ts.to_period("M")
    if last_ts < (last + 1).start_time - pd.Timedelta(days=1):
        last -= 1
    return list(pd.period_range(first, last, freq="M"))


def assign_cohorts(orders: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()
    df["month"] = df["ts"].dt.to_period("M")
    first_purchase = df[~df["is_return"]].groupby("customer_id")["ts"].min()
    first_return = df[df["is_return"]].groupby("customer_id")["ts"].min()
    # возврат раньше первой покупки: клиент покупал до начала данных — новым он не считается
    returned_first = first_return[first_return < first_purchase.reindex(first_return.index)]
    first_purchase = first_purchase.drop(returned_first.index)
    df = df[df["customer_id"].isin(first_purchase.index)].copy()
    df["cohort"] = df["customer_id"].map(first_purchase).dt.to_period("M")
    df["month_offset"] = (df["month"] - df["cohort"]).map(lambda x: x.n)
    first_country = df.sort_values(["ts", "invoice"]).groupby("customer_id")["country"].first()
    is_uk = df["customer_id"].map(first_country).eq(UK)
    df["region"] = is_uk.map({True: "Великобритания", False: "Другие страны"})
    return df


def _cohort_grid(df: pd.DataFrame, months: list[pd.Period], lookback: int) -> pd.DataFrame:
    """Пары (когорта, месяц жизни) для когорт после окна истории."""
    cohort_months = months[lookback:]
    sizes = (
        df[df["cohort"].isin(cohort_months)]
        .groupby("cohort")["customer_id"]
        .nunique()
        .rename("cohort_size")
    )
    last = months[-1]
    rows = [(c, size, k) for c, size in sizes.items() for k in range((last - c).n + 1)]
    return pd.DataFrame(rows, columns=["cohort", "cohort_size", "month_offset"])


def retention_matrix(
    df: pd.DataFrame, months: list[pd.Period], lookback: int = LOOKBACK
) -> pd.DataFrame:
    purchases = df[~df["is_return"] & df["month"].isin(months)]
    active = purchases.groupby(["cohort", "month_offset"])["customer_id"].nunique().rename("active")
    grid = _cohort_grid(df, months, lookback).join(active, on=["cohort", "month_offset"])
    grid["active"] = grid["active"].fillna(0).astype(int)
    grid["retention"] = grid["active"] / grid["cohort_size"]
    return grid


def ltv_curve(df: pd.DataFrame, months: list[pd.Period], lookback: int = LOOKBACK) -> pd.DataFrame:
    revenue = (
        df[df["month"].isin(months)]
        .groupby(["cohort", "month_offset"])["revenue"]
        .sum()
        .rename("revenue")
    )
    grid = _cohort_grid(df, months, lookback).join(revenue, on=["cohort", "month_offset"])
    grid["revenue"] = grid["revenue"].fillna(0.0)
    grid["cum_revenue_per_customer"] = (
        grid.groupby("cohort")["revenue"].cumsum() / grid["cohort_size"]
    )
    return grid


def segment_summary(
    df: pd.DataFrame,
    months: list[pd.Period],
    by: str,
    retention_month: int = 3,
    ltv_month: int = 6,
    lookback: int = LOOKBACK,
) -> pd.DataFrame:
    """Размер сегмента, retention месяца N, средний заказ, LTV к месяцу M и выручка после
    первого заказа (LTV без самого первого заказа).

    Retention и LTV — только по когортам, у которых нужный месяц уже наступил.
    """
    last = months[-1]
    base = df[
        df["cohort"].isin(months[lookback:]) & df["month"].isin(months) & (df["month_offset"] >= 0)
    ]

    def eligible(k: int) -> pd.DataFrame:
        return base[base["cohort"].map(lambda c: (last - c).n >= k)]

    ret = eligible(retention_month)
    returned = ret[~ret["is_return"] & (ret["month_offset"] == retention_month)]
    ltv = eligible(ltv_month)
    purchases = base[~base["is_return"]]
    in_horizon = ltv[ltv["month_offset"] <= ltv_month]
    first_orders = (
        in_horizon[~in_horizon["is_return"]]
        .sort_values(["ts", "invoice"])
        .groupby("customer_id")
        .first()
    )
    summary = pd.DataFrame(
        {
            "customers": base.groupby(by)["customer_id"].nunique(),
            "retention": returned.groupby(by)["customer_id"].nunique()
            / ret.groupby(by)["customer_id"].nunique(),
            "avg_order": purchases.groupby(by)["revenue"].mean(),
            "ltv": in_horizon.groupby(by)["revenue"].sum()
            / ltv.groupby(by)["customer_id"].nunique(),
            "after_first": (
                in_horizon.groupby(by)["revenue"].sum() - first_orders.groupby(by)["revenue"].sum()
            )
            / ltv.groupby(by)["customer_id"].nunique(),
        }
    )
    summary["retention"] = summary["retention"].fillna(0.0)
    return summary.rename_axis("segment").reset_index()


def add_first_order_tier(df: pd.DataFrame) -> pd.DataFrame:
    """Сегмент по сумме первого заказа: выше или не выше медианы клиентов в df."""
    purchases = df[~df["is_return"]].sort_values(["ts", "invoice"])
    first = purchases.groupby("customer_id")["revenue"].first()
    tier = (first > first.median()).map({True: "Выше медианы", False: "До медианы"})
    return df.assign(first_order=df["customer_id"].map(tier))
