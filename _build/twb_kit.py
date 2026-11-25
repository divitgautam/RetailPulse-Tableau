"""Reusable helpers for building scored Tableau dashboards with cwtwb (the Tableau counterpart of the Power BI
projects' pbir_kit.py). cwtwb is AGPL-3.0 and is imported as a dependency, never copied.

What it adds on top of cwtwb's tools:
- Tableau formula builders: Indian rupee text (₹ / ₹ L / ₹ Cr), percentages, ▲▼ change lines split into an "up"
  and a "down" field so each can carry its own AA colour.
- Card, title and chart helpers. A dynamic title is a small Text worksheet with no dimensions above its chart,
  because a measure in a worksheet title shows "*" once a chart has several marks.
- Every worksheet joins the dashboard filter groups it belongs to (one control filters all of them).
- Navigation buttons: placeholders are written during layout and converted to real buttons once every target
  dashboard exists (cwtwb needs the target window id).
"""
from __future__ import annotations

import json
from pathlib import Path

from cwtwb.layout import FlexNode, _render_navigation_button
from cwtwb.mcp import tools_workbook as T

# InXiteOut palette (same as RetailPulse-PBI); status colours meet WCAG AA (>= 4.5:1) on white
NAVY, VIOLET, SLATE, CORAL, INK, MUTED, LILAC = "#030734", "#682EFF", "#62748E", "#F05100", "#020618", "#62748E", "#C8C3F5"
GOOD, BAD, WARN, NEUTRAL, BAND = "#1E7F4B", "#C0392B", "#A15F00", "#5B6B7F", "#9A86E8"
NAV_PREFIX = "NAV|"


def hyper_unlocked(path):
    """Stop early if Tableau holds the extract open: cwtwb then cannot read its columns and writes a broken workbook."""
    from tableauhyperapi import Connection, HyperProcess, Telemetry
    try:
        with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp, Connection(hp.endpoint, str(path)):
            pass
    except Exception as exc:
        raise SystemExit(f"Close Tableau first: {path.name} is locked ({str(exc).splitlines()[0]})")


def step(label, result):
    """Run one cwtwb call and stop on any reported problem."""
    text = str(result)
    if any(w in text.lower() for w in ("error", "failed", "invalid", "unknown field", "not found")):
        print(f"!! {label}: {text}")
        raise SystemExit(1)
    return text


# ---------------------------------------------------------------- Tableau formula builders
def inr(x: str) -> str:
    """Text in Indian units: under ₹1 L in rupees with a thousands comma, ₹1-10 L with 2 decimals, then ₹ L, then ₹ Cr."""
    v = f"({x})"
    r = f"INT(ROUND({v}, 0))"
    thousands = f'STR(INT({r} / 1000)) + "," + RIGHT("00" + STR({r} % 1000), 3)'
    return (f'IF ISNULL({v}) THEN "" '
            f'ELSEIF ABS({v}) >= 10000000 THEN "₹" + STR(ROUND({v} / 10000000, 2)) + " Cr" '
            f'ELSEIF ABS({v}) >= 1000000 THEN "₹" + STR(ROUND({v} / 100000, 1)) + " L" '
            f'ELSEIF ABS({v}) >= 100000 THEN "₹" + STR(ROUND({v} / 100000, 2)) + " L" '
            f'ELSEIF ABS({v}) >= 1000 THEN "₹" + {thousands} '
            f'ELSE "₹" + STR({r}) END')


def pct(x: str, dec: int = 0) -> str:
    return f'STR(ROUND(({x}) * 100, {dec})) + "%"'


def num(x: str, dec: int = 0) -> str:
    return f"STR(ROUND({x}, {dec}))"


def change(cur: str, prev: str, label: str = "vs last year", pp: bool = False, good_up: bool = True):
    """(up text, down text) formulas for a card change line; one of the two is blank, so each gets its own colour.
    Returns them in (good, bad) order so the caller colours the first green and the second red."""
    d = f"(({cur}) - ({prev})) * 100" if pp else f"(({cur}) - ({prev})) / ({prev})"
    mag = f'STR(ROUND(ABS({d}), 1)) + " pp"' if pp else f'STR(ROUND(ABS({d}) * 100, 1)) + "%"'
    up = f'IF NOT ISNULL({prev}) AND {d} >= 0 THEN "▲ " + {mag} + " {label}" END'
    down = f'IF NOT ISNULL({prev}) AND {d} < 0 THEN "▼ " + {mag} + " {label}" END'
    return (up, down) if good_up else (down, up)


# ---------------------------------------------------------------- workbook helpers
class Book:
    def __init__(self, template: Path, name: str):
        step("create", T.create_workbook(str(template), name))
        self.sheets: list[str] = []
        self.calcs: set[str] = set()

    def calc(self, name, formula, datatype="real", fmt=None, **kw):
        step(f"calc {name}", T.add_calculated_field(name, formula, datatype, **kw))
        self.calcs.add(name)
        if fmt:
            step(f"format {name}", T.set_field_format(name, fmt))
        return name

    def sheet(self, name, dash_filters=(), caption=None, style=None, **chart):
        """Add a worksheet, configure it, attach the dashboard filters and an accessibility caption."""
        step(f"sheet {name}", T.add_worksheet(name))
        chart_filters = list(chart.pop("filters", None) or []) + [dict(f) for f in dash_filters]
        step(f"chart {name}", T.configure_chart(name, filters=chart_filters or None, **chart))
        if caption:
            step(f"caption {name}", T.set_worksheet_caption(name, caption))
        if style:
            step(f"style {name}", T.configure_worksheet_style(name, **style))
        self.sheets.append(name)
        return name

    def bar(self, name, dash_filters=(), caption=None, fill=VIOLET, axes=False, **chart):
        """Bar/column chart in one brand colour (unless coloured by a field), direct labels, no axis or field-label clutter."""
        style = {"hide_col_field_labels": True, "hide_row_field_labels": True}
        if not chart.get("color"):
            style["pane_mark_style"] = {"mark_color": fill}
        if not axes:
            style.update(hide_axes=True, hide_gridlines=True)
        return self.sheet(name, dash_filters, caption, style=style, mark_type="Bar", **chart)

    def card(self, name, label, value, lines=(), filters=(), caption=None, size=20):
        """KPI card: grey label, big value, then coloured lines given as (field, colour)."""
        runs = [{"text": label, "fontsize": 9, "fontcolor": MUTED}, {"text": "\n"},
                {"field": value, "fontsize": size, "bold": True, "fontcolor": INK}]
        if lines:
            runs.append({"text": "\n"})
            runs += [{"field": f, "fontsize": 9, "fontcolor": c} for f, c in lines]
        fields = [value] + [f for f, _ in lines]
        out = self.sheet(name, filters, caption or f"{label} card", mark_type="Text", label=value,
                         tooltip=fields[1:] or None, label_runs=runs,
                         style={"disable_tooltip": True, "hide_borders": True})
        text_shelf(name)
        return out

    def title(self, name, title_field=None, subtitle="", static=None, filters=(), header=False):
        """Title sheet: an action title from a string calc (follows the filters) plus a subtitle line."""
        big = {"fontsize": 15 if header else 10, "bold": True, "fontcolor": "#FFFFFF" if header else INK, "fontalignment": "0"}
        runs = [dict(big, field=title_field) if title_field else dict(big, text=static)]
        if subtitle:
            runs += [{"text": "\n"}, {"text": subtitle, "fontsize": 10 if header else 9,
                                      "fontcolor": LILAC if header else MUTED, "fontalignment": "0"}]
        style = {"disable_tooltip": True, "hide_borders": True}
        if header:
            style["background_color"] = NAVY
        if title_field:
            return self.sheet(name, filters, f"Title: {subtitle}" if subtitle else "Title", mark_type="Text",
                              label=title_field, label_runs=runs, style=style)
        return self.sheet(name, filters, static, mark_type="Text", label_runs=runs, style=style)


def text_shelf(sheet_name):
    """Move a sheet's tooltip fields onto the Text shelf (Tableau labels only resolve fields on the Text shelf)."""
    w = T.get_editor().root.find(f".//worksheets/worksheet[@name='{sheet_name}']")
    for enc in w.iter("encodings"):
        for tip in enc.findall("tooltip"):
            tip.tag = "text"


def fix_sizes(node, w, h, direction="vertical"):
    """Give every child a fixed pixel size. Tableau sizes un-fixed tiled zones by their content and ignores
    the relative weights, so the generator works the pixels out once, the same way cwtwb's layout engine does."""
    kids = node.get("children", [])
    if node.get("type") != "container" or not kids:
        return node
    horizontal = node.get("direction") == "horizontal"
    total = w if horizontal else h
    fixed = sum(c["fixed_size"] for c in kids if c.get("fixed_size"))
    flex = [c for c in kids if not c.get("fixed_size")]
    weights = sum(c.get("weight", 1) for c in flex) or 1
    rest = total - fixed
    for i, c in enumerate(kids):
        if not c.get("fixed_size"):
            c["fixed_size"] = round(rest * c.get("weight", 1) / weights)
        size = c["fixed_size"]
        fix_sizes(c, size if horizontal else w, h if horizontal else size)
    if flex:                       # absorb rounding in the last flexible child
        flex[-1]["fixed_size"] += total - sum(c["fixed_size"] for c in kids)
    return node


def ws(name, **kw):
    """Worksheet zone that fills its space (Tableau "Entire View"), with the sheet title hidden."""
    return {"type": "worksheet", "name": name, "show_title": False, "fit": "entire", **kw}


def static_title(title, subtitle=""):
    """Title as a text zone, for charts whose title has no number that a filter could change."""
    runs = [{"text": title + ("\n" if subtitle else ""), "bold": True, "font_size": "10", "font_color": INK, "font_alignment": "0"}]
    if subtitle:
        runs.append({"text": subtitle, "font_size": "9", "font_color": MUTED, "font_alignment": "0"})
    return {"type": "text", "runs": runs}


def block(title_sheet, chart_sheet, weight=1, title_h=58):
    """A chart with its title above it: a title sheet name, or a static_title() text zone."""
    top = dict(title_sheet, fixed_size=title_h) if isinstance(title_sheet, dict) else ws(title_sheet, fixed_size=title_h)
    return {"type": "container", "direction": "vertical", "weight": weight, "children": [top, ws(chart_sheet, weight=1)]}


def nav_bar(pages, current):
    """Placeholder text zones; finish_navigation() turns them into buttons."""
    return [{"type": "text", "fixed_size": 118, "text": f"{NAV_PREFIX}{p}|{label}|{int(p == current)}"} for p, label in pages]


def finish_navigation(editor, active="#682EFF", idle="#030734"):
    """Convert NAV placeholders into navigation buttons now that every dashboard window exists."""
    n = 0
    for zone in editor.root.iter("zone"):
        ft = zone.find("formatted-text")
        run = ft.find("run") if ft is not None else None
        if run is None or not (run.text or "").startswith(NAV_PREFIX):
            continue
        _, target, caption, is_current = run.text.split("|")
        zone.remove(ft)
        for attr in ("type-v2", "forceUpdate"):
            zone.attrib.pop(attr, None)
        node = FlexNode({"type": "navigation_button", "target_dashboard": target, "caption": caption,
                         "background_color": active if is_current == "1" else idle, "font_color": "#FFFFFF",
                         "bold": is_current == "1"})
        _render_navigation_button(node, zone, {"editor": editor})
        n += 1
    return n


def save_layout(path: Path, tree: dict, w: int = 1400, h: int = 900) -> str:
    fix_sizes(tree, w, h)
    path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)
