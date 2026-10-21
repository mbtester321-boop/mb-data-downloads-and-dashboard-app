# How to read the downloaded Notion data

Each downloaded Notion page lives here as:

| File | What it is |
|---|---|
| `<Page Title>.csv` | **The actual downloaded data** — the page's content and visual structure (text, fonts, colors, highlights, checkboxes, links, tables/databases, columns) encoded in the fixed notation described below. This is the file to read for the raw local copy of the page. |
| `<Page Title>.html` | An auto-generated preview page (built from the `.csv`) used by the dashboard website to show a live rendering of the page in the browser. Not part of the raw downloaded format itself. |
| `<screenshot>.png` | A screenshot of the real page in Notion, for side-by-side comparison. |

`notionDownloadTemplate.csv` in this folder is the **blank template/legend** — it is not a real page, it's the pattern every downloaded `.csv` follows.

## Opening a page's `.csv` file

It's a plain CSV — open it in Excel/Numbers/Google Sheets, or read it as text; every row is one line of the original page, column A holding the content and columns B/C used only for table/database cells and side-by-side columns.

## The governing rule

**Every CSV row holds exactly one `ⓣ` (text-run) tag.** A new row starts whenever there's a manual line break in the source, or the font/bold/italic/size/color actually changes mid-line. A completely blank line in the original page becomes a blank CSV row.

## Symbol legend

| Symbol | Meaning |
|---|---|
| `ⓣ<FontName.ttf><NNpts><#RRGGBB>` | Starts a run of text: font file, point size, and text color (always a `#RRGGBB` hex, never a color name). Point size follows a fixed convention: 24pt = page title/H1, 20pt = H2, 16pt = H3, 12pt = everything else (paragraphs, list items, to-dos, table cells, quotes, callouts). Bold/italic are folded into the filename (`Helvetica-Bold.ttf`, etc.); code uses `Courier.ttf`. |
| `ⓑ<#RRGGBB> ... ⓑ` | The text between two `ⓑ` markers has a background highlight of that color (used for Notion's highlighted text *and* for colored select/status "pill" badges in table/database cells). |
| `☑T` / `☑F` | A checked / unchecked to-do checkbox. |
| `***` | Marks a bulleted (or numbered — the number is written directly into the text, e.g. `"1. "`) list item. |
| `Ⓛ<https://example.com>` | A bare link, bookmark, or URL property. |
| `Ⓛ<[display text]https://example.com>` | A link where the visible text differs from the URL. |
| `⊕<#cols x #rows>` (optionally followed by `h`) | Marks the start of a table or database with that many columns/rows. The `h` means the first row is a header row (shown with a gray background in Notion). The cells of the table/database follow as their own rows immediately after. |
| Blank cell (`,,` with nothing between the commas) | An intentionally empty table/database cell — never filled in with placeholder text. |
| Two adjacent, non-empty cells on one row with nothing in between | Side-by-side Notion columns — each cell is one visual column; a cell left blank on a given row means that column has nothing at that row position. |

### Database columns specifically

When a full Notion **database** (not just a simple table) is flattened into rows, each property type is written as:

- Title / rich text → plain text
- Number → the number as text
- Select / status → the option name, wrapped in `ⓑ<#hex>...ⓑ` using the option's own color as a pill/badge
- Multi-select → option names joined with `; `, each with its own color
- Date → written out in full words, e.g. `October 1, 2026` (a range uses an en dash)
- Checkbox → `☑T` / `☑F`
- Person/relation → name(s) joined with `; `
- URL → `Ⓛ<url>`
- Empty property → the cell is left blank

## Worked example

From `Bug Tracker.csv`, a database row:

```
ⓣ<Helvetica.ttf><12pts><#000000>Promo code applied twice at checkout,
ⓣ<Helvetica.ttf><12pts><#0F7B6C>ⓑ<#DDEDEA>Checkoutⓑ,
ⓣ<Helvetica.ttf><12pts><#000000>2,
ⓣ<Helvetica.ttf><12pts><#000000>ⓑ<#DDEBF1>Webⓑ,
ⓣ<Helvetica.ttf><12pts><#000000>☑F ,
"ⓣ<Helvetica.ttf><12pts><#000000>October 13, 2026",
ⓣ<Helvetica.ttf><12pts><#D9730D>ⓑ<#FAEBDD>Highⓑ,
ⓣ<Helvetica.ttf><12pts><#E03E3E>ⓑ<#FBE4E4>Openⓑ,
"ⓣ<Helvetica.ttf><12pts><#000000>Apply code, go back to cart, return to checkout — discount doubles"
```

Reading left to right: the bug's title (plain black text), its **Component** property (`Checkout`, shown as a green pill), an **ID** number, its **Platform** (`Web`, shown as a blue pill), an unchecked **Regression** checkbox, the date it was **Reported**, its **Severity** (`High`, an orange pill), its **Status** (`Open`, a red pill), and the **Steps to Reproduce** text.
