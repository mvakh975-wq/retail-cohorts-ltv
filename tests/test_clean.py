import pandas as pd

from src.clean import clean, to_orders


def raw(rows):
    cols = [
        "Invoice",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "Price",
        "Customer ID",
        "Country",
    ]
    df = pd.DataFrame(rows, columns=cols)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Customer ID"] = df["Customer ID"].astype("Int64")
    return df


ROWS = [
    ("1001", "85048", "LIGHTS", 2, "2010-01-05 10:00", 5.0, 1, "United Kingdom"),
    ("1001", "85048", "LIGHTS", 2, "2010-01-05 10:00", 5.0, 1, "United Kingdom"),  # дубль
    ("1001", "POST", "POSTAGE", 1, "2010-01-05 10:00", 18.0, 1, "United Kingdom"),  # доставка
    ("1001", "79323P", "CHERRY", 1, "2010-01-05 10:00", 3.0, 1, "United Kingdom"),
    ("1002", "85048", "LIGHTS", 1, "2010-01-06 10:00", 5.0, None, "France"),  # нет клиента
    ("1003", "22111", "FREE", 4, "2010-02-01 10:00", 0.0, 2, "France"),  # нулевая цена
    ("C1004", "85048", "LIGHTS", -1, "2010-02-02 10:00", 5.0, 1, "United Kingdom"),  # возврат
    ("A1005", "B", "Adjust bad debt", 1, "2010-02-03 10:00", -100.0, None, "United Kingdom"),
]


def test_clean_drops_and_reports():
    lines, report = clean(raw(ROWS))
    assert report == {
        "без клиента": 2,
        "полные дубли": 1,
        "сервисные коды": 1,
        "цена ≤ 0": 1,
    }
    assert len(lines) == 3
    assert lines["revenue"].tolist() == [10.0, 3.0, -5.0]
    assert lines["is_return"].tolist() == [False, False, True]


def test_orders_are_invoice_level():
    orders = to_orders(clean(raw(ROWS))[0]).set_index("invoice")
    assert orders.loc["1001", "revenue"] == 13.0
    assert bool(orders.loc["C1004", "is_return"]) is True
    assert orders.loc["C1004", "revenue"] == -5.0
    assert list(orders.columns) == ["customer_id", "ts", "country", "is_return", "revenue"]
