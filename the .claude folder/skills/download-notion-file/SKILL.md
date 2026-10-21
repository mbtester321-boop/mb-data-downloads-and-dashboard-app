---
name: download-notion-file
description: Use when the user says "download notion file" / "download this notion page" / "save this notion page as a csv" (referring to a specific Notion page, open or identified by title/link). Converts the page's full content into a .csv file using the notation defined in assets/notionDownloadTemplate.csv, preserving text, fonts/sizes/colors, highlights, checkboxes, links, bullets, tables/databases, and column layouts.
---

# Download Notion File

Save one Notion page to a local `.csv` file (plus a sibling `assets/` folder
for any embedded images/files) that encodes the page's content and visual
structure using a fixed symbol notation. Read
`assets/notionDownloadTemplate.csv` once per session if you haven't already
— it's the canonical legend for every symbol this skill emits.

Use the Notion MCP tools (`notion-search`, `notion-fetch`, and, if attachments
are involved, `notion-get-file-download-urls` / `notion-download-attachment`)
to get the real page content — never ask the user to paste it manually
unless those tools are unavailable. These tools are deferred; load them with
`ToolSearch("select:mcp__claude_ai_Notion__notion-fetch,mcp__claude_ai_Notion__notion-search,mcp__claude_ai_Notion__notion-get-file-download-urls,mcp__claude_ai_Notion__notion-download-attachment")`
before calling them.

## 0. Identify the target page

- If the user gave a Notion URL or pasted page content already, use that
  directly.
- If they named a page by title, `notion-search` for it and confirm the
  match if there's ambiguity (multiple similarly-named pages).
- Fetch the full content with `notion-fetch`.

## 1. The governing rule for turning content into rows

**Every CSV row holds exactly one `ⓣ` tag**, so each row is one
*uniform-style run* of text (same font/bold/italic/size/color). Start a new
row whenever:
- there's a manual line break in the source text, or
- the font/bold/italic/size/color actually changes mid-line.

A background highlight is the one thing that's allowed to change *within* a
row, because the `ⓑ<color>` marker is explicitly repeatable (see the legend
row that says "twice implies the highlight is new for the new area").

A completely empty line in the source becomes a blank CSV row.

## 2. Map Notion content to the notation

Notion's API doesn't expose real per-run font families or point sizes, so
this skill uses a fixed, documented convention (not extracted fact) for
`<##pts>`, and folds bold/italic/code into the font filename itself since
the template has no separate symbol for them:

| Notion element | `<##pts>` | font filename |
|---|---|---|
| Page title / `heading_1` | 24 | `Helvetica.ttf` |
| `heading_2` | 20 | `Helvetica.ttf` |
| `heading_3` | 16 | `Helvetica.ttf` |
| paragraph / list item / to-do / table cell / quote / callout | 12 | `Helvetica.ttf` |
| bold run | (as above) | `Helvetica-Bold.ttf` |
| italic run | (as above) | `Helvetica-Italic.ttf` |
| bold+italic run | (as above) | `Helvetica-BoldItalic.ttf` |
| inline code / code block | 12 | `Courier.ttf` (overrides bold/italic naming) |

Other mappings:
- **Color — always written as a literal hex string (`#RRGGBB`), never a
  color name.** Notion's own color names (`annotations.color` on rich text,
  or a select/status option's `color` field) must be converted to hex before
  they go into the JSON's `"color"`/`"background"` fields — the builder
  script does no name lookup itself. Use this table (Notion's approximate
  palette; text colors are the saturated value, background/highlight colors
  are the pastel value used for highlighted text *and* for select/status
  pill backgrounds):

  | Notion name | text hex | background/highlight hex |
  |---|---|---|
  | default / black | `#000000` | — |
  | gray | `#9B9A97` | `#EBECED` |
  | brown | `#64473A` | `#E9E5E3` |
  | orange | `#D9730D` | `#FAEBDD` |
  | yellow | `#DFAB01` | `#FBF3DB` |
  | green | `#0F7B6C` | `#DDEDEA` |
  | blue | `#0B6E99` | `#DDEBF1` |
  | purple | `#6940A5` | `#EAE4F2` |
  | pink | `#AD1A72` | `#F4DFEB` |
  | red | `#E03E3E` | `#FBE4E4` |

  A `*_background` annotation (e.g. `yellow_background`) is a **highlight**,
  not a text color: wrap that span in `ⓑ<#FBF3DB>...ⓑ` using the
  background-hex column above, leave the cell's own `"color"` as the normal
  text hex.
- **Bulleted list item** → `bullet: true` (prefixes `***`).
- **Numbered list item** → also use `bullet: true`, but additionally set
  `ordered_index` to that item's 1-based position within its list (computed
  by you, since Notion's content doesn't carry the rendered number) — the
  template has no separate ordered-list symbol, so the number is written
  into the text itself (`"1. "`) alongside the `***` marker.
- **To-do block** → `checkbox: true` (checked) or `checkbox: false`
  (unchecked).
- **Link** — a standalone bookmark/embed block becomes its own row:
  `{"type": "bookmark", "columns": [{"url": "..."}]}` → renders as
  `Ⓛ<url>` with no font tag. A link *inside* a line of text becomes a span
  with `"link": {"url": "...", "text": "display text"}` → renders inline as
  `Ⓛ<[display text]url>`.
- **Table / simple table block** → one `table_start` row (`cols`, `rows`,
  `header`) immediately followed by exactly that many `table_row` entries.
  An empty/merged cell is `null` — don't invent filler text for it.
- **Database (full database, not just a simple table)** → flatten each
  database row into a table row the same way, with property names as the
  header row:
  - title / rich text → plain text
  - number → the number as text
  - select / status → the option's name, **with that cell's `"background"`
    set to the option's own `color` (converted via the table above)** — in
    Notion's UI these render as a colored pill/badge, so the cell needs the
    highlight wrapper (`ⓑ<#hex>...ⓑ`) even though the data itself is just
    the option name. Use the option's text-hex column for `"color"` too, so
    the badge reads as colored text on its pastel background, matching how
    Notion actually displays it.
  - multi-select → option names joined with `"; "`, each run its own span
    with its own option's background/color the same way (a multi-select
    cell can show several different-colored pills in one cell).
  - date → written out in full words, e.g. `"October 1, 2026"` (include a
    range with an en dash if the property has an end date)
  - checkbox → `☑T` / `☑F` inside that cell
  - person/people → display name(s) joined with `"; "`
  - relation → related page title(s) joined with `"; "`
  - url → `Ⓛ<url>` inside the cell
  - empty property → leave the cell blank (this is explicitly called out in
    the template: skip it, don't write anything)
- **Side-by-side columns** (`column_list`/`column` blocks) → a `"line"` row
  with multiple entries in `"columns"`, one per visual column, aligned by
  row position; use `null` for a column with nothing on that row (see the
  template's own 2-and-3-column examples).
- **Divider / toggle block** → no symbol is defined for these; use a blank
  row for a divider, and for a toggle just emit its heading line followed by
  its children's lines in normal order (nesting/indentation isn't
  represented — this is a known limitation, not a bug).
- **Images, files, and other embeds** → the template defines no symbol for
  these, but dropping the data silently isn't acceptable either. Download
  the real file (see step 4) into `<output>/assets/`, and represent its
  position in the page as a bookmark row pointing at the local relative
  path: `Ⓛ<assets/filename.ext>`.

## 3. Build the intermediate JSON, then the CSV

Write a JSON file matching the schema at the top of
`scripts/build_notion_csv.py` (one entry in `"rows"` per table_start/
table_row/line/bookmark/blank — do this directly from what `notion-fetch`
returned, applying the mapping above), then run:

```bash
python3 ~/.claude/skills/download-notion-file/scripts/build_notion_csv.py <input.json> "<output>.csv"
```

Use the script — not hand-typed CSV — because the symbol glyphs and the
quoting rules (a cell containing a comma must be quoted; Python's `csv`
module does this automatically) are easy to get subtly wrong by hand.

Sanity-check the result once per session by reading a few lines back and
comparing them against `assets/notionDownloadTemplate.csv`'s legend.

## 4. Download embedded files (if any)

For every image/file block in the page, use `notion-get-file-download-urls`
/ `notion-download-attachment` to fetch the real bytes and write them into
`<output>/assets/<filename>`, sanitizing the filename (strip `/`, `..`, null
bytes). If a file can't be downloaded through these tools, say so plainly
rather than silently skipping it.

## 5. Decide the output location

- If the page has no embedded files to save: write a single
  `<Sanitized Page Title>.csv` in the current working directory.
- If it does: create a folder `<Sanitized Page Title>/` containing
  `<Sanitized Page Title>.csv` and the `assets/` subfolder.

Sanitize the title for the filesystem (replace `/`, `:`, quotes, etc. with
`-`). If a file/folder with that exact name already exists, ask before
overwriting.

## 6. Report back

Tell the user, briefly:
- The file (or folder) path created
- How many rows were written and whether any tables/databases were included
- Any embedded file that couldn't be auto-downloaded, and why
- Any content that had to fall back to a documented limitation (nested
  toggles, dividers, etc.)
