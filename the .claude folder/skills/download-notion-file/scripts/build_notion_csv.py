#!/usr/bin/env python3
"""
Build a .csv file that follows the notionDownloadTemplate.csv notation
(see ../assets/notionDownloadTemplate.csv) from a structured JSON description
of one Notion page.

Usage:
    python3 build_notion_csv.py input.json output.csv

-----------------------------------------------------------------------------
Notation this script emits (the legend from notionDownloadTemplate.csv):

  ⓣ<fontname.ttf><##pts><#RRGGBB> plain-text run: font, point size, text color
  ⊕<#x#>  or  ⊕<#x#>h             starts a table/database: cols x rows,
                                   trailing "h" = row 1 is a header row
  ⓑ<#RRGGBB> ... ⓑ                background/highlight color span; appears
                                   twice in a row to switch directly to a new
                                   highlight color
  ☑T / ☑F                         checked / unchecked checkbox
  Ⓛ<url>                          a standalone link
  Ⓛ<[display text]url>            a link with custom display text, inline
  ***                             this line is a bullet (or numbered) item
  (blank row)                     blank line / empty space
  multiple non-empty columns      side-by-side column layout (no ⊕ marker)
  blank cell inside a ⊕ table     an intentionally empty/skipped cell

Governing rule used to decide row boundaries: each CSV row holds exactly one
ⓣ tag, so it represents one *uniform-style* run of text (same font/bold/
italic/size/color). Split into a new row whenever:
  - there's a manual line break in the source text, or
  - the font/bold/italic/size/color actually changes.
A background highlight is the one exception — it can change *within* a row
via the repeatable ⓑ<color> marker, since that's explicitly supported.

-----------------------------------------------------------------------------
Input JSON schema:

{
  "rows": [
    {"type": "blank"},

    {"type": "line", "columns": [cell, cell, ...]},
    # 1 cell = a normal single-column line.
    # >1 cells = a side-by-side column layout at this row position (use
    # null for a column that has no content on this particular row).

    {"type": "bookmark", "columns": [bookmark_or_null, ...]},
    # a standalone link block (no font tag), bookmark = {"url": "..."}

    {"type": "table_start", "cols": 3, "rows": 2, "header": true},
    # declares a table/database immediately followed by exactly `rows`
    # "table_row" entries, each with up to `cols` cells.

    {"type": "table_row", "cells": [cell_or_null, ...]}
  ]
}

cell = {
  "font": "Helvetica",        # base family name, no extension (optional)
  "bold": false,
  "italic": false,
  "code": false,               # monospace override (inline code / code block)
  "size": 12,                  # point size for this line
  "color": "#000000",          # text color as a literal hex string
  "bullet": false,              # prefix *** (bulleted or numbered list item)
  "ordered_index": null,        # int -> writes "N. " before the text
  "checkbox": null,             # null (not a to-do) | true | false
  "background": "#FBE4E4",      # OPTIONAL whole-line highlight color, hex
  "spans": [                    # the actual text, as background/link spans
     {"text": "...", "background": null, "link": null},
     {"text": "...", "background": "#FBF3DB",
      "link": {"url": "https://x.com", "text": "click here"}}
  ]
  # "spans" may be omitted in favor of a flat "text" field when there's no
  # per-span background/link variation: {"text": "plain text ..."}
}

Suggested size convention (Notion has no real per-run font data, so this is
a documented convention, not extracted fact): page title / heading_1 = 24,
heading_2 = 20, heading_3 = 16, body text / list items / to-dos / table
cells = 12. Bold/italic/code are folded into the font filename itself
(e.g. "Helvetica-BoldItalic.ttf", "Courier.ttf" for code) since the template
has no separate symbol for them.

Both "color" and "background" must already be literal hex strings
("#RRGGBB") by the time they reach this script -- it does no name lookup of
its own. Converting a Notion color name (a rich-text annotations.color, or a
select/status option's "color" field) to its hex value is the caller's job;
see the color table in download-notion-file's SKILL.md.
"""
import csv
import json
import sys

DEFAULT_FONT = "Helvetica"
DEFAULT_SIZE = 12
DEFAULT_COLOR = "#000000"


def _font_filename(cell):
    font = cell.get("font") or DEFAULT_FONT
    if cell.get("code"):
        font = "Courier"
    bold = bool(cell.get("bold"))
    italic = bool(cell.get("italic"))
    suffix = ""
    if bold and italic:
        suffix = "-BoldItalic"
    elif bold:
        suffix = "-Bold"
    elif italic:
        suffix = "-Italic"
    return f"{font}{suffix}.ttf"


def _text_color(cell):
    """Returns this cell's text color as a literal hex string, e.g.
    '#E03E3E'. The caller is responsible for converting a Notion color name
    (annotations.color, or a select/status option's color) to its hex value
    before building the JSON -- see the color table in download-notion-file's
    SKILL.md. This function just passes the hex straight through."""
    return cell.get("color") or DEFAULT_COLOR


def _render_spans(cell):
    spans = cell.get("spans")
    if spans is None:
        spans = [{"text": cell.get("text", "")}]

    parts = []
    current_bg = None
    for span in spans:
        text = span.get("text", "")
        link = span.get("link")
        if link:
            url = link.get("url", "")
            display = link.get("text")
            text = f"Ⓛ<[{display}]{url}>" if display and display != url else f"Ⓛ<{url}>"

        bg = span.get("background") or None
        if bg != current_bg:
            if current_bg is not None:
                parts.append("ⓑ")
            if bg is not None:
                parts.append(f"ⓑ<{bg}>")
            current_bg = bg
        parts.append(text)

    if current_bg is not None:
        parts.append("ⓑ")
    return "".join(parts)


def render_cell(cell):
    """Render one 'cell' object into its full ⓣ-tagged notation string."""
    if cell is None:
        return ""

    size = cell.get("size", DEFAULT_SIZE)
    tag = f"ⓣ<{_font_filename(cell)}><{size}pts><{_text_color(cell)}>"

    whole_line_bg = cell.get("background")
    prefix = ""
    checkbox = cell.get("checkbox")
    if checkbox is True:
        prefix += "☑T "
    elif checkbox is False:
        prefix += "☑F "
    if cell.get("bullet"):
        prefix += "*** "
    if cell.get("ordered_index") is not None:
        prefix += f"{cell['ordered_index']}. "

    body = _render_spans(cell)
    if whole_line_bg and cell.get("spans") is None:
        # Simple whole-line highlight with no per-span background given.
        body = f"ⓑ<{whole_line_bg}>{body}ⓑ"

    return tag + prefix + body


def render_bookmark(bookmark):
    if not bookmark:
        return ""
    return f"Ⓛ<{bookmark.get('url', '')}>"


def build_rows(data):
    out_rows = []
    pending_table = None  # (cols, remaining_data_rows)

    for row in data.get("rows", []):
        rtype = row.get("type")

        if rtype == "blank":
            out_rows.append([""])

        elif rtype == "line":
            out_rows.append([render_cell(c) for c in row.get("columns", [])])

        elif rtype == "bookmark":
            out_rows.append([render_bookmark(b) for b in row.get("columns", [])])

        elif rtype == "table_start":
            cols = row["cols"]
            rows_count = row["rows"]
            header = bool(row.get("header"))
            marker = f"⊕<{cols}x{rows_count}>" + ("h" if header else "")
            out_rows.append([marker])
            pending_table = [cols, rows_count]

        elif rtype == "table_row":
            cells = row.get("cells", [])
            if pending_table is not None:
                cols, remaining = pending_table
                cells = (cells + [None] * cols)[:cols]
                pending_table[1] = remaining - 1
                if pending_table[1] <= 0:
                    pending_table = None
            out_rows.append([render_cell(c) for c in cells])

        else:
            raise ValueError(f"Unknown row type: {rtype}")

    # Deliberately NOT padded to a uniform column count: each row keeps
    # exactly the cell count its own block needs (1 for a plain text line,
    # N for an N-column table/parallel-column row). A reader (e.g.
    # show-notion-file's build_notion_html.py) relies on a row's actual
    # cell count to tell a single-column line apart from a side-by-side
    # column layout -- padding every row out to the file's widest row
    # (e.g. a wide table elsewhere in the same document) would make that
    # undecidable.
    return out_rows


def main():
    if len(sys.argv) != 3:
        print("Usage: build_notion_csv.py input.json output.csv", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = build_rows(data)

    with open(sys.argv[2], "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"Wrote {sys.argv[2]} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
