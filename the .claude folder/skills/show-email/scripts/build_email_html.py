#!/usr/bin/env python3
"""
Build an index-style HTML page from an email.rtf produced by the
download-email skill's build_email_rtf.py.

Usage:
    python3 build_email_html.py <folder>

<folder> must contain email.rtf (as written by download-email) plus any
real attachment files saved alongside it. Writes "<folder_basename>.html"
into that same folder.

This is the inverse of build_email_rtf.py: it re-parses the exact marker
conventions that script writes (see emailDownloadTemplate.rtf) and renders
them back out as a styled HTML page.
"""
import os
import re
import shutil
import sys

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp",
              ".svg", ".tiff", ".tif", ".heic", ".heif"}

PLACEHOLDER_IMAGE = "image-file.jpg"
PLACEHOLDER_FILE = "file-folder-icon-simple-vector-22366990.jpg.avif"

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

FONT_OPEN_RE = re.compile(r'\{\\f1 \\uc0\\u9443 \}<<([^>]*)\.ttf><(\d+)pts>')
COLOR_RE = re.compile(r'\{\\f1 \\uc0\\u9400 \}<(#[0-9A-Fa-f]{6})>')
INLINE_RE = re.compile(r'\{\\f2 \\uc0\\u9429 \}<([^>]*)>')
LINK_RE = re.compile(r'\{\\f2 \\uc0\\u9409 \}<(\[[^\]]*\])?([^>]*)>')
ALIGN_RE = re.compile(r'\\q([lcr])')
TABLE_RE = re.compile(r'<table>(.*?)</table>', re.S)
ROW_RE = re.compile(r'<row>(.*?)</row>', re.S)
CELL_RE = re.compile(r'<cell>(.*?)</cell>', re.S)
CLOSE_RE = re.compile(r'>')

DEFAULT_COLOR = "#000000"

SPECIAL_RE = re.compile(
    "(?:" + FONT_OPEN_RE.pattern + ")"
    "|(?:" + COLOR_RE.pattern + ")"
    "|(?:" + INLINE_RE.pattern + ")"
    "|(?:" + LINK_RE.pattern + ")"
    "|(?:" + ALIGN_RE.pattern + ")"
    "|(?:" + TABLE_RE.pattern + ")"
    "|(?:" + CLOSE_RE.pattern + ")",
    re.S
)


def rtf_unescape(s):
    """Inverse of build_email_rtf.py's rtf_escape: resolves \\line, \\uN?
    (incl. UTF-16 surrogate pairs), \\\\, \\{, \\}. Leaves \\q[lcr] alone
    (handled separately by the body tokenizer)."""
    out = []
    pending = []  # buffered UTF-16 code units from consecutive \u escapes

    def flush():
        if pending:
            b = b"".join(cu.to_bytes(2, "little") for cu in pending)
            out.append(b.decode("utf-16-le", errors="replace"))
            pending.clear()

    token_re = re.compile(r'\\line ?|\\u(-?\d+)\?|\\\\|\\\{|\\\}')
    pos = 0
    for m in token_re.finditer(s):
        literal = s[pos:m.start()]
        if literal:
            flush()
            out.append(literal)
        tok = m.group(0)
        if tok.startswith("\\line"):
            flush()
            out.append("\n")
        elif tok.startswith("\\u"):
            v = int(m.group(1))
            if v < 0:
                v += 65536
            pending.append(v)
        elif tok == "\\\\":
            flush()
            out.append("\\")
        elif tok == "\\{":
            flush()
            out.append("{")
        elif tok == "\\}":
            flush()
            out.append("}")
        pos = m.end()
    flush()
    out.append(s[pos:])
    return "".join(out)


def html_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def css_font_family(name):
    """Wrap an RTF-labeled font name (e.g. 'Helvetica') in a CSS font stack
    with a sane generic fallback, so the page still looks reasonable if the
    exact named font isn't installed on the viewer's system."""
    lowered = name.lower()
    if any(k in lowered for k in ("courier", "mono", "consolas")):
        fallback = "monospace"
    elif any(k in lowered for k in ("times", "georgia", "serif", "garamond", "cambria")):
        fallback = "serif"
    else:
        fallback = "sans-serif"
    return f"'{name}', {fallback}"


def extract_top_fields(head):
    def field(name):
        m = re.search(r'<%s>(.*?)//\\line' % re.escape(name), head, re.S)
        return m.group(1) if m else ""

    def addrs(name):
        raw = field(name)
        return [rtf_unescape(a) for a in re.findall(r'<([^<>]*)>', raw) if a]

    from_addr = addrs("From")
    to_addr = addrs("To")
    cc = addrs("CC")
    bcc = addrs("BCC")

    dt_raw = field("DateAndTime")
    dt_parts = re.findall(r'<([^<>]*)>', dt_raw)
    date, time, tz = (dt_parts + ["", "", ""])[:3]

    subj_raw = field("Subject")
    subj_m = re.match(r'^<(.*)>$', subj_raw, re.S)
    subject = rtf_unescape(subj_m.group(1)) if subj_m else rtf_unescape(subj_raw)

    return {
        "from": from_addr[0] if from_addr else "",
        "to": ", ".join(to_addr),
        "cc": cc,
        "bcc": bcc,
        "date": date,
        "time": time,
        "tz": tz,
        "subject": subject,
    }


def parse_table(inner):
    """inner is the raw (rtf-escaped) text between <table> and </table>."""
    rows = []
    for rm in ROW_RE.finditer(inner):
        cells = [rtf_unescape(cm.group(1)) for cm in CELL_RE.finditer(rm.group(1))]
        rows.append(cells)
    return rows


def parse_body(body_raw):
    """Returns a list of blocks: {'type': 'text', 'align': ..., 'font': ...,
    'size': ..., 'color': ..., 'text': ...} (already rtf-unescaped),
    {'type': 'inline_file', 'filename': ...}, {'type': 'link', 'text': ...,
    'url': ..., 'font': ..., 'size': ..., 'color': ...}, or {'type': 'table',
    'rows': [[cell, ...], ...]}. 'font'/'size'/'color' are the name/point-size
    /hex color labeled in the RTF's font- and color-section markers that the
    block fell under."""
    blocks = []
    align = "left"
    font, size = "Helvetica", 12
    color = DEFAULT_COLOR
    pos = 0
    for m in SPECIAL_RE.finditer(body_raw):
        gap = body_raw[pos:m.start()]
        if gap:
            blocks.append({"type": "text", "align": align, "font": font,
                            "size": size, "color": color, "text": rtf_unescape(gap)})
        tok = m.group(0)
        if tok.startswith("{\\f1 \\uc0\\u9443"):
            fm = FONT_OPEN_RE.match(tok)
            font, size = rtf_unescape(fm.group(1)), int(fm.group(2))
        elif tok.startswith("{\\f1 \\uc0\\u9400"):
            cm = COLOR_RE.match(tok)
            color = cm.group(1).upper()
        elif tok.startswith("{\\f2 \\uc0\\u9429"):
            im = INLINE_RE.match(tok)
            blocks.append({"type": "inline_file", "filename": rtf_unescape(im.group(1))})
        elif tok.startswith("{\\f2 \\uc0\\u9409"):
            lm = LINK_RE.match(tok)
            bracket, url = lm.group(1), lm.group(2)
            text = rtf_unescape(bracket[1:-1]) if bracket else None
            blocks.append({"type": "link", "text": text, "url": rtf_unescape(url),
                            "font": font, "size": size, "color": color})
        elif tok.startswith("\\q"):
            align = {"l": "left", "c": "center", "r": "right"}[ALIGN_RE.match(tok).group(1)]
        elif tok.startswith("<table>"):
            tm = TABLE_RE.match(tok)
            blocks.append({"type": "table", "rows": parse_table(tm.group(1))})
        elif tok == ">":
            pass  # section-close marker, no visual effect
        pos = m.end()
    tail = body_raw[pos:]
    if tail:
        blocks.append({"type": "text", "align": align, "font": font,
                        "size": size, "color": color, "text": rtf_unescape(tail)})
    return blocks


def paragraphs_html(text, align, font, size, color=DEFAULT_COLOR):
    align_css = {"left": "justify", "center": "center", "right": "right"}[align]
    font_css = css_font_family(font)
    color_css = color or DEFAULT_COLOR
    chunks = re.split(r"\n{2,}", text)
    out = []
    bullet_items = []
    bullet_re = re.compile(r'^[•‣◦⁃∙]\s*')

    def flush_bullets():
        if not bullet_items:
            return
        items = "".join(
            "      <li>%s</li>\n" % html_escape(item).replace("\n", "<br>\n")
            for item in bullet_items
        )
        out.append(
            f'    <ul style="font-family:{font_css}; font-size:{size}pt; color:{color_css}; line-height:1.6; margin:0 0 20px 0; padding-left:1.4em;">\n'
            f'{items}'
            f'    </ul>\n'
        )
        bullet_items.clear()

    for chunk in chunks:
        chunk = chunk.strip("\n")
        if chunk.strip() == "":
            continue
        stripped = chunk.lstrip()
        bullet_m = bullet_re.match(stripped)
        if bullet_m:
            bullet_items.append(stripped[bullet_m.end():])
            continue
        flush_bullets()
        inner = html_escape(chunk).replace("\n", "<br>\n")
        out.append(
            f'    <p style="font-family:{font_css}; font-size:{size}pt; color:{color_css}; line-height:1.6; text-align:{align_css}; margin:0 0 20px 0;">\n'
            f'      {inner}\n'
            f'    </p>\n'
        )
    flush_bullets()
    return "".join(out)


def is_image(filename):
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTS


def ensure_placeholder(folder, name):
    dest = os.path.join(folder, name)
    if not os.path.exists(dest):
        shutil.copy(os.path.join(ASSETS_DIR, name), dest)
    return name


def render_table(rows):
    if not rows:
        return ""
    body_rows = []
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        cells = "".join(
            f'<{tag} style="border:1px solid #ddd; padding:8px 14px; text-align:left;'
            f'{" font-weight:bold; background:#f5f5f5;" if tag == "th" else ""}">'
            f'{html_escape(cell).replace(chr(10), "<br>")}</{tag}>'
            for cell in row
        )
        body_rows.append(f'      <tr>{cells}</tr>\n')
    return (
        '    <table style="border-collapse:collapse; width:100%; margin:0 0 20px 0; font-size:16px;">\n'
        + "".join(body_rows) +
        '    </table>\n'
    )


def render_body(blocks, folder):
    html = []
    for b in blocks:
        if b["type"] == "text":
            html.append(paragraphs_html(b["text"], b["align"], b["font"], b["size"], b.get("color")))
        elif b["type"] == "link":
            label = html_escape(b["text"]) if b["text"] else html_escape(b["url"])
            font_css = css_font_family(b["font"])
            html.append(
                f'    <p style="font-family:{font_css}; font-size:{b["size"]}pt; line-height:1.6; margin:0 0 20px 0;">'
                f'<a href="{html_escape(b["url"])}" target="_blank" '
                f'style="color:#1a73e8;">{label}</a></p>\n'
            )
        elif b["type"] == "table":
            html.append(render_table(b["rows"]))
        elif b["type"] == "inline_file":
            filename = b["filename"]
            if is_image(filename) and os.path.exists(os.path.join(folder, filename)):
                src = filename
            elif is_image(filename):
                src = ensure_placeholder(folder, PLACEHOLDER_IMAGE)
            else:
                src = ensure_placeholder(folder, PLACEHOLDER_FILE)
            html.append(
                f'    <img src="{html_escape(src)}" alt="{html_escape(filename)}" '
                f'style="width:64px; height:64px; object-fit:contain; margin-bottom:24px; display:block;">\n'
            )
    return "".join(html)


def render_attachments(attachments, folder):
    if not attachments:
        return ""
    tiles = []
    for filename in attachments:
        if is_image(filename) and os.path.exists(os.path.join(folder, filename)):
            icon = filename
        elif is_image(filename):
            icon = ensure_placeholder(folder, PLACEHOLDER_IMAGE)
        else:
            icon = ensure_placeholder(folder, PLACEHOLDER_FILE)
        href = filename if os.path.exists(os.path.join(folder, filename)) else "#"
        tiles.append(
            '      <a href="%s" download style="text-align:left; text-decoration:none; color:inherit;">\n'
            '        <img src="%s" alt="file icon" style="width:72px; height:72px; object-fit:contain; display:block;">\n'
            '        <div style="font-size:16px; margin-top:4px;">%s &#8681;</div>\n'
            '      </a>\n'
            % (html_escape(href), html_escape(icon), html_escape(filename))
        )
    return (
        '    <div style="display:flex; gap:40px; flex-wrap:wrap; margin-top:8px;">\n'
        + "".join(tiles) +
        '    </div>\n'
    )


def format_datetime(date, time, tz):
    try:
        import datetime
        d = datetime.datetime.strptime(date, "%Y-%m-%d")
        t = datetime.datetime.strptime(time, "%H:%M:%S")
        day = d.strftime("%B %-d")
        hour = t.strftime("%-I:%M%p").lower()
        return f"{day}, {hour} {tz}".strip()
    except Exception:
        return f"{date} {time} {tz}".strip()


def build_html(fields, body_html, attachments_html):
    cc_row = ""
    if fields["cc"]:
        cc_row = (
            '      <div style="color:#888;">CC: %s</div>\n'
            % html_escape(", ".join(fields["cc"]))
        )
    bcc_row = ""
    if fields["bcc"]:
        bcc_row = (
            '      <div style="color:#888;">BCC: %s</div>\n'
            % html_escape(", ".join(fields["bcc"]))
        )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html_escape(fields["subject"]) or "Email"}</title>
</head>
<body style="margin:0;">
<div style="background:#000; margin:0; padding:60px 20px; min-height:100vh; box-sizing:border-box; display:flex; justify-content:center; align-items:flex-start; font-family:Georgia, 'Times New Roman', serif;">
  <div style="background:#ffffff; border-radius:48px; max-width:760px; width:100%; padding:48px 56px; box-sizing:border-box; color:#000;">

    <div style="font-size:18px; line-height:1.6; margin-bottom:24px;">
      <div style="display:flex; justify-content:space-between;">
        <span>From: {html_escape(fields["from"])}</span>
        <span>{html_escape(format_datetime(fields["date"], fields["time"], fields["tz"]))}</span>
      </div>
      <div>To: {html_escape(fields["to"])}</div>
{cc_row}{bcc_row}    </div>

    <h2 style="font-family:'Helvetica Heavy', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight:900; font-size:15pt; margin:0 0 20px 0;">{html_escape(fields["subject"])}</h2>

{body_html}
{attachments_html}
  </div>
</div>
</body>
</html>
'''


def main():
    if len(sys.argv) != 2:
        print("Usage: build_email_html.py <folder>", file=sys.stderr)
        sys.exit(1)

    folder = os.path.abspath(sys.argv[1])
    rtf_path = os.path.join(folder, "email.rtf")
    if not os.path.isfile(rtf_path):
        print(f"No email.rtf found in {folder}", file=sys.stderr)
        sys.exit(1)

    with open(rtf_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    body_start_idx = text.index("<body>")
    head = text[:body_start_idx]
    rest = text[body_start_idx + len("<body>"):]

    attach_tag_idx = rest.index("<Attachments>")
    body_and_close = rest[:attach_tag_idx]
    body_raw = re.sub(r'>//\\line\s*$', '', body_and_close.rstrip())
    if body_raw.startswith("<"):
        body_raw = body_raw[1:]
    attachments_raw = rest[attach_tag_idx + len("<Attachments>"):].rstrip()
    if attachments_raw.endswith("}"):
        attachments_raw = attachments_raw[:-1]
    attachments = [rtf_unescape(a) for a in re.findall(r'<([^<>]*)>', attachments_raw) if a]

    fields = extract_top_fields(head)
    blocks = parse_body(body_raw)
    body_html = render_body(blocks, folder)
    attachments_html = render_attachments(attachments, folder)

    html = build_html(fields, body_html, attachments_html)

    folder_name = os.path.basename(folder.rstrip("/"))
    out_path = os.path.join(folder, f"{folder_name}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
