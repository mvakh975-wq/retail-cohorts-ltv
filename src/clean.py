"""Очистка Online Retail II: от строк накладных к заказам клиентов."""

import pandas as pd

# Не товары: доставка, комиссии, ручные корректировки, тестовые позиции
SERVICE_CODES = {
    "POST", "DOT", "M", "m", "C2", "C3", "D", "S", "B", "BANK CHARGES", "ADJUST", "ADJUST2",
    "AMAZONFEE", "CRUK", "TEST001", "TEST002",
}  # fmt: skip


def load(path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        dtype={"Invoice": str, "StockCode": str, "Customer ID": "Int64"},
        parse_dates=["InvoiceDate"],
    )


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Возвращает строки товаров с выручкой и отчёт, сколько строк отброшено на каждом шаге."""
    steps = {
        "без клиента": lambda d: d["Customer ID"].notna(),
        "полные дубли": lambda d: ~d.duplicated(),
        "сервисные коды": lambda d: ~d["StockCode"].isin(SERVICE_CODES),
        "цена ≤ 0": lambda d: d["Price"] > 0,
    }
    report = {}
    df = raw
    for name, keep in steps.items():
        mask = keep(df)
        report[name] = int((~mask).sum())
        df = df[mask]
    lines = pd.DataFrame(
        {
            "invoice": df["Invoice"],
            "customer_id": df["Customer ID"].astype("int64"),
            "ts": df["InvoiceDate"],
            "country": df["Country"],
            "is_return": df["Invoice"].str.startswith("C"),
            "revenue": df["Quantity"] * df["Price"],
        }
    ).reset_index(drop=True)
    return lines, report


def to_orders(lines: pd.DataFrame) -> pd.DataFrame:
    """Одна строка на накладную: заказ (выручка > 0) или возврат (выручка < 0)."""
    return (
        lines.groupby("invoice", sort=False)
        .agg(
            customer_id=("customer_id", "first"),
            ts=("ts", "min"),
            country=("country", "first"),
            is_return=("is_return", "first"),
            revenue=("revenue", "sum"),
        )
        .reset_index()
    )
