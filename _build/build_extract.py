"""Build data/retailpulse.hyper (one denormalised Sales table) from the RetailPulse-PBI parquet files.

Personal fields (names, email, phone, birth date) are left out on purpose.
Usage: .venv\\Scripts\\python _build\\build_extract.py [--source <folder with parquet files>]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from tableauhyperapi import (Connection, CreateMode, HyperProcess, Inserter, SqlType, TableDefinition,
                             TableName, Telemetry)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = os.environ.get("RETAILPULSE_PARQUET", r"D:\Wolf\PBI\RetailPulse-PBI\analysis\data")
OUT = ROOT / "data" / "retailpulse.hyper"


def load(source: Path) -> pd.DataFrame:
    lines = pd.read_parquet(source / "lines.parquet")
    products = pd.read_parquet(source / "products.parquet")[["product_id", "product_name", "supplier"]]
    customers = pd.read_parquet(source / "customers.parquet")[
        ["customer_id", "city", "state", "country", "segment", "customer_type"]]
    df = lines.merge(products, on="product_id", how="left").merge(customers, on="customer_id", how="left")
    df = df[["order_item_id", "order_id", "order_date", "order_month", "customer_id", "order_status", "payment_method",
             "product_id", "product_name", "category", "subcategory", "supplier", "quantity", "unit_price",
             "item_discount_percent", "gross_amount", "net_sales", "cogs", "gross_profit", "is_revenue",
             "city", "state", "country", "segment", "customer_type"]]
    df.columns = ["Order Item ID", "Order ID", "Order Date", "Order Month", "Customer ID", "Order Status",
                  "Payment Method", "Product ID", "Product Name", "Category", "Subcategory", "Supplier", "Quantity",
                  "Unit Price", "Discount %", "Gross Amount", "Net Sales", "COGS", "Gross Profit", "Is Revenue",
                  "City", "State", "Country", "Segment", "Customer Type"]
    return df


def sql_type(s: pd.Series) -> SqlType:
    if pd.api.types.is_bool_dtype(s):
        return SqlType.bool()
    if pd.api.types.is_integer_dtype(s):
        return SqlType.big_int()
    if pd.api.types.is_float_dtype(s):
        return SqlType.double()
    if pd.api.types.is_datetime64_any_dtype(s):
        return SqlType.date()
    return SqlType.text()


def write_hyper(df: pd.DataFrame, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    table = TableDefinition(TableName("Extract", "Extract"),
                            [TableDefinition.Column(c, sql_type(df[c])) for c in df.columns])
    rows = []
    for rec in df.itertuples(index=False):
        row = []
        for c, v in zip(df.columns, rec):
            if pd.isna(v):
                row.append(None)
            elif pd.api.types.is_datetime64_any_dtype(df[c]):
                row.append(v.date())
            elif isinstance(v, (bool,)) or pd.api.types.is_bool_dtype(df[c]):
                row.append(bool(v))
            elif pd.api.types.is_integer_dtype(df[c]):
                row.append(int(v))
            elif pd.api.types.is_float_dtype(df[c]):
                row.append(float(v))
            else:
                row.append(str(v))
        rows.append(row)
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, str(out), CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(table)
            with Inserter(conn, table) as ins:
                ins.add_rows(rows)
                ins.execute()
            n = conn.execute_scalar_query(f"SELECT COUNT(*) FROM {table.table_name}")
            net = conn.execute_scalar_query(f'SELECT SUM("Net Sales") FROM {table.table_name} WHERE "Is Revenue"')
    print(f"wrote {out} rows={n} revenue_net_sales={net:,.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    a = ap.parse_args()
    data = load(Path(a.source))
    assert len(data) == 1500, len(data)
    write_hyper(data, OUT)
