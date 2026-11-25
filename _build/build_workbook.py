"""Generate RetailPulse-Tableau.twb from data/retailpulse.hyper with cwtwb (no Tableau Desktop needed).

v2 (Nov 2026, scored with D:\\Wolf\\PBI\\_knowledge\\dashboard_scorecard.md): four dashboards that mirror the
RetailPulse-PBI pages (1 Retention, 2 Profit, 3 KPI, 4 Forecast), action titles from string calculations that follow
the filters, KPI cards with ▲▼ change lines in AA colours, Indian units, linked Segment/State filters, a filter
action, captions, a footer, navigation buttons and phone layouts.

Usage: .venv\\Scripts\\python _build\\build_workbook.py   (close Tableau first)
"""
from __future__ import annotations

import csv
import os
from datetime import date
from pathlib import Path

import cwtwb
import pandas as pd
from cwtwb.mcp import tools_workbook as T

import twb_kit as k
from twb_kit import (BAD, BAND, CANVAS, CORAL, GOOD, INK, NAVY, NEUTRAL, SLATE, VIOLET, WARN, block, card_zone, change, inr, num,
                     panel, pct, static_title, step, ws)

ROOT = Path(__file__).resolve().parents[1]
HYPER = ROOT / "data" / "retailpulse.hyper"
OUT = ROOT / "RetailPulse-Tableau.twb"
LAYOUT_DIR = ROOT / "_build" / "layouts"
LAYOUT_DIR.mkdir(exist_ok=True)
EMPTY = Path(cwtwb.__file__).parent / "references" / "empty_template.twb"
SRC = Path(os.environ.get("RETAILPULSE_PARQUET", r"D:\Wolf\PBI\RetailPulse-PBI\analysis\data"))
OUTPUTS = Path(os.environ.get("RETAILPULSE_OUTPUTS", r"D:\Wolf\PBI\RetailPulse-PBI\analysis\output"))

# domains used to unroll per-member comparisons (so titles stay correct under any filter)
lines = pd.read_parquet(SRC / "lines.parquet")
CATS = sorted(lines["category"].unique())
SEGS = sorted(pd.read_parquet(SRC / "customers.parquet")["segment"].unique())
STATES = sorted(pd.read_parquet(SRC / "customers.parquet")["state"].unique())
YEARS = sorted(int(y) for y in lines["order_date"].dt.year.unique())
DISC = sorted(int(d) for d in lines["item_discount_percent"].unique())
PERIOD = f"{lines['order_date'].min():%b %Y} – {lines['order_date'].max():%b %Y}"

k.hyper_unlocked(HYPER)
b = k.Book(EMPTY, "RetailPulse")
step("hyper", T.set_hyper_connection(str(HYPER), table_name="Extract"))
T.get_editor()._datasource.set("caption", "RetailPulse Sales")   # the blank template would say Superstore
C = b.calc

# ================================================================ main datasource: row-level helpers
# Segment and State choices are global parameters: one control drives every sheet on pages 1-3, and the choice
# carries across pages (a categorical filter shared by filter group did not apply in Tableau Desktop 2026.3).
step("param", T.add_parameter("Segment Choice", "string", "All", domain_type="list", allowed_values=["All"] + SEGS))
step("param", T.add_parameter("State Choice", "string", "All", domain_type="list", allowed_values=["All"] + STATES))
C("In Segment", "[Segment Choice] = 'All' OR [Segment] = [Segment Choice]", "boolean")
C("In State", "[State Choice] = 'All' OR [State] = [State Choice]", "boolean")
C("RNS", "IF [Is Revenue] THEN [Net Sales] END")
C("RGP", "IF [Is Revenue] THEN [Gross Profit] END")
C("Max Date", "{FIXED : MAX([Order Date])}", "date")
C("Is CY", "YEAR([Order Date]) = YEAR([Max Date])", "boolean")
C("Is PY", "YEAR([Order Date]) = YEAR([Max Date]) - 1 AND [Order Date] <= DATEADD('year', -1, [Max Date])", "boolean")
C("Like for Like Months", "MONTH([Order Date]) <= MONTH([Max Date])", "boolean")
C("First Order Year", "STR(YEAR([First Order Date]))", "string")
C("First Order Qtr", "'Q' + STR(DATEPART('quarter', [First Order Date]))", "string")
C("Order Frequency", "IF [Lifetime Orders] >= 4 THEN '4+ orders' ELSEIF [Lifetime Orders] = 1 THEN '1 order' "
  "ELSE STR([Lifetime Orders]) + ' orders' END", "string")
C("Item Discount", "[Discount %]", "integer", role="dimension", field_type="ordinal", fmt='n0"%"')

# ---------------------------------------------------------------- measures
C("Gross Profit ₹ L", "SUM([RGP]) / 100000", fmt='n"₹"#,##0.0" L"')
C("Gross Margin %", "SUM([RGP]) / SUM([RNS])", fmt="p0.0%")
C("Revenue Orders", "COUNTD(IF [Is Revenue] THEN [Order ID] END)", "integer")
C("Active Customers", "COUNTD(IF [Is Revenue] THEN [Customer ID] END)", "integer")
C("PPAC", "SUM([RGP]) / [Active Customers]", fmt='n"₹"#,##0')
C("Profit per Customer ₹ L", "[PPAC] / 100000", fmt='n"₹"#,##0.00" L"')
C("Orders per Customer", "[Revenue Orders] / [Active Customers]", fmt="n0.00")
C("AOV", "SUM([RNS]) / [Revenue Orders]", fmt='n"₹"#,##0')
C("Registered", "COUNTD([Customer ID])", "integer")
C("Buyers", "COUNTD(IF [Customer Type] <> 'No Purchase' THEN [Customer ID] END)", "integer")
C("Recurring Customers", "COUNTD(IF [Customer Type] = 'Recurring' THEN [Customer ID] END)", "integer")
C("One-Time Customers", "COUNTD(IF [Customer Type] = 'One-Time' THEN [Customer ID] END)", "integer")
C("Never Ordered", "COUNTD(IF [Customer Type] = 'No Purchase' THEN [Customer ID] END)", "integer")
C("Repeat Rate", "[Recurring Customers] / [Buyers]", fmt="p0.0%")
C("Recurring GP", "SUM(IF [Customer Type] = 'Recurring' THEN [RGP] END)")
C("Recurring Profit Share", "[Recurring GP] / SUM([RGP])", fmt="p0.0%")
C("PP Recurring", "[Recurring GP] / COUNTD(IF [Customer Type] = 'Recurring' AND [Is Revenue] THEN [Customer ID] END)")
C("PP One-Time", "SUM(IF [Customer Type] = 'One-Time' THEN [RGP] END) / "
  "COUNTD(IF [Customer Type] = 'One-Time' AND [Is Revenue] THEN [Customer ID] END)")
C("Value Multiplier", "[PP Recurring] / [PP One-Time]")
C("Orders per Buyer", "COUNTD([Order ID]) / [Buyers]")
C("Buyers 3plus", "COUNTD(IF [Lifetime Orders] >= 3 THEN [Customer ID] END) / [Buyers]")
C("New Buyers", "COUNTD([Customer ID])", "integer")
# current year (to the last order date) vs the same months last year
for p, flag in (("CY", "[Is CY]"), ("PY", "[Is PY]")):
    C(f"GP {p}", f"SUM(IF {flag} THEN [RGP] END)")
    C(f"NS {p}", f"SUM(IF {flag} THEN [RNS] END)")
    C(f"Margin {p}", f"[GP {p}] / [NS {p}]")
    C(f"Orders {p}", f"COUNTD(IF {flag} AND [Is Revenue] THEN [Order ID] END)", "integer")
    C(f"Active {p}", f"COUNTD(IF {flag} AND [Is Revenue] THEN [Customer ID] END)", "integer")
    C(f"AOV {p}", f"[NS {p}] / [Orders {p}]")
    C(f"OPC {p}", f"[Orders {p}] / [Active {p}]")
    C(f"PPAC {p}", f"[GP {p}] / [Active {p}]")
C("PPAC Target", "[PPAC PY] * 1.05")
# unrolled members: titles compare members without LOD, so every filter still applies
q = lambda s: "'" + s.replace("'", "\\'") + "'"
for c in CATS:
    C(f"GP {c}", f"SUM(IF [Category] = {q(c)} THEN [RGP] END)")
    C(f"Margin {c}", f"[GP {c}] / SUM(IF [Category] = {q(c)} THEN [RNS] END)")
for s in SEGS:
    C(f"Repeat {s}", f"COUNTD(IF [Segment] = {q(s)} AND [Customer Type] = 'Recurring' THEN [Customer ID] END) / "
                     f"COUNTD(IF [Segment] = {q(s)} AND [Customer Type] <> 'No Purchase' THEN [Customer ID] END)")
    C(f"PPAC CY {s}", f"SUM(IF [Segment] = {q(s)} AND [Is CY] THEN [RGP] END) / "
                      f"COUNTD(IF [Segment] = {q(s)} AND [Is CY] AND [Is Revenue] THEN [Customer ID] END)")
for y in YEARS:
    C(f"New Buyers {y}", f"COUNTD(IF YEAR([First Order Date]) = {y} THEN [Customer ID] END)", "integer")
    C(f"Recurring Share {y}", f"SUM(IF YEAR([Order Date]) = {y} AND [Customer Type] = 'Recurring' THEN [RGP] END) / "
                              f"SUM(IF YEAR([Order Date]) = {y} THEN [RGP] END)")
    C(f"PPAC LFL {y}", f"SUM(IF YEAR([Order Date]) = {y} AND [Like for Like Months] THEN [RGP] END) / "
                       f"COUNTD(IF YEAR([Order Date]) = {y} AND [Like for Like Months] AND [Is Revenue] THEN [Customer ID] END)")
for d in DISC:
    C(f"Margin Disc {d}", f"SUM(IF [Discount %] = {d} THEN [RGP] END) / SUM(IF [Discount %] = {d} THEN [RNS] END)")


def pick(members, field, best=True, ret="name"):
    """Nested IF that returns the member (or its value) with the highest/lowest field."""
    op = ">=" if best else "<="
    parts = []
    for m in members:
        cond = " AND ".join(f"([{field.format(m)}] {op} [{field.format(o)}] OR ISNULL([{field.format(o)}]))" for o in members if o != m)
        out = q(m) if ret == "name" else f"[{field.format(m)}]"
        parts.append(f"NOT ISNULL([{field.format(m)}]) AND {cond} THEN {out}")
    return "IF " + " ELSEIF ".join(parts) + " END"


C("Top Category", pick(CATS, "GP {}"), "string")
C("Top Category GP", pick(CATS, "GP {}", ret="value"))
C("Low Category", pick(CATS, "GP {}", best=False), "string")
C("Low Category GP", pick(CATS, "GP {}", best=False, ret="value"))
C("High Margin Category", pick(CATS, "Margin {}"), "string")
C("High Margin", pick(CATS, "Margin {}", ret="value"))
C("Low Margin Category", pick(CATS, "Margin {}", best=False), "string")
C("Low Margin", pick(CATS, "Margin {}", best=False, ret="value"))

# ---------------------------------------------------------------- display text (cards and titles)
L2 = lambda x: f'"₹" + STR(ROUND(({x}) / 100000, 2)) + " L"'
S = lambda name, formula: C(name, formula, "string")
S("V Buyers", "STR([Buyers])")
S("X Buyers", '"of " + STR([Registered]) + " registered (" + ' + pct("[Buyers] / [Registered]") + ' + ")"')
S("V Repeat", pct("[Repeat Rate]", 1))
S("X Repeat", 'STR([Recurring Customers]) + " vs " + STR([One-Time Customers]) + " one-time"')
S("V RecShare", pct("[Recurring Profit Share]", 1))
S("X RecShare", inr("[Recurring GP]") + ' + " of " + ' + f"({inr('SUM([RGP])')})")
S("V Multiplier", num("[Value Multiplier]", 1) + ' + "x"')
S("X Multiplier", L2("[PP Recurring]") + ' + " vs " + ' + L2("[PP One-Time]"))
S("V OPB", num("[Orders per Buyer]", 2))
S("X OPB", pct("[Buyers 3plus]") + ' + " ordered 3+ times"')
S("V Never", "STR([Never Ordered])")
S("X Never", pct("[Never Ordered] / [Registered]") + ' + " of registered"')
for key, cur, prev, kind in (("GP", "[GP CY]", "[GP PY]", "inr"), ("NS", "[NS CY]", "[NS PY]", "inr"),
                             ("Margin", "[Margin CY]", "[Margin PY]", "pp"), ("AOV", "[AOV CY]", "[AOV PY]", "inr"),
                             ("PPAC", "[PPAC CY]", "[PPAC PY]", "inr"), ("OPC", "[OPC CY]", "[OPC PY]", "num"),
                             ("Active", "[Active CY]", "[Active PY]", "int")):
    S(f"V {key}", {"inr": inr(cur), "pp": pct(cur, 1), "num": num(cur, 2), "int": f"STR({cur})"}[kind])
    good, bad = change(cur, prev, pp=(kind == "pp"))
    S(f"U {key}", good)
    S(f"D {key}", bad)
S("V Target", inr("[PPAC Target]"))
S("U Target", 'IF [PPAC CY] >= [PPAC Target] THEN STR(ROUND(([PPAC CY] - [PPAC Target]) / [PPAC Target] * 100, 1)) + "% ahead of target" END')
S("D Target", 'IF [PPAC CY] < [PPAC Target] THEN STR(ROUND(([PPAC Target] - [PPAC CY]) / [PPAC Target] * 100, 1)) + "% behind target" END')
S("X Top", inr("[Top Category GP]") + ' + " · " + ' + pct("[Top Category GP] / SUM([RGP])") + ' + " of profit"')
S("X Low", inr("[Low Category GP]") + ' + " · " + ' + pct("[Low Category GP] / SUM([RGP])") + ' + " of profit"')
CYL = 'STR(YEAR(MAX([Max Date])))'
MON = "LEFT(DATENAME('month', MAX([Max Date])), 3)"
S("Title Retention", pct("[Repeat Rate]") + ' + " of buyers came back, and they earn " + ' + pct("[Recurring Profit Share]") + ' + " of gross profit"')
S("Title New Buyers", f'"New buyers " + IIF([New Buyers {YEARS[-1]}] < [New Buyers {YEARS[0]}], "fell ", "rose ") + ' + ' + "→" + '.join(f"STR([New Buyers {y}])" for y in YEARS))
S("Title Frequency", pct("[One-Time Customers] / [Buyers]") + ' + " ordered once; " + ' + pct("[Buyers 3plus]") + ' + " ordered 3+ times"')
S("Title Value", '"Recurring earn " + ' + num("[Value Multiplier]", 1) + ' + "x: " + ' + L2("[PP Recurring]") + ' + " vs " + '
  + L2("[PP One-Time]"))
S("Title Profit Type", f'"Recurring share: " + {pct(f"[Recurring Share {YEARS[0]}]")} + " ({YEARS[0]}) → " + '
  f'{pct(f"[Recurring Share {YEARS[-1]}]")} + " ({YEARS[-1]})"')
S("Title Segment", '"Repeat rate: " + ' + ' + '.join(f'IIF(ISNULL([Repeat {s}]), "", "{s} " + {pct(f"[Repeat {s}]")}{" + \'  ·  \'" if i < len(SEGS) - 1 else ""})' for i, s in enumerate(SEGS)))
S("Title Profit", '[Top Category] + " leads with " + ' + inr("[Top Category GP]") + ' + " (" + ' + pct("[Top Category GP] / SUM([RGP])")
  + ' + " of profit); margins run " + ' + pct("[Low Margin]") + ' + "–" + ' + pct("[High Margin]"))
S("Title GP Category", '[Top Category] + " earns most; " + [Low Category] + " least (" + ' + inr("[Low Category GP]") + ' + ")"')
S("Title Margin Category", '"Margin: highest in " + [High Margin Category] + " (" + ' + pct("[High Margin]", 1) + ' + "), thinnest in " + '
  '[Low Margin Category] + " (" + ' + pct("[Low Margin]", 1) + ' + ")"')
S("Title Discount", f'"Margin " + IIF([Margin Disc {DISC[-1]}] < [Margin Disc {DISC[0]}], "falls", "rises") + " from " + '
  f'{pct(f"[Margin Disc {DISC[0]}]")} + " at {DISC[0]}% item discount to " + {pct(f"[Margin Disc {DISC[-1]}]")} + " at {DISC[-1]}%"')
S("Title KPI", '"PPAC is " + ' + inr("[PPAC CY]") + ' + " in " + ' + CYL + ' + " YTD: " + STR(ROUND(ABS([PPAC CY] - [PPAC PY]) / [PPAC PY] * 100, 1)) '
  '+ IIF([PPAC CY] >= [PPAC PY], "% above", "% below") + " last year and " + STR(ROUND(ABS([PPAC CY] - [PPAC Target]) / [PPAC Target] * 100, 1)) '
  '+ IIF([PPAC CY] >= [PPAC Target], "% above", "% below") + " target"')
S("Title PPAC Years", '"PPAC, Jan–" + ' + MON + ' + ": " + ' + ' + " → " + '.join(inr(f"[PPAC LFL {y}]") for y in YEARS)
  + ' + " (target " + ' + inr("[PPAC Target]") + ' + ")"')
S("Title PPAC Segment", '"PPAC in " + ' + CYL + ' + " YTD: " + ' + ' + '.join(
    f'IIF(ISNULL([PPAC CY {s}]), "", "{s} " + ({inr(f"[PPAC CY {s}]")}){" + \'  ·  \'" if i < len(SEGS) - 1 else ""})' for i, s in enumerate(SEGS)))
mv = lambda d: f'IIF({d} >= 0, "rose ", "fell ")'
S("Title Drivers", '"In " + ' + CYL + ' + ", orders/customer " + ' + mv("([OPC CY] - [OPC PY])") + ' + STR(ROUND(ABS([OPC CY] - [OPC PY]) / [OPC PY] * 100, 1)) '
  '+ "%, order value " + ' + mv("([AOV CY] - [AOV PY])") + ' + STR(ROUND(ABS([AOV CY] - [AOV PY]) / [AOV PY] * 100, 1)) + "%, margin " + '
  + mv("([Margin CY] - [Margin PY])") + ' + STR(ROUND(ABS([Margin CY] - [Margin PY]) * 100, 1)) + " pp"')

# ================================================================ worksheets: page 1 Retention
SEG_F = {"column": "In Segment", "values": [True]}
STATE_F = {"column": "In State", "values": [True]}
BUYERS_ONLY = {"column": "Customer Type", "values": ["No Purchase"], "exclude": True}
P1F = (SEG_F, STATE_F)
CT_COLORS = {"Recurring": VIOLET, "One-Time": SLATE}

b.title("P1 Header", "Title Retention", f"One-time = 1 order  |  Recurring = 2+ orders  |  Lifetime, {PERIOD}  |  Titles follow the filters",
        filters=P1F, header=True)
p1_cards = [("K Buyers", "Buying customers", "V Buyers", [("X Buyers", NEUTRAL)]),
            ("K Repeat", "Repeat rate", "V Repeat", [("X Repeat", NEUTRAL)]),
            ("K RecShare", "Profit from recurring", "V RecShare", [("X RecShare", NEUTRAL)]),
            ("K Multiplier", "Recurring vs one-time", "V Multiplier", [("X Multiplier", NEUTRAL)]),
            ("K OPB", "Orders per buyer", "V OPB", [("X OPB", NEUTRAL)]),
            ("K Never", "Never ordered", "V Never", [("X Never", WARN)])]
for name, label, value, extra in p1_cards:
    b.card(name, label, value, extra, filters=P1F)
b.title("T New Buyers", "Title New Buyers", "First-time buyers per quarter of their first order", filters=P1F)
b.bar("New Buyers by Quarter", P1F, "Column chart of first-time buyers by quarter: new buyers fall each year after sign-ups stop.",
        columns=["First Order Year", "First Order Qtr"], rows=["New Buyers"], label="New Buyers", filters=[BUYERS_ONLY])
b.title("T Frequency", "Title Frequency", "Buying customers by lifetime order count", filters=P1F)
b.bar("Order Frequency Mix", P1F, "Column chart of buying customers by lifetime orders, from 1 to 4+.",
        columns=["Order Frequency"], rows=["New Buyers"], label="New Buyers", filters=[BUYERS_ONLY])
b.title("T Value", "Title Value", "Lifetime gross profit per customer, ₹ L", filters=P1F)
b.bar("Profit per Customer", P1F, "Bar chart of lifetime gross profit per customer: recurring in violet, one-time in grey.",
        rows=["Customer Type"], columns=["Profit per Customer ₹ L"], label="Profit per Customer ₹ L",
        color="Customer Type", color_map=CT_COLORS, sort_descending="Profit per Customer ₹ L", filters=[BUYERS_ONLY])
b.title("T Profit Type", "Title Profit Type", "Gross profit by year, ₹ L  |  grey = one-time buyers", filters=P1F)
b.bar("Profit by Type", P1F, "Stacked columns of gross profit by year, split into recurring and one-time customers.",
        columns=["YEAR(Order Date)"], rows=["Gross Profit ₹ L"], color="Customer Type", color_map=CT_COLORS,
        label="Gross Profit ₹ L", filters=[BUYERS_ONLY])
b.title("T Segment", "Title Segment", "Recurring / buying customers, by segment", filters=P1F)
b.bar("Repeat Rate by Segment", P1F, "Bar chart of the repeat rate in each customer segment.",
        rows=["Segment"], columns=["Repeat Rate"], label="Repeat Rate", sort_descending="Repeat Rate")

# ---------------------------------------------------------------- page 2 Profit
P2F = (SEG_F,)
b.title("P2 Header", "Title Profit", f"Cards: latest YTD vs same months last year  |  Charts: {PERIOD}  |  Click a category to filter",
        filters=P2F, header=True)
for key, label in (("GP", "Gross profit"), ("NS", "Net sales"), ("Margin", "Gross margin"), ("AOV", "Order value")):
    b.card(f"K2 {key}", label, f"V {key}", [(f"U {key}", GOOD), (f"D {key}", BAD)], filters=P2F)
b.card("K2 Top", "Top category", "Top Category", [("X Top", NEUTRAL)], filters=P2F, size=13)
b.card("K2 Low", "Lowest category", "Low Category", [("X Low", NEUTRAL)], filters=P2F, size=13)
b.title("T GP Category", "Title GP Category", "Gross profit by category, ₹ L, highest to lowest  |  click a bar", filters=P2F)
b.bar("Profit by Category", P2F, "Bar chart of gross profit by category in lakh rupees, sorted highest to lowest.",
        rows=["Category"], columns=["Gross Profit ₹ L"], label="Gross Profit ₹ L", sort_descending="Gross Profit ₹ L",
        tooltip=["Gross Margin %", "Revenue Orders"], filters=[BUYERS_ONLY])
b.title("T Margin Category", "Title Margin Category", "Gross margin % by category, highest to lowest (axis from zero)", filters=P2F)
b.bar("Margin by Category", P2F, "Bar chart of gross margin by category; all categories sit between 25% and 27%.", fill=NAVY,
        rows=["Category"], columns=["Gross Margin %"], label="Gross Margin %", sort_descending="Gross Margin %", filters=[BUYERS_ONLY])
b.bar("Profit by Subcategory", P2F, "Bar chart of gross profit by subcategory; click a category above to filter it.",
        rows=["Subcategory"], columns=["Gross Profit ₹ L"], label="Gross Profit ₹ L", sort_descending="Gross Profit ₹ L", filters=[BUYERS_ONLY, {"column": "Subcategory", "top": 10, "by": "SUM(RGP)"}])
b.title("T Discount", "Title Discount", "Gross margin % by item-level discount", filters=P2F)
b.bar("Margin by Discount", P2F, "Column chart of gross margin at each item discount: margin falls as the discount deepens.",
        columns=["Item Discount"], rows=["Gross Margin %"], label="Gross Margin %", filters=[BUYERS_ONLY])

# ---------------------------------------------------------------- page 3 KPI
P3F = (SEG_F,)
b.title("P3 Header", "Title KPI", "PPAC = gross profit / active customers = orders per customer x order value x margin  |  Target = same months last year + 5%",
        filters=P3F, header=True)
for key, label in (("PPAC", "PPAC, latest YTD"), ("OPC", "Orders per customer"), ("AOV", "Order value"),
                   ("Margin", "Gross margin"), ("Active", "Active customers")):
    b.card(f"K3 {key}", label, f"V {key}", [(f"U {key}", GOOD), (f"D {key}", BAD)], filters=P3F)
b.card("K3 Target", "Target (last year + 5%)", "V Target", [("U Target", GOOD), ("D Target", BAD)], filters=P3F)
LFL = {"column": "Like for Like Months", "values": [True]}
b.title("T PPAC Years", "Title PPAC Years", "Like-for-like months of each year, ₹ per active customer", filters=P3F)
b.bar("PPAC by Year", P3F, "Columns of PPAC for the same months of each year.",
        columns=["YEAR(Order Date)"], rows=["PPAC"], label="PPAC", filters=[LFL, BUYERS_ONLY])
b.title("T PPAC Segment", "Title PPAC Segment", "PPAC by segment, ₹, latest year to date", filters=P3F)
b.bar("PPAC by Segment", P3F, "Bar chart of PPAC by customer segment in the latest year.",
        rows=["Segment"], columns=["PPAC"], label="PPAC", sort_descending="PPAC",
        filters=[{"column": "Is CY", "values": [True]}])
b.title("T Drivers", "Title Drivers", "Same months of each year  |  PPAC = orders per customer x order value x margin", filters=P3F)
b.sheet("PPAC Drivers", P3F, "Table of PPAC and its drivers for the same months of each year.",
        style={"hide_row_field_labels": True},
        mark_type="Text", rows=["YEAR(Order Date)"], measure_values=["Active Customers", "Orders per Customer", "AOV", "Gross Margin %", "PPAC"],
        filters=[LFL, BUYERS_ONLY])
step("aliases", T.set_measure_name_aliases("PPAC Drivers", {"Active Customers": "Active", "Orders per Customer": "Orders / cust.",
                                                         "AOV": "Order value", "Gross Margin %": "Margin", "PPAC": "PPAC"}))

# ================================================================ forecast datasources (page 4)
f26 = list(csv.DictReader(open(OUTPUTS / "pbi_forecast_2026.csv", encoding="utf-8")))
scenarios = list(dict.fromkeys(r["scenario"] for r in f26))
step("param", T.add_parameter("Scenario Choice", "string", scenarios[0], domain_type="list", allowed_values=scenarios))
step("param", T.add_parameter("Chart Metric", "string", "Gross profit", domain_type="list",
                              allowed_values=["Gross profit", "Net sales", "Revenue orders", "New buyers"]))

step("ds forecast", T.add_hyper_datasource("RetailPulse Forecast", str(HYPER), "Forecast"))
C("Sel", "[Scenario] = [Scenario Choice] AND [Metric] = [Chart Metric]", "boolean")
C("Unit", "IF [Chart Metric] = 'Gross profit' OR [Chart Metric] = 'Net sales' THEN 100000 ELSE 1 END", "integer")
C("Chart Value", "SUM(IF [Sel] THEN [Value] / [Unit] END)", fmt="n#,##0.0")
b.sheet("Forecast Trend", (), "Line chart of monthly history and the 2026 forecast median with its 80% range.",
        style={"hide_col_field_labels": True, "hide_row_field_labels": True, "axis_style": {"per_field": [
            {"field": "Chart Value", "attr": "title", "class": "0", "scope": "rows", "value": "₹ L, or count"},
            {"field": "MONTHTRUNC(Month)", "attr": "title", "class": "0", "scope": "cols", "value": " "}]}},
        mark_type="Line", columns=["MONTHTRUNC(Month)"], rows=["Chart Value"], color="Series",
        color_map={"Actual": NAVY, "Forecast (median)": VIOLET, "Low case (P10)": BAND, "High case (P90)": BAND})

step("ds f26", T.add_hyper_datasource("RetailPulse 2026", str(HYPER), "Forecast 2026"))
F = lambda metric, col_="P50": f"SUM(IF [Scenario] = [Scenario Choice] AND [Metric] = '{metric}' THEN [{col_}] END)"
lakh1 = lambda x: f'"₹" + STR(ROUND(({x}) / 100000, 1)) + " L"'
for nm, f in (("F GP", F("Gross profit")), ("F GP Low", F("Gross profit", "P10")), ("F GP High", F("Gross profit", "P90")),
              ("F Orders", F("Revenue orders")), ("F New", F("New buyers")), ("F PPAC", F("PPAC")), ("F Target", F("PPAC target")),
              ("F Hit", F("P(PPAC hits target)")), ("B GP", F("Gross profit 2024")), ("B Orders", F("Revenue orders 2024")),
              ("B New", F("New buyers 2024"))):
    C(nm, f)
S("V F GP", lakh1("[F GP]"))
S("V F Range", '"₹" + STR(ROUND([F GP Low] / 100000, 0)) + "–" + STR(ROUND([F GP High] / 100000, 0)) + " L"')
S("X F Range", 'IF NOT ISNULL([F GP]) THEN "80% of 2,000 runs" END')
S("V F Orders", "STR(ROUND([F Orders], 0))")
S("V F New", "STR(ROUND([F New], 0))")
S("V F PPAC", inr("[F PPAC]"))
S("V F Hit", pct("[F Hit]"))
S("X F Hit", 'IF NOT ISNULL([F Hit]) THEN "of runs reach the target" END')
for key, cur, base_, unit in (("GP", "[F GP]", "[B GP]", lakh1("[B GP]")), ("Orders", "[F Orders]", "[B Orders]", "STR(ROUND([B Orders], 0))"),
                              ("New", "[F New]", "[B New]", "STR(ROUND([B New], 0))")):
    good, bad = change(cur, base_, label="vs 2024")
    S(f"U F {key}", good.replace('" vs 2024" END', f'" vs " + {unit} END'))
    S(f"D F {key}", bad.replace('" vs 2024" END', f'" vs " + {unit} END'))
S("U F PPAC", 'IF [F PPAC] >= [F Target] THEN STR(ROUND(([F PPAC] - [F Target]) / [F Target] * 100, 0)) + "% above target" END')
S("D F PPAC", 'IF [F PPAC] < [F Target] THEN STR(ROUND(([F Target] - [F PPAC]) / [F Target] * 100, 0)) + "% below target" END')
S("Title Forecast", '"2026 gross profit ≈ " + [V F GP] + " (80% range " + [V F Range] + "), scenario " + LEFT([Scenario Choice], 1)')
b.title("P4 Header", "Title Forecast", "Simulation, 2,000 runs  |  Median and 80% range  |  Cards vs 2024 (last full year)", header=True)
b.card("K4 GP", "2026 gross profit", "V F GP", [("U F GP", GOOD), ("D F GP", BAD)])
b.card("K4 Range", "80% range", "V F Range", [("X F Range", NEUTRAL)])
b.card("K4 Orders", "2026 revenue orders", "V F Orders", [("U F Orders", GOOD), ("D F Orders", BAD)])
b.card("K4 New", "2026 new buyers", "V F New", [("U F New", GOOD), ("D F New", BAD)])
b.card("K4 PPAC", "2026 PPAC", "V F PPAC", [("U F PPAC", GOOD), ("D F PPAC", BAD)])
b.card("K4 Hit", "Hits PPAC target", "V F Hit", [("X F Hit", NEUTRAL)])

step("ds levers", T.add_hyper_datasource("RetailPulse Levers", str(HYPER), "Levers"))
C("Lever Label", "IF CONTAINS([Lever], 'Discount cap') THEN 'Discount cap 10%, no stacking' ELSE [Lever] END", "string")
C("Uplift ₹ L", "SUM([Uplift Mid]) / 100000", fmt='n"₹"#,##0.0" L"')
C("Low ₹ L", "SUM([Uplift Low]) / 100000", fmt='n"₹"#,##0.0" L"')
C("High ₹ L", "SUM([Uplift High]) / 100000", fmt='n"₹"#,##0.0" L"')
S("Title Levers", '"Four levers, each worth ₹" + STR(ROUND(MIN([Uplift Low]) / 100000, 1)) + "–" + STR(ROUND(MAX([Uplift High]) / 100000, 1)) + " L of 2026 gross profit"')
b.title("T Levers", "Title Levers", "Mid estimate, ₹ L  |  confidence and cost in the plan  |  hover for the range")
b.bar("Profit Levers", (), "Bar chart of four 2026 profit levers with their mid uplift in lakh rupees.",
        rows=["Lever Label"], columns=["Uplift ₹ L"], label="Uplift ₹ L", sort_descending="Uplift ₹ L",
        tooltip=["Low ₹ L", "High ₹ L", "Confidence", "Cost"])

# ================================================================ static text (plan, insights, footer) from the notebook outputs
lv = {r["lever"]: r for r in csv.DictReader(open(OUTPUTS / "pbi_levers.csv", encoding="utf-8"))}
lk = lambda x: float(x) / 1e5
cap, act = lv["Discount cap (10%, no stacking)"], lv["Activate 20% of never-ordered"]
rep, rst = lv["Repeat rate 53% to 60%"], lv["Restart sign-ups (2024 pace)"]
base = lk(next(r["p50"] for r in f26 if r["scenario"] == scenarios[0] and r["metric"] == "Gross profit"))
lo, hi = lk(cap["uplift_low"]) + lk(act["uplift_low"]), lk(cap["uplift_high"]) + lk(act["uplift_high"])


def text(title, items, accent=VIOLET):
    runs = [{"text": title + "\n", "bold": True, "font_size": "11", "font_color": INK, "font_alignment": "0"}]
    for lead, rest in items:
        runs += [{"text": lead, "bold": True, "font_size": "9", "font_color": accent, "font_alignment": "0"},
                 {"text": rest + "\n", "font_size": "9", "font_color": INK, "font_alignment": "0"}]
    return {"type": "text", "runs": runs, "style": {"background-color": "#FFFFFF"}}


plan = text(f"Recommended plan: start with the two cheap levers (₹{lo:.0f}–{hi:.0f} L)", [
    ("1. Pricing: ", f"cap item discounts at 10%, no stacking (+₹{lk(cap['uplift_low']):.1f}–{lk(cap['uplift_high']):.1f} L, high confidence, no cost)."),
    ("2. CRM: ", f"first-order offer to the 80 never-ordered (+₹{lk(act['uplift_low']):.1f}–{lk(act['uplift_high']):.1f} L, medium, low cost)."),
    ("3. CRM: ", f"second-order nudge, repeat rate 53% to 60% (+₹{lk(rep['uplift_mid']):.1f} L; lowers PPAC)."),
    ("4. Marketing: ", f"find out why sign-ups stopped before spending on them (+₹{lk(rst['uplift_mid']):.1f} L at the 2024 pace)."),
    ("Size: ", f"levers 1+2 add {lo / base:.0%}–{hi / base:.0%} to the ₹{base:.1f} L baseline (scenario A); levers overlap, so don't add all four."),
])
retention_text = text("What this tells us (all customers)", [
    ("Retention carries profit: ", "recurring customers are 53% of buyers but earn 76% of gross profit."),
    ("Second orders are slow: ", "the median gap is 254 days; 54% return within 2 years. Silence is not churn."),
    ("The funnel is empty: ", "no sign-ups since 25 Sep 2024, and 80 registered customers never ordered."),
    ("Action: ", "a second-order nudge for one-time buyers and a first-order offer for the 80."),
])
kpi_text = text("Why this KPI", [
    ("One number, three owners: ", "frequency (CRM), order value (merchandising), margin (pricing)."),
    ("Read it with total profit: ", "winning back one-time buyers adds profit but can lower PPAC."),
    ("Target: ", "same months last year + 5%; the cards compare like-for-like months."),
])
FOOTER = {"type": "text", "runs": [{"text": f"Source: Online Sales Data, {PERIOD} · Extract {date.today():%d %b %Y} · "
                                            "Profit excl. shipping, marketing · Synthetic data",
                                    "font_size": "8", "font_color": NEUTRAL}]}
PAGES = [("1 Retention", "1 Retention"), ("2 Profit", "2 Profit"), ("3 KPI", "3 KPI"), ("4 Forecast", "4 Forecast")]


def page(name, header, filters, cards, row2, row3):
    """Grey canvas: full-width navy header with the controls in white boxes, a row of KPI cards, two rows of chart
    panels, then the footer and navigation."""
    top = [ws(header, weight=1)] + filters
    return {"type": "container", "direction": "vertical", "style": {"background-color": CANVAS}, "children": [
        {"type": "container", "direction": "horizontal", "fixed_size": 74, "style": {"background-color": NAVY}, "children": top},
        {"type": "container", "direction": "horizontal", "fixed_size": 136, "children": [card_zone(c, WARN if c == "K Never" else VIOLET) for c in cards]},
        {"type": "container", "direction": "horizontal", "weight": 1, "children": row2},
        {"type": "container", "direction": "horizontal", "weight": 1, "children": row3},
        {"type": "container", "direction": "horizontal", "fixed_size": 30, "children": [dict(FOOTER, weight=1)] + k.nav_bar(PAGES, name)},
    ]}


def flt(sheet, field, mode="dropdown"):
    return {"type": "filter", "worksheet": sheet, "field": field, "mode": mode, "fixed_size": 190}


def param(p, width=220):
    """Parameter dropdown in a white box on the navy header (like the Power BI slicers)."""
    return {"type": "paramctrl", "parameter": p, "mode": "compact", "fixed_size": width,
            "style": {"background-color": "#FFFFFF", "margin": "10", "padding": "2"}}


layouts = {
    "1 Retention": page("1 Retention", "P1 Header", [param("Segment Choice", 190), param("State Choice", 190)], [c[0] for c in p1_cards],
                        [block("T New Buyers", "New Buyers by Quarter"), block("T Frequency", "Order Frequency Mix"), block("T Value", "Profit per Customer")],
                        [block("T Profit Type", "Profit by Type"), block("T Segment", "Repeat Rate by Segment"), panel(retention_text)]),
    "2 Profit": page("2 Profit", "P2 Header", [param("Segment Choice", 190)], ["K2 GP", "K2 NS", "K2 Margin", "K2 AOV", "K2 Top", "K2 Low"],
                     [block("T GP Category", "Profit by Category"), block("T Margin Category", "Margin by Category")],
                     [block(static_title("Top 10 subcategories by gross profit, ₹ L", "Click a category above to filter"), "Profit by Subcategory"), block("T Discount", "Margin by Discount")]),
    "3 KPI": page("3 KPI", "P3 Header", [param("Segment Choice", 190)], ["K3 PPAC", "K3 Target", "K3 OPC", "K3 AOV", "K3 Margin", "K3 Active"],
                  [block("T PPAC Years", "PPAC by Year", weight=3), block("T PPAC Segment", "PPAC by Segment", weight=2)],
                  [block("T Drivers", "PPAC Drivers", weight=3), panel(kpi_text, 2)]),
    "4 Forecast": page("4 Forecast", "P4 Header", [param("Scenario Choice"), param("Chart Metric")],
                       ["K4 GP", "K4 Range", "K4 Orders", "K4 New", "K4 PPAC", "K4 Hit"],
                       [block(static_title("Monthly history and forecast: single months swing, so plan on quarterly totals",
                                             "₹ L for profit and sales, counts otherwise  |  light violet = 80% range  |  backtest, 6 held-out months: orders -1.4%, profit -10.2%, inside the range"), "Forecast Trend")],
                       [block("T Levers", "Profit Levers", weight=11), panel(plan, 9)]),
}
p1_sheets = [s for s in b.sheets if s.startswith(("P1", "K ", "T New", "T Freq", "T Value", "T Profit Type", "T Segment"))] + \
            ["New Buyers by Quarter", "Order Frequency Mix", "Profit per Customer", "Profit by Type", "Repeat Rate by Segment"]
dash_sheets = {
    "1 Retention": p1_sheets,
    "2 Profit": [s for s in b.sheets if s.startswith(("P2", "K2"))] + ["T GP Category", "Profit by Category", "T Margin Category", "Margin by Category",
                                                                       "Profit by Subcategory", "T Discount", "Margin by Discount"],
    "3 KPI": [s for s in b.sheets if s.startswith(("P3", "K3"))] + ["T PPAC Years", "PPAC by Year", "T PPAC Segment", "PPAC by Segment", "T Drivers", "PPAC Drivers"],
    "4 Forecast": [s for s in b.sheets if s.startswith(("P4", "K4"))] + ["Forecast Trend", "T Levers", "Profit Levers"],
}
step("select sales", T.select_datasource("RetailPulse Sales"))   # filter controls resolve against the sales source
for name, tree in layouts.items():
    path = k.save_layout(LAYOUT_DIR / f"{name}.json", tree)
    step(f"dashboard {name}", T.add_dashboard(name, dash_sheets[name], width=1400, height=900, layout=path))
    step(f"phone {name}", T.enable_automatic_phone_layout(name))
step("action", T.add_dashboard_action("2 Profit", "filter", source_sheet="Profit by Category", target_sheet="Profit by Subcategory",
                                      fields=["Category"], caption="Filter subcategories by category"))
print("navigation buttons:", k.finish_navigation(T.get_editor()))
for s in b.sheets:
    step(f"hide {s}", T.set_worksheet_hidden(s, True))
step("save", T.save_workbook(str(OUT)))
print(f"saved {OUT.name}: {len(b.sheets)} worksheets, {len(b.calcs)} calculated fields, 4 dashboards")
