---
name: show-notion-file
description: Use when the user says "show the notion file" / "build a page for this notion file" / "turn this csv into a notion-style page", referring to a .csv (or folder) produced by the download-notion-file skill. Reads that file's notation and renders it back out as a styled, self-contained HTML page that looks like an exported Notion page.
---

# Show Notion File

Undo the `download-notion-file` skill: take a `.csv` it produced (following
the notation in `assets/notionDownloadTemplate.csv`) and render it back out
as a single rounded-corner HTML page that looks like the original Notion
page, in the style of `assets/exportTemplateNotion.pdf` (a mockup of what an
exported Notion page should look like: a serif-leaning bold title/subtitle,
justified body paragraphs, a zebra-striped table with a bold header row,
inline color highlights, blue links, and side-by-side columns — all inside
one big rounded white card).

This is the `download-notion-file` skill's mirror image, the same way
`show-email` mirrors `download-email`: `build_notion_csv.py` encodes a
Notion page into the notation; `build_notion_html.py` (this skill) decodes
that notation back into a page people can actually look at.

## 1. Identify the target file

The user will name a `.csv` file (e.g. `Job Application Form -
Responses.csv`) or a folder `download-notion-file` created when the page had
embedded files (containing `<folder>.csv` plus an `assets/` subfolder).
Resolve it relative to the current working directory unless they give a
different path. If it's not a `.csv` and isn't a folder containing one, say
so rather than guessing.

## 2. Run the builder script

```bash
python3 ~/.claude/skills/show-notion-file/scripts/build_notion_html.py "<input.csv or folder>"
```

This writes `<basename>.html` next to the CSV (inside the folder, if given a
folder). It re-parses the exact notation `build_notion_csv.py` writes (see
`assets/notionDownloadTemplate.csv` for the legend) and renders it as one
HTML document, with **all styling inline** via `style="..."` attributes —
no `<style>` block, no external stylesheet, no classes — wrapped in a single
`<div>` with large rounded corners, matching the "everything in one
rounded-corner div, inline CSS only" shape of the show-email page.

What it does with each notation element:

- **`ⓣ<font.ttf><##pts><color>`** — becomes that line's `font-family`
  (wrapped in a CSS stack with a generic serif/sans/mono fallback),
  `font-size`, and `color`. A `-Bold`/`-Italic`/`-BoldItalic` suffix on the
  font name becomes `font-weight`/`font-style`; `Courier` becomes a
  monospace stack. Any line at 16pt or larger is also rendered bold even
  without an explicit `-Bold` suffix, since that's how Notion itself
  visually weights headings. 12pt body lines are text-justified (matching
  the PDF reference); headings stay left-aligned.
- **`⊕<#x#>h`** — becomes a real `<table>`: the declared row count of CSV
  rows directly below the marker become that table's rows, a header flag
  renders row 1 bold with a light background, and body rows get a subtle
  zebra stripe.
- **`ⓑ<#RRGGBB>...ⓑ`** — becomes an inline `<span>` with that hex value as
  its background. `download-notion-file` now writes colors as literal hex
  directly (see its SKILL.md's color table), so this is normally a
  pass-through; a bare legacy color name from an older CSV still resolves
  via a small fallback table at the top of the script.
- **`☑T` / `☑F`** — becomes a checked/unchecked checkbox glyph (✓/☐) inline
  before the text.
- **`Ⓛ<url>`** (standalone row) — becomes a bordered link "chip". **`Ⓛ<[text]url>`**
  inline inside a line — becomes a normal in-text `<a>` link, styled blue.
- **`***`** — consecutive bulleted lines become one real `<ul><li>` list.
  An ordered item (bullet + a leading number the download skill wrote into
  the text) is rendered as its own numbered line rather than grouped, since
  the number is already literal text.
- **A blank row** — becomes a small vertical spacer `<div>`.
- **Multiple non-empty cells in one row with no `⊕` marker** — becomes a
  flex row of side-by-side columns; consecutive such rows with the same
  column count are grouped into one multi-column block, each column
  stacking its own cells top-to-bottom, a `None`/empty cell in one column
  just leaves a gap there (matching the template's 2- and 3-column
  examples).

Row width matters for telling a single-column line apart from a
multi-column layout, so this only works correctly on a CSV written by the
current `build_notion_csv.py` (which gives each row exactly the cell count
its own block needs, not padded out to the file's widest row) — if you're
ever handed an older/differently-padded CSV, re-download it with
`download-notion-file` rather than hand-editing padding back out.

**Sizing the card to fit wide content.** The outer rounded `<div>` is sized
`width:100%` up to a generous `max-width:1600px`, wide enough that a normal
multi-column table (e.g. an 11-property database) fits without spilling
outside the rounded corners — that used to happen with an older, narrower
fixed card width. On top of that, every table gets its own
`overflow-x:auto` wrapper and every cell gets `word-break`/`overflow-wrap`
so long unbreakable tokens (URLs, emails) wrap instead of forcing the table
wider than its container, as a last-resort guard for anything wider than
even the 1600px card. If a table still visibly overflows the card after
running this script, that means its content is wider than 1600px even
wrapped — widen the `max-width` in `build_html()` rather than changing
anything else.

## 3. Embedded files

If the input was a folder with an `assets/` subfolder (images/files the
download skill saved), the HTML's own image/file references already point
at those existing relative paths — no re-linking needed.

## 4. Sanity-check and report

Skim the produced HTML (or check tag balance) to confirm the title/table/
highlights came through and no stray `ⓣ`/`⊕`/`Ⓛ` glyphs leaked into the
visible text — that usually means a row's notation didn't match the
expected pattern (e.g. a hand-edited CSV cell).

Tell the user, briefly:
- The path to the HTML file written.
- Whether any rows fell back to plain text because their notation couldn't
  be parsed.
