# How to read the downloaded Gmail data

Each sub-folder in this directory is one downloaded email, named:

```
<sender-local-part>_<mmddyy>_<hhmm>
```

e.g. `rme3880_101426_1854` = an email from `rme3880@...`, received on 10/14/26 at 18:54. Inside each folder:

| File | What it is |
|---|---|
| `email.rtf` | **The actual downloaded data** — the email's headers, body, and attachment list, written using the fixed notation described below. This is the file to read if you want the raw local copy of the email. |
| `*.html` | An auto-generated preview page (built from `email.rtf`) used by the dashboard website to show a live rendering of the email in the browser. Not part of the raw downloaded format itself. |
| Any other image/file | The email's real, non-inline attachments (or inline images) saved as actual files alongside `email.rtf`. |

`emailDownloadTemplate.rtf` in this folder is the **blank template/legend** — it is not a real email, it's the pattern every `email.rtf` file follows.

## Opening an `email.rtf` file

These are plain RTF files — macOS Preview, TextEdit, Word, etc. will all open them, or from the Terminal:

```bash
textutil -convert txt -stdout "Emails/<folder>/email.rtf"
```

## The notation, field by field

```
<From><sender@example.com>//
<To><recipient@example.com>//
<CC><addr1><addr2>//
<BCC><addr1>//
<DateAndTime><yyyy-mm-dd><hh:mm:ss><TimeZone>//
<Subject><the subject line>//
<body><...see below.../>//
<Attachments><filename1.ext><filename2.ext>
```

- `<From>` / `<To>` — single email addresses.
- `<CC>` / `<BCC>` — zero or more `<address>` tags back to back; empty if there were none.
- `<DateAndTime>` — the date, time, and timezone the message was **received**.
- `<Subject>` — the subject line, verbatim.
- `//` marks the end of a top-level field.
- `<Attachments>` — one `<filename.ext>` tag per **non-inline** attachment that was actually downloaded as a real file in this folder. Empty if there were none.

### Inside `<body>` — symbol legend

| Symbol | Meaning |
|---|---|
| `ⓣ<<FontName.ttf><NNpts>` | Starts a run of body text in that font/size. A new `ⓣ` marker starts whenever the font, size, or **bold/italic** actually changes (bold/italic are folded into the font filename, e.g. `Helvetica-Bold.ttf`). |
| `Ⓒ<#RRGGBB>` | Sets the text color for the current run (immediately follows the `ⓣ` tag). `#000000` = normal/default black text. |
| `ⓕ<filename.ext>` | Marks the position of an **inline** file (e.g. an embedded image) at that point in the body — the real file sits in this same folder. |
| `Ⓛ<https://example.com>` | A bare link. |
| `Ⓛ<[display text]https://example.com>` | A link where the clickable text differs from the URL. |
| `⊕<<#cols x #rows>><cell1><cell2>...` | A table/HTML table in the email, flattened to cells read left-to-right, top-to-bottom; an empty `<>` is a blank cell. Rendered in the archive as `<table><row><cell>...</cell></row>...</table>` tags. |
| Plain text | Everything else is the literal body text, including line breaks. |

### Worked example

From `rme3880_101426_1854/email.rtf`:

```
<body><ⓣ<<Helvetica.ttf><12pts>Ⓒ<#000000> Hi Massimo, ... blondeandbelowthenetⓕ<image.png>>// <Attachments>
```

This means: the whole body is one 12pt Helvetica, black-text run, and there's an inline image (`image.png`, saved in the same folder) at the very end of the message; there were no separate (non-inline) attachments.

From `rme3880_101426_1903/email.rtf`, a message with a pricing table:

```
...here is the quote for the repairs needed on your refrigerator:<table><row><cell>REPAIR ITEM</cell><cell>PRICE</cell></row><row><cell>Compressor Replacement</cell><cell>$450.00</cell></row>...</table> Please let me know...
```

This is the email's HTML table, preserved as plain, greppable `<table>/<row>/<cell>` tags rather than true RTF table formatting — the goal of this format is an easy-to-read, easy-to-search local archive, not pixel-perfect visual reproduction.
