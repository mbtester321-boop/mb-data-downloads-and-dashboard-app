#!/usr/bin/env python3
"""
Build a styled, self-contained HTML page from a .csv file produced by the
download-notion-file skill's build_notion_csv.py.

Usage:
    python3 build_notion_html.py <input.csv or folder> [output.html]

<input> is either:
  - a .csv path directly, or
  - a folder (as download-notion-file creates when there are embedded
    files) containing "<folder_basename>.csv" plus an "assets/" subfolder
    of downloaded images/files.

Writes "<basename>.html" next to the csv unless an explicit output path is
given. This is the inverse of build_notion_csv.py: it re-parses the exact
notation documented in notionDownloadTemplate.csv (ⓣ font/size/color runs,
⊕ tables/databases, ⓑ highlight spans, ☑T/☑F checkboxes, Ⓛ links, ***
bullets, blank rows, multi-column rows) and renders it back out as HTML
styled to resemble a real exported Notion page (see assets/
exportTemplateNotion.pdf for the visual reference this aims to match):
a single rounded-corner card, serif-leaning body text, justified
paragraphs, a zebra-striped table with a bold header row, inline color
highlights, and side-by-side columns.

All CSS is inline (style="..." attributes) -- there is no <style> block or
external stylesheet, matching how this skill's sibling show-email renders
email.rtf back to HTML.
"""
import csv
import html
import os
import re
import sys

# ---------------------------------------------------------------------------
# build_notion_csv.py now writes "color"/"background" as literal hex
# strings ("#RRGGBB") directly -- see download-notion-file's SKILL.md color
# table. These name->hex maps are kept only as a fallback for CSVs written
# by an older version of that script that used bare Notion color names.
# ---------------------------------------------------------------------------
TEXT_COLORS = {
    "black": "#191919", "default": "#191919",
    "gray": "#9B9A97", "brown": "#64473A", "orange": "#D9730D",
    "yellow": "#DFAB01", "green": "#0F7B6C", "blue": "#0B6E99",
    "purple": "#6940A5", "pink": "#AD1A72", "red": "#E03E3E",
}
BACKGROUND_COLORS = {
    "gray": "#EBECED", "brown": "#E9E5E3", "orange": "#FAEBDD",
    "yellow": "#FBF3DB", "green": "#DDEDEA", "blue": "#DDEBF1",
    "purple": "#EAE4F2", "pink": "#F4DFEB", "red": "#FBE4E4",
}
DEFAULT_TEXT_HEX = "#191919"
DEFAULT_BG_HEX = "#EBECED"


def resolve_color(value, fallback_table, default_hex):
    """A hex string passes through unchanged; a bare legacy color name
    (from an older CSV) is looked up in the given fallback table."""
    if not value:
        return default_hex
    if value.startswith("#"):
        return value
    return fallback_table.get(value, default_hex)

CHECK_RE = re.compile(r'^☑([TF]) ')
BULLET_RE = re.compile(r'^\*\*\* ')
ORDERED_RE = re.compile(r'^(\d+)\. ')
CELL_TAG_RE = re.compile(r'^ⓣ<([^>]+)\.ttf><(\d+)pts><([^>]+)>(.*)$', re.S)
TABLE_MARKER_RE = re.compile(r'^⊕<(\d+)x(\d+)>(h)?$')
BARE_BOOKMARK_RE = re.compile(r'^Ⓛ<(.*)>$', re.S)
SPAN_TOKEN_RE = re.compile(
    r'ⓑ<(?P<bgopen>[^>]+)>'
    r'|(?P<bgclose>ⓑ)'
    r'|Ⓛ<\[(?P<linktext>[^\]]*)\](?P<linkurl>[^>]*)>'
    r'|Ⓛ<(?P<bareurl>[^>]*)>'
)


def css_font_family(name):
    lowered = name.lower()
    if any(k in lowered for k in ("courier", "mono", "consolas")):
        return f"'{name}', monospace"
    if any(k in lowered for k in ("times", "georgia", "serif", "garamond", "cambria")):
        return f"'{name}', Georgia, 'Times New Roman', serif"
    return f"'{name}', Georgia, 'Times New Roman', serif"


def parse_font(raw_font):
    """'Helvetica-BoldItalic' -> ('Helvetica', True, True, False);
    'Courier' -> ('Courier', False, False, True)."""
    code = raw_font.lower() == "courier"
    for suffix, bold, italic in (("-BoldItalic", True, True),
                                  ("-Bold", True, False),
                                  ("-Italic", False, True)):
        if raw_font.endswith(suffix):
            return raw_font[: -len(suffix)], bold, italic, code
    return raw_font, False, False, code


def parse_spans(body):
    """Walk ⓑ<color>...ⓑ highlight spans and Ⓛ<...> links, returning a list
    of {'text', 'background', 'link': {'url','text'} or None}."""
    spans = []
    pos = 0
    current_bg = None
    buf = []

    def flush_text():
        if buf:
            spans.append({"text": "".join(buf), "background": current_bg, "link": None})
            buf.clear()

    for m in SPAN_TOKEN_RE.finditer(body):
        literal = body[pos:m.start()]
        if literal:
            buf.append(literal)
        if m.group("bgopen") is not None:
            flush_text()
            current_bg = m.group("bgopen")
        elif m.group("bgclose") is not None:
            flush_text()
            current_bg = None
        elif m.group("linkurl") is not None:
            flush_text()
            spans.append({"text": "", "background": current_bg,
                          "link": {"url": m.group("linkurl"), "text": m.group("linktext")}})
        elif m.group("bareurl") is not None:
            flush_text()
            spans.append({"text": "", "background": current_bg,
                          "link": {"url": m.group("bareurl"), "text": None}})
        pos = m.end()
    tail = body[pos:]
    if tail:
        buf.append(tail)
    flush_text()
    return spans


def parse_cell(raw):
    """Parse one ⓣ-tagged CSV cell into a structured dict, or None for an
    empty/skipped cell."""
    raw = raw.strip("﻿")
    if raw == "":
        return None

    m = CELL_TAG_RE.match(raw)
    if not m:
        # Not a ⓣ-tagged cell (shouldn't normally happen outside bookmarks,
        # which are handled separately) -- treat as plain literal text.
        return {"font": "Helvetica", "bold": False, "italic": False, "code": False,
                "size": 12, "color": DEFAULT_TEXT_HEX, "checkbox": None, "bullet": False,
                "ordered_index": None, "spans": [{"text": raw, "background": None, "link": None}]}

    font_raw, size_raw, color, rest = m.groups()
    font, bold, italic, code = parse_font(font_raw)
    size = int(size_raw)

    checkbox = None
    cm = CHECK_RE.match(rest)
    if cm:
        checkbox = cm.group(1) == "T"
        rest = rest[cm.end():]

    bullet = False
    if BULLET_RE.match(rest):
        bullet = True
        rest = rest[BULLET_RE.match(rest).end():]

    ordered_index = None
    om = ORDERED_RE.match(rest)
    if om:
        ordered_index = int(om.group(1))
        rest = rest[om.end():]

    return {
        "font": font, "bold": bold, "italic": italic, "code": code, "size": size,
        "color": color, "checkbox": checkbox, "bullet": bullet,
        "ordered_index": ordered_index, "spans": parse_spans(rest),
    }


def parse_csv_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return [row for row in csv.reader(f)]


def group_blocks(raw_rows):
    """Turn the raw CSV rows into a list of blocks: {'kind': 'blank'},
    {'kind': 'columns', 'columns': [cell_or_None, ...]},
    {'kind': 'bookmark', 'columns': [url_or_None, ...]},
    {'kind': 'table', 'cols': N, 'header': bool, 'rows': [[cell_or_None,...]]}."""
    blocks = []
    i = 0
    n = len(raw_rows)
    while i < n:
        row = raw_rows[i]
        non_empty = [c for c in row if c.strip()]

        if not non_empty:
            blocks.append({"kind": "blank"})
            i += 1
            continue

        if len(non_empty) == 1:
            tm = TABLE_MARKER_RE.match(non_empty[0])
            if tm:
                cols, table_rows, header = int(tm.group(1)), int(tm.group(2)), bool(tm.group(3))
                data_rows = []
                i += 1
                for _ in range(table_rows):
                    if i >= n:
                        break
                    r = (raw_rows[i] + [""] * cols)[:cols]
                    data_rows.append([parse_cell(c) for c in r])
                    i += 1
                blocks.append({"kind": "table", "cols": cols, "header": header, "rows": data_rows})
                continue

            bm = BARE_BOOKMARK_RE.match(non_empty[0])
            if bm and not non_empty[0].startswith("ⓣ"):
                idx = row.index(non_empty[0])
                cols_out = [None] * len(row)
                cols_out[idx] = bm.group(1)
                blocks.append({"kind": "bookmark", "columns": cols_out})
                i += 1
                continue

        blocks.append({"kind": "columns", "columns": [parse_cell(c) for c in row]})
        i += 1

    return blocks


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_spans_html(spans):
    out = []
    for span in spans:
        link = span.get("link")
        if link:
            label = html.escape(link["text"]) if link.get("text") else html.escape(link["url"])
            piece = (f'<a href="{html.escape(link["url"])}" target="_blank" '
                      f'style="color:#0B6E99; text-decoration:none; border-bottom:1px solid #0B6E99;">{label}</a>')
        else:
            piece = html.escape(span.get("text", "")).replace("\n", "<br>")
        bg = span.get("background")
        if bg:
            bg_hex = resolve_color(bg, BACKGROUND_COLORS, DEFAULT_BG_HEX)
            piece = f'<span style="background:{bg_hex}; border-radius:3px; padding:0 2px;">{piece}</span>'
        out.append(piece)
    return "".join(out)


def cell_style(cell, base_align=None):
    font_css = css_font_family(cell["font"])
    weight = "700" if (cell["bold"] or cell["size"] >= 16) else "400"
    style = (f"font-family:{font_css}; font-size:{cell['size']}pt; "
             f"color:{resolve_color(cell['color'], TEXT_COLORS, DEFAULT_TEXT_HEX)}; "
             f"font-weight:{weight}; word-break:break-word; overflow-wrap:anywhere;")
    if cell["italic"]:
        style += " font-style:italic;"
    if base_align:
        style += f" text-align:{base_align};"
    return style


def checkbox_glyph(checkbox):
    if checkbox is True:
        return '<span style="color:#0F7B6C;">&#9745;</span> '
    if checkbox is False:
        return '<span style="color:#9B9A97;">&#9744;</span> '
    return ""


def render_cell_inline(cell):
    if cell is None:
        return ""
    prefix = checkbox_glyph(cell["checkbox"])
    body = render_spans_html(cell["spans"])
    if cell["ordered_index"] is not None:
        prefix += f"{cell['ordered_index']}. "
    return prefix + body


def render_line(cell, out):
    if cell is None:
        return
    align = "justify" if cell["size"] <= 12 and not cell["bullet"] else "left"
    style = cell_style(cell, align)
    out.append(f'    <div style="{style} line-height:1.6; margin:0 0 16px 0;">\n'
               f'      {render_cell_inline(cell)}\n'
               f'    </div>\n')


def render_bullet_group(cells, out):
    first = cells[0]
    style = cell_style(first)
    items = "".join(f"      <li>{render_cell_inline(c)}</li>\n" for c in cells)
    out.append(f'    <ul style="{style} line-height:1.6; margin:0 0 16px 0; padding-left:1.4em;">\n'
               f'{items}    </ul>\n')


def render_table(block, out):
    """A table is wrapped in its own horizontally-scrolling div. The card
    around it is sized generously (see build_html) so this scrollbar should
    rarely be needed in practice -- it's the last-resort guard that keeps a
    table from ever visually bursting out through the card's rounded
    corners, which is what a fixed, too-narrow card width used to cause."""
    cols, header, rows = block["cols"], block["header"], block["rows"]
    out.append('    <div style="overflow-x:auto; border-radius:8px; margin:0 0 20px 0;">\n')
    out.append('      <table style="border-collapse:collapse; width:100%; table-layout:auto; '
                'font-size:11pt; font-family:Helvetica, Arial, sans-serif;">\n')
    for r_i, row in enumerate(rows):
        is_header = header and r_i == 0
        tag = "th" if is_header else "td"
        if is_header:
            row_style = "background:#F7F6F3; font-weight:700;"
        else:
            row_style = "background:#FBFBFA;" if r_i % 2 == 0 else "background:#FFFFFF;"
        out.append(f'        <tr style="{row_style}">\n')
        for c_i in range(cols):
            cell = row[c_i] if c_i < len(row) else None
            cell_css = ("border-bottom:1px solid #EBECED; padding:8px 14px; text-align:left; "
                        "vertical-align:top; word-break:break-word; overflow-wrap:anywhere;")
            if cell is not None:
                font_css = css_font_family(cell["font"])
                cell_css += f" font-family:{font_css}; color:{resolve_color(cell['color'], TEXT_COLORS, DEFAULT_TEXT_HEX)};"
                if cell["italic"]:
                    cell_css += " font-style:italic;"
            out.append(f'          <{tag} style="{cell_css}">{render_cell_inline(cell)}</{tag}>\n')
        out.append('        </tr>\n')
    out.append('      </table>\n')
    out.append('    </div>\n')


def render_columns_group(column_rows, n_cols, out):
    """column_rows is a list of 'columns' blocks (each with len == n_cols)
    that ran consecutively; render as n_cols side-by-side flex columns, each
    stacking its cells top-to-bottom in order."""
    out.append(f'    <div style="display:flex; gap:32px; margin:0 0 16px 0;">\n')
    for c_i in range(n_cols):
        out.append(f'      <div style="flex:1 1 0; min-width:0;">\n')
        for block in column_rows:
            cell = block["columns"][c_i] if c_i < len(block["columns"]) else None
            if cell is None:
                continue
            inner = []
            render_line(cell, inner)
            # indent nested lines to line up with this column's own markup
            out.append("        " + "".join(inner))
        out.append('      </div>\n')
    out.append('    </div>\n')


def render_bookmark(block, out):
    for url in block["columns"]:
        if not url:
            continue
        out.append(f'    <div style="margin:0 0 16px 0;">\n'
                   f'      <a href="{html.escape(url)}" target="_blank" '
                   f'style="display:inline-block; max-width:100%; padding:10px 14px; border:1px solid #EBECED; '
                   f'border-radius:6px; color:#0B6E99; text-decoration:none; font-family:Helvetica, Arial, sans-serif; '
                   f'word-break:break-word; overflow-wrap:anywhere;">'
                   f'{html.escape(url)}</a>\n    </div>\n')


def render_blocks(blocks):
    out = []
    i = 0
    n = len(blocks)
    while i < n:
        b = blocks[i]

        if b["kind"] == "blank":
            out.append('    <div style="height:12px;"></div>\n')
            i += 1
            continue

        if b["kind"] == "bookmark":
            render_bookmark(b, out)
            i += 1
            continue

        if b["kind"] == "table":
            render_table(b, out)
            i += 1
            continue

        if b["kind"] == "columns":
            n_cols = len(b["columns"])
            if n_cols > 1:
                run = [b]
                j = i + 1
                while j < n and blocks[j]["kind"] == "columns" and len(blocks[j]["columns"]) == n_cols:
                    run.append(blocks[j])
                    j += 1
                render_columns_group(run, n_cols, out)
                i = j
                continue

            # single-column lines: group consecutive bullet lines into one <ul>
            cell = b["columns"][0]
            if cell is not None and cell["bullet"] and cell["ordered_index"] is None:
                run_cells = [cell]
                j = i + 1
                while (j < n and blocks[j]["kind"] == "columns" and len(blocks[j]["columns"]) == 1
                       and blocks[j]["columns"][0] is not None
                       and blocks[j]["columns"][0]["bullet"]
                       and blocks[j]["columns"][0]["ordered_index"] is None):
                    run_cells.append(blocks[j]["columns"][0])
                    j += 1
                render_bullet_group(run_cells, out)
                i = j
                continue

            render_line(cell, out)
            i += 1
            continue

        i += 1

    return "".join(out)


def build_html(title, body_html):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title) or "Notion Page"}</title>
</head>
<body style="margin:0; background:#F7F6F3;">
<div style="background:#F7F6F3; margin:0; padding:60px 20px; min-height:100vh; box-sizing:border-box; display:flex; justify-content:center; align-items:flex-start; font-family:Georgia, 'Times New Roman', serif;">
  <div style="background:#ffffff; border-radius:40px; max-width:1600px; width:100%; padding:56px 64px; box-sizing:border-box; color:#191919; box-shadow:0 20px 60px rgba(0,0,0,0.12);">
{body_html}  </div>
</div>
</body>
</html>
'''


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: build_notion_html.py <input.csv or folder> [output.html]", file=sys.stderr)
        sys.exit(1)

    src = os.path.abspath(sys.argv[1])
    if os.path.isdir(src):
        base = os.path.basename(src.rstrip("/"))
        csv_path = os.path.join(src, f"{base}.csv")
        out_dir = src
    else:
        csv_path = src
        out_dir = os.path.dirname(src)
        base = os.path.splitext(os.path.basename(src))[0]

    if not os.path.isfile(csv_path):
        print(f"No CSV found at {csv_path}", file=sys.stderr)
        sys.exit(1)

    out_path = sys.argv[2] if len(sys.argv) == 3 else os.path.join(out_dir, f"{base}.html")

    raw_rows = parse_csv_rows(csv_path)
    blocks = group_blocks(raw_rows)
    body_html = render_blocks(blocks)
    html_doc = build_html(base, body_html)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
