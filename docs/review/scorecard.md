# Scorecard: RetailPulse-Tableau

Reviewer: Claude, using the expert rubric `D:\Wolf\PBI\_knowledge\dashboard_scorecard.md` (v1), the same one used for the
Power BI builds. Date: 25 Nov 2026.

**Evidence:**
- **PDF exports:** the final export is `docs/RetailPulse-Tableau.pdf`, with page images in `docs/dashboard/`. It was reviewed after each of six export rounds.
- **Independent reconciliation:** `_build/reconcile.py` recomputes every number on the four dashboards with pandas from the source parquet. All matched (see the table below).
- **Hand tests in Tableau Desktop 2026.3:**
  - the Segment choice on page 1 changes pages 1–3
  - clicking a category on page 2 filters the subcategory chart
  - the final workbook opens without warnings
- **Schema check:** `cwtwb validate` passes. The only remaining item is the known "referenced-extensions" strict-schema warning, which Tableau accepts.

| # | Criterion | Before (v1) | After (v2) | What changed |
|---|---|---|---|---|
| 1 | Purpose and message | 0.25 | 1.0 | Topic titles ("Net Sales Trend") became action titles built from string calculations, so they follow the filters. Example: "53% of buyers came back, and they earn 76% of gross profit". Each title is a small text sheet, because a measure in a worksheet title shows "*" once a chart has several marks. |
| 2 | Data trust and accuracy | 0.75 | 1.0 | Every number reconciles with pandas, not just the five v1 KPIs. A footer on every page gives the source, period, extract date and caveats. |
| 3 | KPI design | 0.25 | 1.0 | The cards show ▲▼ change lines against the same months last year, or against target. The change text is green or red at AA contrast, and grey for context lines. PPAC is broken into orders per customer, order value and margin. |
| 4 | Chart choice and honesty | 0.5 | 1.0 | Bars are sorted and start at zero (axes hidden, direct labels). The forecast shows an 80% range and states its backtest. Never-ordered customers are kept out of the category and discount charts, so there is no "Null" bar. |
| 5 | Layout and hierarchy | 0.5 | 1.0 | Four dashboards share one template: header, KPI row, two chart rows, footer and navigation. Every zone has a fixed pixel size, because Tableau sizes tiled zones by their content otherwise. Nothing is clipped in the export. |
| 6 | Colour and accessibility | 0.5 | 1.0 | The InXiteOut palette, the same as RetailPulse-PBI: violet for the main series, slate for context (ΔE 78 under deuteranopia), AA-contrast status text with ▲▼ as a second cue. Every worksheet has a descriptive caption. |
| 7 | Declutter, text, formatting | 0.25 | 1.0 | Indian units (₹, ₹ L, ₹ Cr) replace raw figures like 108,222,683. Field labels and axis titles are hidden where bars carry labels. One font family. |
| 8 | Interaction, navigation, devices | 0.25 | 0.75 | Segment and State parameters drive pages 1–3 (hand-tested), plus a category click filter (hand-tested), navigation buttons, scenario and metric controls, tooltips and generated phone layouts. **Not verified by hand:** clicking the navigation buttons and viewing the phone layout in Device Preview. |
| 9 | Insight and action | 0.5 | 1.0 | Ranked findings and a recommended plan with owners, cost, confidence and ₹ ranges (start with the two cheap levers, ₹20–28 L). The 2026 forecast is compared with 2024, and its backtest is stated. |
| 10 | Model and engineering | 0.75 | 0.75 | Fully generated: an extract builder (Hyper API) and a workbook builder on the reusable `_build/twb_kit.py`, plus `cwtwb validate`, a reconciliation script, and a guard against building while Tableau locks the extract. **Not measured:** query time, because a Tableau Performance Recording needs the UI. |
| | Gates applied | max 6 (brief Q1 unanswered) | none | Brief Q1 (one-time vs recurring) has its own dashboard; no clipped text or misleading encodings remain. |
| | **Total** | **4.5 / 10** | **9.5 / 10** | |

**To reach 10:**
1. Click each navigation button once.
2. Open Dashboard → Device Preview → Phone on each page.
3. Run Help → Settings and Performance → Start Performance Recording, click through the four pages, and stop it.

If the buttons work, the phone layouts read well and every view renders in under 1–2 s, criteria 8 and 10 become 1.0.

## Reconciliation (pandas = Tableau)

| Page | Number | Value |
|---|---|---|
| 1 | Buying / registered customers | 220 / 300 (73%) |
| 1 | Repeat rate | 52.7% (116 recurring vs 104 one-time) |
| 1 | Profit from recurring | 76.2% (₹2.18 Cr of ₹2.86 Cr) |
| 1 | Recurring vs one-time per customer | 2.8x (₹1.88 L vs ₹0.68 L) |
| 1 | New buyers per year | 128 → 64 → 28; last sign-up 25 Sep 2024 |
| 1 | Repeat rate by segment | Retail 53.6%, Wholesale 48.8% |
| 2 | Gross profit, latest YTD vs same months last year | ₹83.6 L, +5.7% |
| 2 | Net sales, margin, order value | ₹3.12 Cr (−1.7%), 26.8% (+1.9 pp), ₹2.73 L (−4.2%) |
| 2 | Category leader / laggard | Beauty ₹76.5 L (27%); Home & Kitchen ₹48.1 L |
| 2 | Margin by item discount | 30.4% → 27.3% → 21.1% → 17.1% |
| 3 | PPAC, latest YTD | ₹92,868 (−1.3% vs last year; −6.0% vs the ₹98,816 target) |
| 3 | PPAC Jan–Oct by year | ₹92,136 → ₹94,110 → ₹92,868 |
| 3 | PPAC by segment | Retail ₹96,563, Wholesale ₹79,061 |
| 4 | 2026 gross profit (scenario A) | ₹96.9 L (+7.3% vs ₹90.3 L in 2024), 80% range ₹80–115 L |
| 4 | 2026 orders / new buyers / PPAC | 132 (+3.9%), 23 (−64.1%), ₹92,247 (12% below the ₹1.04 L target) |

These match RetailPulse-PBI, which reports the same numbers from its own model.
