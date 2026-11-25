"""Generate RetailPulse-Tableau.twb from data/retailpulse.hyper with cwtwb (no Tableau Desktop needed).

Usage: .venv\\Scripts\\python _build\\build_workbook.py
"""
from __future__ import annotations

import json
from pathlib import Path

import cwtwb
from cwtwb.mcp import tools_workbook as T

ROOT = Path(__file__).resolve().parents[1]
HYPER = ROOT / "data" / "retailpulse.hyper"
OUT = ROOT / "RetailPulse-Tableau.twb"
LAYOUT = ROOT / "_build" / "layout.json"
EMPTY = Path(cwtwb.__file__).parent / "references" / "empty_template.twb"


def step(label, result):
    text = str(result)
    print(f"== {label}: {text.splitlines()[0] if text else ''}")
    if any(w in text.lower() for w in ("error", "failed", "invalid")):
        print(text)
        raise SystemExit(1)
    return text


step("create", T.create_workbook(str(EMPTY), "RetailPulse"))
step("hyper", T.set_hyper_connection(str(HYPER), table_name="Extract"))
T.get_editor()._datasource.set("caption", "RetailPulse Sales")  # template caption would otherwise say Superstore

# Revenue lines only (delivered and shipped orders), the same rule as the Power BI model
step("calc", T.add_calculated_field("Revenue Net Sales", "IF [Is Revenue] THEN [Net Sales] END", "real"))
step("calc", T.add_calculated_field("Revenue Gross Profit", "IF [Is Revenue] THEN [Gross Profit] END", "real"))
step("calc", T.add_calculated_field("Gross Margin %", "SUM([Revenue Gross Profit]) / SUM([Revenue Net Sales])", "real"))
step("calc", T.add_calculated_field("Revenue Orders", "COUNTD(IF [Is Revenue] THEN [Order ID] END)", "integer"))
step("calc", T.add_calculated_field("Avg Order Value", "SUM([Revenue Net Sales]) / [Revenue Orders]", "real"))

sheets = {
    "KPIs": dict(mark_type="Text", measure_values=["SUM(Revenue Net Sales)", "SUM(Revenue Gross Profit)", "Gross Margin %", "Revenue Orders", "Avg Order Value"]),
    "Net Sales Trend": dict(mark_type="Line", columns=["MONTHTRUNC(Order Date)"], rows=["SUM(Revenue Net Sales)"]),
    "Net Sales by Category": dict(mark_type="Bar", rows=["Category"], columns=["SUM(Revenue Net Sales)"], label="SUM(Revenue Net Sales)", sort_descending="SUM(Revenue Net Sales)"),
    "Margin by Category": dict(mark_type="Bar", rows=["Category"], columns=["Gross Margin %"], label="Gross Margin %", sort_descending="Gross Margin %"),
    "Net Sales by State": dict(mark_type="Bar", rows=["State"], columns=["SUM(Revenue Net Sales)"], sort_descending="SUM(Revenue Net Sales)"),
    "Orders by Payment Method": dict(mark_type="Bar", rows=["Payment Method"], columns=["Revenue Orders"], label="Revenue Orders", sort_descending="Revenue Orders"),
}
for name, cfg in sheets.items():
    step("sheet", T.add_worksheet(name))
    step(f"chart {name}", T.configure_chart(name, **cfg))

step("format", T.set_field_format("Gross Margin %", "p0.0%"))
step("format", T.set_field_format("Avg Order Value", "n#,##0"))

layout = {
    "type": "container", "direction": "vertical", "children": [
        {"type": "text", "text": "RetailPulse — Sales Overview (revenue orders only)", "fixed_size": 50, "font_size": "18", "bold": True},
        {"type": "worksheet", "name": "KPIs", "fixed_size": 130},
        {"type": "container", "direction": "horizontal", "weight": 1, "children": [
            {"type": "worksheet", "name": "Net Sales Trend", "weight": 2},
            {"type": "worksheet", "name": "Net Sales by Category", "weight": 1}]},
        {"type": "container", "direction": "horizontal", "weight": 1, "children": [
            {"type": "worksheet", "name": "Margin by Category", "weight": 1},
            {"type": "worksheet", "name": "Net Sales by State", "weight": 1},
            {"type": "worksheet", "name": "Orders by Payment Method", "weight": 1}]},
    ]}
LAYOUT.write_text(json.dumps(layout, indent=2), encoding="utf-8")
step("dashboard", T.add_dashboard("RetailPulse Overview", list(sheets), width=1400, height=900, layout=str(LAYOUT)))
step("save", T.save_workbook(str(OUT)))
