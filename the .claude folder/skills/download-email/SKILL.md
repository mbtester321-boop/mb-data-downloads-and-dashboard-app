---
name: download-email
description: Use when the user says "download the email" / "save this email" / "download this email to a folder" (referring to a specific Gmail message, open or identified by sender/subject). Saves the email as a folder containing email.rtf (built from emailDownloadTemplate.rtf) plus every non-inline attachment, named emailprefix_mmddyy_hhmm from the sender's address and the time the email was received.
---

# Download Email

Save one Gmail message to a self-contained local folder: a formatted `email.rtf`
plus its real attachment files. Uses the Gmail MCP tools (`get_message`,
`get_thread`, `search_threads`) to fetch the message — never ask the user to
paste email content manually unless those tools are unavailable.

## 0. Identify the target message

Figure out which message the user means:
- If they just viewed/mentioned a specific email in this conversation, you may
  already have its message ID or enough detail to `search_threads` for it
  (e.g. `from:sender subject:keyword`).
- If ambiguous, ask which email (sender + subject, or point you at a search).

Fetch it with `get_message` (or `get_thread` if they mean a whole thread —
in that case, ask whether to save the whole thread as one folder with one
`email.rtf` per message, or just the one message they mean) using
`messageFormat: FULL_CONTENT` so you get `sender`, `to_recipients`,
`cc_recipients`, `bcc_recipients`, `date`, `subject`, `plaintext_body`,
`html_body`, and `attachments`.

## 1. Compute the folder name

`emailprefix_mmddyy_hhmm`, where:
- `emailprefix` = the local part of the **sender's** address (before the `@`),
  lowercased, with anything unsafe for a folder name (spaces, `/`, `.`, quotes)
  replaced with `-`. E.g. `Joe Burger <joe.burger@x.com>` → `joe-burger`.
- `mmddyy` / `hhmm` = the date and time the email was **received** (the
  message's `date` field), converted to the local system timezone, zero-padded
  (e.g. October 14 2026, 12:56 PM → `101426_1256`).

Create this folder in the **current working directory** (the directory the
session is running in when the skill is triggered) unless the user names a
different destination this time. If a folder with this exact name already
exists (e.g. you re-save the same email), ask before overwriting.

## 2. Work out the body content and attachments

Always check `html_body` for this step, even when `plaintext_body` reads
fine — plaintext conversion silently drops color and table structure, which
the format now preserves. From the fetched message:
- **Body**: start from `html_body` (fall back to `plaintext_body` only when
  `html_body` is missing). Split into one or more `body_blocks` text entries
  (see step 3) — almost all real emails are a single font/size/color, so this
  is usually exactly one `text` block holding the whole message.
- **Color**: if a run of text in `html_body` has an explicit non-black color
  (inline `style="color:..."`, a `color` attribute, or a named/hex color that
  isn't effectively black), set that `text` block's `"color"` to the
  equivalent `#RRGGBB` hex. Leave `"color"` unset (defaults to black) for
  everything else — don't invent colors that aren't actually in the markup.
- **Tables**: an HTML `<table>` becomes its own `body_blocks` entry of
  `"type": "table"` with `"rows"`: a list of rows, each a list of that row's
  cell text (reading order, left to right, top to bottom). Flatten any
  cell-internal formatting to plain text; don't try to represent merged
  cells — repeat the value or leave a cell empty instead.
- **Links**: any URL in the body (bare, or `<a href>` text) becomes a `link`
  block at that position in the text, with `text` set to the anchor's display
  text when it differs from the URL itself.
- **Attachments**: for each entry in the message's `attachments` array, check
  its `inline` flag (or whether `html_body` references it by `cid:`):
  - `inline: true` (embedded images etc.) → an `inline_file` block at its
    position in the body — don't list these under `<Attachments>`.
  - Not inline → goes in the top-level `attachments` list (filenames only),
    **and** gets downloaded as a real file in the folder (step 5).

## 3. Build email.rtf

Write a JSON file describing the email (see the schema and example at the top
of `scripts/build_email_rtf.py`), then run:

```bash
python3 ~/.claude/skills/download-email/scripts/build_email_rtf.py <input.json> "<folder>/email.rtf"
```

This script — not hand-typed RTF — produces the file, because the RTF control
codes and the template's marker glyphs are easy to get subtly wrong by hand.
It fills in:
- `<From>` — sender's address
- `<To>` — the message's actual recipient address(es) (the user's own inbox)
- `<CC>` / `<BCC>` — each address as its own `<addr>` tag, empty if none
- `<DateAndTime>` — date, time, and timezone the email was received
- `<Subject>` — the subject line
- `<body>` — the body content, formatted per `body_blocks`, including any
  color markers and `<table><row><cell>...` blocks
- `<Attachments>` — one `<filename.ext>` tag per non-inline attachment

Reference `assets/emailDownloadTemplate.rtf` if you need to double check the
exact tag/marker conventions.

Sanity-check the result once per session (not required every run) with:
```bash
textutil -convert txt -stdout "<folder>/email.rtf"
```
If that errors, the RTF is malformed — fix the script input, don't hand-patch
the `.rtf` output.

## 4. Download the real attachment files

For each non-inline attachment, `get_message` with `FULL_CONTENT` should
include its content; decode the base64 `content` field and write it to
`<folder>/<filename>`, sanitizing the filename (strip any `/`, `..`, or null
bytes — write only inside the target folder).

If an attachment's content isn't embedded in the response (only an `id` with
no `content`), there is no separate attachment-download tool on this Gmail
connector — say so plainly to the user rather than silently skipping it, and
suggest opening the message's `viewUrl` in a browser to download it manually.

## 5. Report back

Tell the user, briefly:
- The folder path created
- That `email.rtf` was written and from how many attachments (inline vs. real
  files saved)
- Any attachment that couldn't be auto-downloaded and why
