"""Independent check of every number on the four dashboards, computed with pandas from the source parquet files.
Compare the output with the PDF export (docs/RetailPulse-Tableau.pdf); the expected values are recorded in
docs/review/reconciliation.md.

Usage: .venv\\Scripts\\python _build\\reconcile.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

SRC = Path(os.environ.get("RETAILPULSE_PARQUET", r"D:\Wolf\PBI\RetailPulse-PBI\analysis\data"))
OUT = Path(os.environ.get("RETAILPULSE_OUTPUTS", r"D:\Wolf\PBI\RetailPulse-PBI\analysis\output"))
lines = pd.read_parquet(SRC / "lines.parquet")
cust = pd.read_parquet(SRC / "customers.parquet")
rev = lines[lines["is_revenue"]].merge(cust[["customer_id", "customer_type", "segment"]], on="customer_id", how="left")
max_date = lines["order_date"].max()
cy = rev[rev["order_date"].dt.year == max_date.year]
py = rev[(rev["order_date"].dt.year == max_date.year - 1) & (rev["order_date"] <= max_date - pd.DateOffset(years=1))]
rows: list[tuple[str, str, str]] = []
L = lambda x: f"₹{x / 1e5:,.2f} L"


def add(page, item, value):
    rows.append((page, item, value))


def kpis(d):
    o, a = d["order_id"].nunique(), d["customer_id"].nunique()
    ns, gp = d["net_sales"].sum(), d["gross_profit"].sum()
    return dict(gp=gp, ns=ns, margin=gp / ns, orders=o, active=a, aov=ns / o, opc=o / a, ppac=gp / a)


# ---------------- 1 Retention (lifetime)
buyers = cust[cust["customer_type"] != "No Purchase"]
rec = cust[cust["customer_type"] == "Recurring"]
one = cust[cust["customer_type"] == "One-Time"]
gp_type = rev.groupby("customer_type")["gross_profit"].sum()
act_type = rev.groupby("customer_type")["customer_id"].nunique()
ppr, ppo = gp_type["Recurring"] / act_type["Recurring"], gp_type["One-Time"] / act_type["One-Time"]
add("1", "Buying customers / registered", f"{len(buyers)} / {len(cust)} ({len(buyers) / len(cust):.0%})")
add("1", "Repeat rate", f"{len(rec) / len(buyers):.1%} ({len(rec)} vs {len(one)})")
add("1", "Profit from recurring", f"{gp_type['Recurring'] / rev['gross_profit'].sum():.1%} ({L(gp_type['Recurring'])} of {L(rev['gross_profit'].sum())})")
add("1", "Recurring vs one-time per customer", f"{ppr / ppo:.1f}x ({L(ppr)} vs {L(ppo)})")
add("1", "Orders per buyer (any status)", f"{lines['order_id'].nunique() / len(buyers):.2f}; 3+ orders {(buyers['lifetime_orders'] >= 3).mean():.0%}")
add("1", "Never ordered", f"{len(cust) - len(buyers)} ({(len(cust) - len(buyers)) / len(cust):.0%} of registered)")
add("1", "New buyers per year", " → ".join(str(v) for v in buyers.groupby(buyers['first_order'].dt.year).size()))
add("1", "Last sign-up", f"{cust['join_date'].max():%d %b %Y}")
add("1", "Order frequency 1/2/3/4+", "/".join(str((buyers['lifetime_orders'].clip(upper=4) == k).sum()) for k in (1, 2, 3, 4)))
yr = rev.groupby([rev["order_date"].dt.year, "customer_type"])["gross_profit"].sum().unstack()
add("1", "Profit by year, recurring / one-time", "; ".join(f"{y}: {L(r['Recurring'])} / {L(r['One-Time'])}" for y, r in yr.iterrows()))
add("1", "Repeat rate by segment", "; ".join(f"{s} {(g['customer_type'] == 'Recurring').sum() / len(g):.1%}" for s, g in buyers.groupby("segment")))

# ---------------- 2 Profit
c, p = kpis(cy), kpis(py)
add("2", "Gross profit YTD vs same months LY", f"{L(c['gp'])}, {c['gp'] / p['gp'] - 1:+.1%}")
add("2", "Net sales YTD", f"₹{c['ns'] / 1e7:.2f} Cr, {c['ns'] / p['ns'] - 1:+.1%}")
add("2", "Gross margin YTD", f"{c['margin']:.1%}, {100 * (c['margin'] - p['margin']):+.1f} pp")
add("2", "Order value YTD", f"{L(c['aov'])}, {c['aov'] / p['aov'] - 1:+.1%}")
cat = rev.groupby("category").agg(gp=("gross_profit", "sum"), ns=("net_sales", "sum")).assign(m=lambda d: d.gp / d.ns)
add("2", "Gross profit by category", "; ".join(f"{k} {L(v)}" for k, v in cat["gp"].sort_values(ascending=False).items()))
add("2", "Margin by category", "; ".join(f"{k} {v:.1%}" for k, v in cat["m"].sort_values(ascending=False).items()))
add("2", "Top 10 subcategories", "; ".join(f"{k} {L(v)}" for k, v in rev.groupby("subcategory")["gross_profit"].sum().nlargest(10).items()))
disc = rev.groupby("item_discount_percent").apply(lambda d: d["gross_profit"].sum() / d["net_sales"].sum())
add("2", "Margin by item discount", "; ".join(f"{k}% {v:.1%}" for k, v in disc.items()))

# ---------------- 3 KPI
add("3", "PPAC YTD vs LY / target", f"₹{c['ppac']:,.0f}, {c['ppac'] / p['ppac'] - 1:+.1%}; target ₹{p['ppac'] * 1.05:,.0f} ({c['ppac'] / (p['ppac'] * 1.05) - 1:+.1%})")
add("3", "Orders/customer, active customers", f"{c['opc']:.2f} ({c['opc'] / p['opc'] - 1:+.1%}); {c['active']} ({c['active'] / p['active'] - 1:+.1%})")
lfl = rev[rev["order_date"].dt.month <= max_date.month]
for y, g in lfl.groupby(lfl["order_date"].dt.year):
    k = kpis(g)
    add("3", f"Drivers {y} Jan–{max_date:%b}", f"active {k['active']}, orders/cust {k['opc']:.2f}, AOV ₹{k['aov']:,.0f}, margin {k['margin']:.1%}, PPAC ₹{k['ppac']:,.0f}")
add("3", "PPAC YTD by segment", "; ".join(f"{s} ₹{kpis(g)['ppac']:,.0f}" for s, g in cy.groupby("segment")))

# ---------------- 4 Forecast (notebook outputs)
f26 = pd.read_csv(OUT / "pbi_forecast_2026.csv", encoding="utf-8")
a = f26[f26["scenario"].str.startswith("A")].set_index("metric")
r24 = rev[rev["order_date"].dt.year == 2024]
gp24, o24 = r24["gross_profit"].sum(), r24["order_id"].nunique()
nb24 = int((buyers["first_order"].dt.year == 2024).sum())
add("4", "2026 gross profit (A) vs 2024", f"{L(a.loc['Gross profit', 'p50'])} ({a.loc['Gross profit', 'p50'] / gp24 - 1:+.1%} vs {L(gp24)}); 80% range "
    f"₹{a.loc['Gross profit', 'p10'] / 1e5:.0f}–{a.loc['Gross profit', 'p90'] / 1e5:.0f} L")
add("4", "2026 orders / new buyers vs 2024", f"{a.loc['Revenue orders', 'p50']:.0f} ({a.loc['Revenue orders', 'p50'] / o24 - 1:+.1%} vs {o24}); "
    f"{a.loc['New buyers', 'p50']:.0f} ({a.loc['New buyers', 'p50'] / nb24 - 1:+.1%} vs {nb24})")
add("4", "2026 PPAC vs target; chance", f"₹{a.loc['PPAC', 'p50']:,.0f} ({a.loc['PPAC', 'p50'] / a.loc['PPAC target', 'p50'] - 1:+.0%} vs ₹{a.loc['PPAC target', 'p50']:,.0f}); "
    f"{a.loc['P(PPAC hits target)', 'p50']:.0%}")
lv = pd.read_csv(OUT / "pbi_levers.csv")
add("4", "Levers (mid)", "; ".join(f"{r.lever} {L(r.uplift_mid)}" for r in lv.itertuples()))

for pg, item, val in rows:
    print(f"[{pg}] {item}: {val}")
