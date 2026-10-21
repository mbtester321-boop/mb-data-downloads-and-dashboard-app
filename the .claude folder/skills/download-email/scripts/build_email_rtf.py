#!/usr/bin/env python3
"""
Build an email.rtf file that follows the emailDownloadTemplate.rtf conventions,
from a structured JSON description of one email.

Usage:
    python3 build_email_rtf.py input.json output.rtf

Input JSON schema:
{
  "from": "sender@example.com",
  "to": "me@example.com",
  "cc": ["a@example.com", ...],       # may be empty
  "bcc": ["b@example.com", ...],      # may be empty
  "date": "2026-10-14",               # yyyy-mm-dd, date received
  "time": "12:56:00",                 # hh:mm:ss (24h), time received
  "timezone": "EDT",                  # short zone abbreviation
  "subject": "Subject line",
  "body_blocks": [
      {"type": "text", "text": "line1\nline2", "align": "left|center|right",
       "font": "Helvetica", "size": 12, "color": "#D32F2F"},
      {"type": "inline_file", "filename": "logo.png"},
      {"type": "link", "url": "https://example.com", "text": "optional display text"},
      {"type": "table", "rows": [["Term", "Details"], ["Position", "Senior PM"]]}
  ],
  "attachments": ["file1.pdf", "file2.docx"]   # non-inline attachments only
}

"color" on a text block is optional; omit it (or use "#000000") for the
template's default black. Only emitted when it actually changes from the
previous block, same as font/size below.

Each consecutive run of "text" blocks that shares the same (font, size) is one
"section": it opens with the template's font-change marker followed by a
descriptive <FontName.ttf><Npts> label, and closes (switching to the next
section's label) only when font or size actually changes. The label is
documentation of the original email's styling for that section; the archival
RTF itself renders uniformly in the body font (f0) throughout, exactly as
emailDownloadTemplate.rtf does. Color is tracked independently of font/size
via its own marker (see COLOR_MARKER) since an email can recolor text (e.g. a
warning line) without changing font or size.

A "table" block renders the email's original HTML table as plain tagged text
— <table><row><cell>...</cell>...</row>...</table> — rather than real RTF
table rows, since this format favors plain, greppable archival text over
exact visual fidelity (same reasoning as the font-label markers above).
"""
import json
import sys

# Marker control sequences copied verbatim from emailDownloadTemplate.rtf:
# a font switch to the marker's icon font (f1/f2) and the RTF unicode escape
# for the icon glyph itself. Each is wrapped in its own {} group so the
# glyph's \uc0 (zero Unicode fallback bytes) setting stays local and doesn't
# leak into the \uc1 fallback convention used for the rest of the document's
# escaped non-ASCII text (see rtf_escape).
FONT_CHANGE_MARKER = "{\\f1 \\uc0\\u9443 }"   # brackets a font-labeled section
COLOR_CHANGE_MARKER = "{\\f1 \\uc0\\u9400 }"  # labels the text color from this point on
INLINE_FILE_MARKER = "{\\f2 \\uc0\\u9429 }"   # denotes a file embedded/linked at this spot
LINK_MARKER = "{\\f2 \\uc0\\u9409 }"          # denotes a hyperlink

ALIGN_CODES = {"left": r"\ql", "center": r"\qc", "right": r"\qr"}
DEFAULT_ALIGN = ALIGN_CODES["left"]
DEFAULT_COLOR = "#000000"


def _u_escape(code_unit):
    # RTF \uN is a signed 16-bit decimal; emit a literal '?' fallback byte after it
    # (matches the document-level \uc1 declared in the header).
    signed = code_unit if code_unit < 32768 else code_unit - 65536
    return f"\\u{signed}?"


def rtf_escape(text):
    out = []
    for ch in text:
        cp = ord(ch)
        if ch == "\\":
            out.append(r"\\")
        elif ch == "{":
            out.append(r"\{")
        elif ch == "}":
            out.append(r"\}")
        elif ch == "\n":
            out.append(r"\line ")
        elif cp < 128:
            out.append(ch)
        elif cp <= 0xFFFF:
            out.append(_u_escape(cp))
        else:
            # Outside the Basic Multilingual Plane (e.g. emoji): encode as a
            # UTF-16 surrogate pair, each half its own \u escape.
            cp -= 0x10000
            high = 0xD800 + (cp >> 10)
            low = 0xDC00 + (cp & 0x3FF)
            out.append(_u_escape(high))
            out.append(_u_escape(low))
    return "".join(out)


def build_table(rows):
    parts = ["<table>"]
    for row in rows:
        parts.append("<row>")
        for cell in row:
            parts.append(f"<cell>{rtf_escape(str(cell))}</cell>")
        parts.append("</row>")
    parts.append("</table>")
    return "".join(parts)


def build_body(body_blocks):
    parts = []
    current_label = None  # (font, size) of the currently open section, or None
    current_color = None  # hex string of the currently active text color, or None

    for block in body_blocks:
        btype = block.get("type", "text")

        if btype == "text":
            font = block.get("font", "Helvetica")
            size = block.get("size", 12)
            color = block.get("color") or DEFAULT_COLOR
            align = ALIGN_CODES.get(block.get("align", "left"), DEFAULT_ALIGN)
            text = block.get("text", "")

            label = (font, size)
            if label != current_label:
                if current_label is not None:
                    parts.append(">")  # close previous section
                parts.append(FONT_CHANGE_MARKER)
                parts.append(f"<<{rtf_escape(font)}.ttf><{size}pts>")
                current_label = label

            if color != current_color:
                parts.append(COLOR_CHANGE_MARKER)
                parts.append(f"<{color}>")
                current_color = color

            parts.append(f" {align} ")
            parts.append(rtf_escape(text))

        elif btype == "inline_file":
            filename = block.get("filename", "")
            parts.append(f"{INLINE_FILE_MARKER}<{rtf_escape(filename)}>")

        elif btype == "link":
            url = block.get("url", "")
            text = block.get("text")
            parts.append(LINK_MARKER)
            if text and text != url:
                parts.append(f"<[{rtf_escape(text)}]{rtf_escape(url)}>")
            else:
                parts.append(f"<{rtf_escape(url)}>")

        elif btype == "table":
            parts.append(build_table(block.get("rows", [])))

        else:
            raise ValueError(f"Unknown body block type: {btype}")

    # The final '>' closing the open section is supplied by the caller, which
    # wraps this with "<body><" ... ">//" — the same '>' closes both.
    return "".join(parts)


def build_rtf(data):
    from_addr = data.get("from", "")
    to_addr = data.get("to", "")
    cc = data.get("cc", []) or []
    bcc = data.get("bcc", []) or []
    date = data.get("date", "")
    time = data.get("time", "")
    tz = data.get("timezone", "")
    subject = data.get("subject", "")
    body_blocks = data.get("body_blocks", [])
    attachments = data.get("attachments", []) or []

    body_rtf = build_body(body_blocks)

    cc_tags = "".join(f"<{rtf_escape(a)}>" for a in cc)
    bcc_tags = "".join(f"<{rtf_escape(a)}>" for a in bcc)
    attachment_tags = "".join(f"<{rtf_escape(a)}>" for a in attachments)

    header = (
        r"{\rtf1\ansi\ansicpg1252\cocoartf2907"
        "\n"
        r"\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;"
        r"\f1\fnil\fcharset128 HiraginoSans-W3;\f2\fnil\fcharset128 HiraMinProN-W3;"
        "\n}\n"
        r"{\colortbl;\red255\green255\blue255;\red0\green0\blue0;}"
        "\n"
        r"{\*\expandedcolortbl;;\cssrgb\c0\c0\c0;}"
        "\n"
        r"\margl1440\margr1440\vieww14580\viewh17260\viewkind0"
        "\n"
        r"\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640"
        r"\pardirnatural\partightenfactor0"
        "\n\n"
        r"\uc1\f0\fs24 \cf0 "
    )

    fields = (
        f"<From><{rtf_escape(from_addr)}>//\\line \n"
        f"<To><{rtf_escape(to_addr)}>//\\line \n"
        f"<CC>{cc_tags}//\\line \n"
        f"<BCC>{bcc_tags}//\\line \n"
        f"<DateAndTime><{rtf_escape(date)}><{rtf_escape(time)}><{rtf_escape(tz)}>//\\line \n"
        f"<Subject><{rtf_escape(subject)}>//\\line \n"
    )

    body_section = f"<body><{body_rtf}>//\\line \n"

    attachments_section = f"<Attachments>{attachment_tags}"

    return header + fields + body_section + attachments_section + "}"


def main():
    if len(sys.argv) != 3:
        print("Usage: build_email_rtf.py input.json output.rtf", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    rtf = build_rtf(data)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(rtf)

    print(f"Wrote {sys.argv[2]}")


if __name__ == "__main__":
    main()
