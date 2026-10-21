---
name: show-calendar-event
description: Use when the user says "show the calendar event" / "visualize this .rtf" / "turn this calendar download into a page" / "preview the downloaded event", referring to a .rtf file produced by the download-calendar-event skill. Parses the file's tags and renders a styled HTML <div> card matching EventTemplate.pdf, TaskTemplate.pdf, or appointmentScheduleTemplate.pdf depending on its <eventKind>.
---

# Show Calendar Event

Turn a `.rtf` file produced by **download-calendar-event** back into a styled,
self-contained `.html` file containing one `<div class="calendar-card">`. The
look is dictated entirely by `<eventKind>`:

- `Event` → `assets/EventTemplate.pdf`'s layout
- `Task` → `assets/TaskTemplate.pdf`'s layout
- `Appointment schedule` → `assets/appointmentScheduleTemplate.pdf`'s layout

Reference those three PDFs if you need to double-check a visual detail — they
are the source of truth for spacing, color, and text hierarchy, not this
document's prose description of them.

## 0. Identify the target

Figure out which `.rtf` file(s) the user means (by filename, or "the one I
just downloaded"). This skill only knows how to read files that follow
`calendarDownloadTemplate*.rtf`'s tag conventions — i.e. ones produced by
**download-calendar-event**. If the user points at some other `.rtf`, say so
rather than guessing at its structure.

## 1. Parse the .rtf back to JSON

```bash
python3 ~/.claude/skills/show-calendar-event/scripts/parse_calendar_rtf.py <input.rtf> <output.json>
```

This reverses `build_calendar_rtf.py`'s tag format exactly (via
`textutil -convert txt -stdout`, then a small state-machine parser) and
produces the same JSON shape that script's own docstring documents — so the
result round-trips. If parsing fails, the `.rtf` likely wasn't built by
download-calendar-event (or was hand-edited off-pattern); say so rather than
patching around it.

## 2. Render the JSON to HTML

```bash
python3 ~/.claude/skills/show-calendar-event/scripts/build_calendar_html.py <input.json> <output.html>
```

The renderer dispatches on `eventKind` and handles all the layout rules
itself — you shouldn't need to hand-write any HTML/CSS for a normal run.
What it does, per kind, for reference:

**All three:** a rounded card with a banner whose background is a gradient
from `calendarColor` to a lightened version of it, with the gradient's 50/50
blend point placed 1/3 of the way *up from the bottom* (i.e. at 67% down from
the top, not the usual 50%) — this keeps the top two-thirds close to the base
color and lightens quickly only near the bottom, matching the mockups. A
light-grey `Calendar: <calendar>` footer sits centered at the bottom of every
card.

**Event:** banner shows weekday + full date (from `eventDate`) stacked, two
lines, centered, white. Below: `eventTitle`, then `eventTime` in grey with
`(notify <alert, "minutes"→"min"> before)` beside it in a lighter grey — or
nothing if `alert` is `"None"`. Then `eventSubtitle`, then `Location:
<location>` in grey.

**Task:** same weekday/date banner. Below: `eventTitle`, then (if present)
"Repeats `<repeat>`" in grey, then a bulleted (hollow-circle) list: first the
`principalTask` in bold with `eventSubtitle` beside it in grey, then every
`subTask` as its own bullet line, verbatim.

**Appointment schedule:** banner shows `eventTitle` alone, large, centered,
no date/weekday. Below it, a fixed 5-day × 8-hour grid: the two halves of
`eventDate` are printed as small lowercase `mon d` labels at the grid's top
corners; each row's hour label (colored like `calendarColor`) starts from
`eventTime`'s first value and increments by one hour per row. Each booking
(`bookings[]`) is placed into the cell matching its `bookedDate` (day offset
from the range's start) and `bookedTime` (hour offset from `eventTime`'s
start) — out-of-range bookings are silently skipped (shouldn't happen for a
schedule built by download-calendar-event's own convention of one file per
week). Each booking renders as a solid-`calendarColor`, rounded box with
`name` (bold) and `service` beneath it; **on hover** it expands downward with
a lighter-tint background showing `notes`, then `email`/`phone`, then
🔔`<alert, "minutes"→"min">` — real mouse hover in an actual browser triggers
this via plain CSS `:hover`; note that if you're checking the result through
browser-automation tooling, a synthetic "hover" action may not trigger CSS
`:hover` the way a real mouse does — that's a limitation of the tool, not a
sign the page is broken (verify by temporarily forcing the `.booking__details`
element's opacity to `1` via `javascript_tool` if you need to confirm
visually without a real mouse).

If you need to adjust the design, edit `scripts/build_calendar_html.py`
directly — the CSS lives in Python string constants near the top of the file
(`BASE_CSS`, `EVENT_CSS`, `TASK_CSS`, `SCHEDULE_CSS`), and the three
`render_*` functions build each kind's markup.

## 3. Sanity-check

Open the result once (e.g. serve the output directory with
`python3 -m http.server` and view it in a browser, or use Claude in Chrome)
to confirm it rendered sensibly — especially after any CSS edit, or for a
file this skill hasn't been run against before. Not required on every routine
run once you trust the pipeline.

## 4. Name and save the file

Same basename as the input `.rtf`, with a `.html` extension, in the same
directory as the source file unless the user says otherwise. If a file with
that name already exists, ask before overwriting.

## 5. Report back

Tell the user, briefly: the filename written and which of the three layouts
it used. If any field fell back to a default (e.g. a missing `repeat`, or an
`alert` of `"None"` producing no notify line), that's expected behavior, not
worth flagging — only flag something if the source `.rtf` was missing data
the layout actually needed.
