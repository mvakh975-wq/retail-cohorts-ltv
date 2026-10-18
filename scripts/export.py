"""Выгружает агрегаты когорт для DataLens: CSV с русскими заголовками, без id клиентов."""

from pathlib import Path

import pandas as pd

from src.cohorts import LOOKBACK, add_first_order_tier, ltv_curve, retention_matrix, segment_summary


def export_all(
    df: pd.DataFrame,
    months: list[pd.Period],
    out_dir: str | Path,
    lookback: int = LOOKBACK,
    horizon: int = 6,
) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cohort_months = months[lookback:]

    first_seen = (
        df[~df["is_return"]]
        .groupby("customer_id")["month"]
        .min()
        .value_counts()
        .reindex(months[1:], fill_value=0)
    )
    new_customers = pd.DataFrame(
        {
            "Месяц": [m.start_time.date() for m in first_seen.index],
            "Клиентов с первым заказом": first_seen.values,
            "Период": [
                "когорты" if m in cohort_months else "окно истории" for m in first_seen.index
            ],
        }
    )

    rm = retention_matrix(df, months, lookback)
    retention = pd.DataFrame(
        {
            "Когорта": rm["cohort"].map(lambda p: p.start_time.date()),
            "Размер когорты": rm["cohort_size"],
            "Месяц жизни": rm["month_offset"],
            "Покупали": rm["active"],
        }
    )

    lt = ltv_curve(df, months, lookback)
    ltv = pd.DataFrame(
        {
            "Когорта": lt["cohort"].map(lambda p: p.start_time.date()),
            "Размер когорты": lt["cohort_size"],
            "Месяц жизни": lt["month_offset"],
            "Выручка месяца, £": lt["revenue"].round(2),
            "Накопленная выручка когорты, £": (
                lt["cum_revenue_per_customer"] * lt["cohort_size"]
            ).round(2),
        }
    )

    new = df[df["cohort"].isin(cohort_months) & df["month"].isin(months)]
    tiered = add_first_order_tier(new)
    parts = []
    for by, title in (("first_order", "Первый заказ"), ("region", "Страна")):
        s = segment_summary(tiered, months, by=by, ltv_month=horizon, lookback=lookback)
        s.insert(0, "dimension", title)
        parts.append(s)
    segments = (
        pd.concat(parts)
        .rename(
            columns={
                "dimension": "Разрез",
                "segment": "Сегмент",
                "customers": "Клиентов",
                "retention": "Retention 3-го месяца",
                "avg_order": "Средний заказ, £",
                "ltv": f"LTV {horizon} мес., £",
                "after_first": "После первого заказа, £",
            }
        )
        .round(4)
    )

    paths = []
    for name, table in (
        ("new_customers", new_customers),
        ("retention", retention),
        ("ltv", ltv),
        ("segments", segments),
    ):
        path = out_dir / f"{name}.csv"
        table.to_csv(path, index=False)
        paths.append(path)
    return paths
