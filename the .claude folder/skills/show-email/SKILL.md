---
name: show-email
description: Use when the user says "show the email" / "build a page for this email" / "turn this email folder into a website", referring to a folder produced by the download-email skill (e.g. rme3880_101426_1854). Reads that folder's email.rtf and renders it back out as a styled, self-contained index-style HTML page inside the same folder.
---

# Show Email

Undo the `download-email` skill: take a folder it produced (`email.rtf` plus
any real attachment files) and render the email as a styled HTML page,
placed in that same folder.

## 1. Identify the target folder

The user will name a folder like `rme3880_101426_1854` (an
`emailprefix_mmddyy_hhmm` folder from `download-email`). Resolve it relative
to the current working directory unless they give a different path. It must
contain an `email.rtf` — if it doesn't, say so rather than guessing.

## 2. Run the builder script

```bash
python3 ~/.claude/skills/show-email/scripts/build_email_html.py "<folder>"
```

This parses `email.rtf` using the exact marker conventions documented in
`emailDownloadTemplate.rtf` (and implemented by `download-email`'s
`build_email_rtf.py` — this script is its inverse) and writes
`<folder_basename>.html` into that folder. It:

- Extracts `From`, `To`, `CC`, `BCC`, date/time, and `Subject`.
- Walks the body's font-section, inline-file, link, and alignment markers in
  order, converting each into the matching HTML: paragraphs (justified by
  default, centered/right if the original was `\qc`/`\qr`), `<a>` tags for
  links, and `<img>` tags for inline files at their original position.
  Consecutive lines starting with a bullet character (`•`/`‣`/`◦`/`⁃`/`∙`)
  become a real `<ul><li>` list instead of a literal bullet glyph in a
  paragraph.
- Each paragraph/list/link keeps the font name and point size that the RTF's
  `<<FontName.ttf><Npts>` section label gave it (wrapped in a CSS stack with
  a sane generic fallback — serif/monospace/sans-serif guessed from the font
  name — in case the exact font isn't installed on the viewer's machine).
  The `Subject` heading is fixed separately at Helvetica Heavy, 15pt,
  regardless of the body's labeled fonts.
- Also tracks the RTF's color marker (`<#RRGGBB>` after the circled-C glyph)
  the same way it tracks font/size: whichever hex color was last set applies
  to every paragraph/list until the marker changes again, default black.
  Color changes a paragraph's boundary exactly like a font or alignment
  change does — it's block-level, not an inline span within one paragraph,
  so a colored aside (e.g. a warning line) should be its own `text` block
  going into `build_email_rtf.py`, not a color change mid-sentence.
- Renders a `<table>...</table>` body block (rows of `<row><cell>` tags) as
  a real bordered HTML `<table>`, first row styled as a header (bold, light
  gray background), matching the card's black-on-white aesthetic. Table
  cells don't carry their own font/color/align — they inherit the page's
  base styling.
- Emits a full HTML document (`<!DOCTYPE html>` + `<meta charset="UTF-8">`),
  not a bare fragment — without an explicit UTF-8 declaration, browsers can
  misread the file's UTF-8 bytes as Latin-1/Windows-1252 when opened
  directly, which is what turns bullets/emoji into mojibake like `â€¢`.
  Multi-codepoint emoji (ZWJ sequences, skin-tone modifiers, variation
  selectors) round-trip correctly since each codepoint's RTF `\uN` escape is
  decoded and recombined in order.
- For every inline file or attachment: if it's an image extension **and**
  the real file is sitting in the folder, embeds/links that real file. If
  it's an image extension but the real file isn't there, substitutes the
  bundled placeholder `image-file.jpg`. If it's not an image extension at
  all, uses the bundled placeholder
  `file-folder-icon-simple-vector-22366990.jpg.avif`. Either placeholder is
  copied into the target folder the first time it's needed.
- Lists every attachment named in `<Attachments>` (i.e. not inline) in a row
  at the bottom, each as an icon + filename + a download arrow, wrapped in a
  link to the real file so clicking it downloads/opens that attachment.
- Wraps the whole email in one rounded-corner `<div>` on a dark backdrop,
  matching the look of this project's `index.html` mockup.

## 3. Sanity-check and report

Open the produced HTML (or at least skim it) to confirm the subject, sender,
and body read correctly and no stray characters leaked in from the RTF
markers — malformed RTF or an email containing a literal `<`/`>` in the body
text can occasionally confuse the parser since the format doesn't escape
those characters; fix by hand if something looks off rather than re-running
blindly.

Tell the user, briefly:
- The path to the HTML file written.
- Whether any inline/attached files were missing from the folder and got a
  placeholder instead.
