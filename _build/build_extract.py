"""Build data/retailpulse.hyper from the RetailPulse-PBI parquet files and notebook outputs.

Tables (schema "Extract"):
- Extract: one row per order line, plus one row per registered customer who never ordered (customer fields only,
  Is Revenue = False), so a single datasource answers the retention question and the Segment/State filters apply to
  every view. Personal fields (names, email, phone, birth date) are left out on purpose.
- Forecast, Forecast 2026, Levers: the forecast and lever tables from analysis/output (notebooks 03 and 04).
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
OUTPUTS = Path(os.environ.get("RETAILPULSE_OUTPUTS", r"D:\Wolf\PBI\RetailPulse-PBI\analysis\output"))
OUT = ROOT / "data" / "retailpulse.hyper"


def load(source: Path) -> pd.DataFrame:
    lines = pd.read_parquet(source / "lines.parquet")
    products = pd.read_parquet(source / "products.parquet")[["product_id", "product_name", "supplier"]]
    customers = pd.read_parquet(source / "customers.parquet")[
        ["customer_id", "join_date", "city", "state", "country", "segment", "customer_type", "lifetime_orders", "first_order"]]
    df = lines.merge(products, on="product_id", how="left").merge(customers, on="customer_id", how="left")
    never = customers[customers["customer_type"] == "No Purchase"].copy()      # customer spine: never-ordered customers
    never["is_revenue"] = False
    df = pd.concat([df, never], ignore_index=True)
    df["is_revenue"] = df["is_revenue"].astype(bool)
    df = df[["order_item_id", "order_id", "order_date", "order_month", "customer_id", "order_status", "payment_method",
             "product_id", "product_name", "category", "subcategory", "supplier", "quantity", "unit_price",
             "item_discount_percent", "gross_amount", "net_sales", "cogs", "gross_profit", "is_revenue",
             "join_date", "city", "state", "country", "segment", "customer_type", "lifetime_orders", "first_order"]]
    df.columns = ["Order Item ID", "Order ID", "Order Date", "Order Month", "Customer ID", "Order Status",
                  "Payment Method", "Product ID", "Product Name", "Category", "Subcategory", "Supplier", "Quantity",
                  "Unit Price", "Discount %", "Gross Amount", "Net Sales", "COGS", "Gross Profit", "Is Revenue",
                  "Join Date", "City", "State", "Country", "Segment", "Customer Type", "Lifetime Orders", "First Order Date"]
    return df


def load_outputs(folder: Path, lines: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Forecast and lever tables written by the RetailPulse-PBI notebooks."""
    f = pd.read_csv(folder / "pbi_forecast.csv", parse_dates=["month"])
    f.columns = ["Scenario", "Month", "Metric", "Kind", "Actual", "P10", "P50", "P90"]
    # bridge: the forecast bands start at the last actual month, so the lines join the history
    last = f[f["Actual"].notna()].groupby(["Scenario", "Metric"])["Month"].transform("max")
    at_last = f["Actual"].notna() & (f["Month"] == last.reindex(f.index))
    for c in ("P10", "P50", "P90"):
        f.loc[at_last, c] = f.loc[at_last, "Actual"]
    f26 = pd.read_csv(folder / "pbi_forecast_2026.csv", encoding="utf-8")
    f26.columns = ["Scenario", "Metric", "P10", "P50", "P90"]
    # 2024 (last full year) benchmarks for the 2026 cards, from the same line data as the Extract table
    r24 = lines[lines["is_revenue"] & (lines["order_date"].dt.year == 2024)]
    first = lines.groupby("customer_id")["order_date"].min()
    bench = {"Gross profit 2024": r24["gross_profit"].sum(), "Revenue orders 2024": r24["order_id"].nunique(),
             "New buyers 2024": int((first.dt.year == 2024).sum())}
    extra = [{"Scenario": sc, "Metric": m, "P10": v, "P50": v, "P90": v} for sc in f26["Scenario"].unique() for m, v in bench.items()]
    f26 = pd.concat([f26, pd.DataFrame(extra)], ignore_index=True)
    lv = pd.read_csv(folder / "pbi_levers.csv")
    lv.columns = ["Lever", "Uplift Low", "Uplift High", "Confidence", "Cost", "Basis", "Uplift Mid"]
    # long form for the chart: one Series column (Actual, Forecast (median), Low case (P10), High case (P90)) and one Value
    names = {"Actual": "Actual", "P50": "Forecast (median)", "P10": "Low case (P10)", "P90": "High case (P90)"}
    long = f.melt(id_vars=["Scenario", "Month", "Metric"], value_vars=list(names), var_name="Series", value_name="Value")
    long = long[long["Value"].notna()].assign(Series=lambda d: d["Series"].map(names))
    return {"Forecast": long, "Forecast 2026": f26, "Levers": lv}


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


def rows_of(df: pd.DataFrame) -> list[list]:
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
    return rows


def write_hyper(tables: dict[str, pd.DataFrame], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, str(out), CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            for name, df in tables.items():
                table = TableDefinition(TableName("Extract", name),
                                        [TableDefinition.Column(c, sql_type(df[c])) for c in df.columns])
                conn.catalog.create_table(table)
                with Inserter(conn, table) as ins:
                    ins.add_rows(rows_of(df))
                    ins.execute()
                n = conn.execute_scalar_query(f"SELECT COUNT(*) FROM {table.table_name}")
                print(f"  {name}: {n} rows")
            net = conn.execute_scalar_query('SELECT SUM("Net Sales") FROM "Extract"."Extract" WHERE "Is Revenue"')
    print(f"wrote {out} revenue_net_sales={net:,.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    a = ap.parse_args()
    data = load(Path(a.source))
    assert len(data) == 1500 + 80, len(data)          # 1,500 order lines + 80 never-ordered customers
    write_hyper({"Extract": data, **load_outputs(OUTPUTS, pd.read_parquet(Path(a.source) / "lines.parquet"))}, OUT)
