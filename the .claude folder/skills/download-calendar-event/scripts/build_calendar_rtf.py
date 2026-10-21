#!/usr/bin/env python3
"""
Build a calendar-event .rtf file that follows the calendarDownloadTemplate*.rtf
conventions, from a structured JSON description of one Google Calendar item.

Usage:
    python3 build_calendar_rtf.py input.json output.rtf

All three event kinds share these fields:
{
  "calendar": "Personal",
  "calendarColor": "#D81B60",
  "eventKind": "Event" | "Task" | "Appointment schedule",
  "eventTitle": "Walk the Brooklyn Bridge",
  "eventDate": "10/27/2026",                    # "10/19/2026-10/23/2026" for Appointment schedule
  "eventTime": "4pm-6pm",                        # "AllDay" for Task, the week's overall span for Appointment schedule
  ...
}

eventKind == "Event" adds:
  "eventSubtitle": "...",
  "alert": "10 minutes before",   # or "None" if no reminder is configured
  "location": "..."

eventKind == "Task" adds:
  "repeat": "Weekly on Tuesday",  # omit/empty if the task list doesn't repeat
  "eventSubtitle": "...",
  "principalTask": "Tuesday Tasks",
  "subTasks": ["1. Gym / workout session", "2. Pay bills and check bank statement", ...]

eventKind == "Appointment schedule" adds:
  "eventSubtitle": "...",
  "bookings": [
    {
      "bookedDate": "Monday, October 19",
      "bookedTime": "10am",           # booking's start time, 12-hour, no colon on the hour
      "name": "Alex Morgan",
      "email": "alex.morgan@example.com",
      "phone": "(212) 555-0148",
      "service": "30-min strategy consultation",
      "notes": "First-time client, wants to discuss Q4 marketing plan.",
      "location": "meet.google.com/tcy-anst-rtd",
      "alert": "30 minutes before"
    }, ...
  ]

Field order and nesting (<contents, <Tasks, <bookBlock, <bookedBy, and their
closing ">" lines) mirror assets/calendarDownloadTemplate*.rtf exactly. Minor
whitespace quirks in those hand-typed template files (e.g. a stray leading
space before some values) are not reproduced here — every value is written as
"<tag>value" with no extra space, which is the consistent form.
"""
import json
import re
import sys


def camel_case_title(title):
    """'Walk the Brooklyn Bridge' -> 'walkTheBrooklynBridge' (first word fully
    lowercase, each later word capitalized, all non-alphanumeric chars dropped)."""
    words = re.findall(r"[A-Za-z0-9]+", title)
    if not words:
        return "event"
    out = [words[0].lower()]
    for w in words[1:]:
        out.append(w[0].upper() + w[1:].lower())
    return "".join(out)


def rtf_escape(text):
    out = []
    for ch in str(text):
        cp = ord(ch)
        if ch == "\\":
            out.append(r"\\")
        elif ch == "{":
            out.append(r"\{")
        elif ch == "}":
            out.append(r"\}")
        elif ch == "\n":
            out.append("\\\n")
        elif cp < 128:
            out.append(ch)
        elif cp <= 0xFFFF:
            signed = cp if cp < 32768 else cp - 65536
            out.append(f"\\u{signed}?")
        else:
            cp2 = cp - 0x10000
            high = 0xD800 + (cp2 >> 10)
            low = 0xDC00 + (cp2 & 0x3FF)
            for half in (high, low):
                signed = half if half < 32768 else half - 65536
                out.append(f"\\u{signed}?")
    return "".join(out)


HEADER = (
    r"{\rtf1\ansi\ansicpg1252\cocoartf2907"
    "\n"
    r"\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}"
    "\n"
    r"{\colortbl;\red255\green255\blue255;}"
    "\n"
    r"{\*\expandedcolortbl;;}"
    "\n"
    r"\margl1440\margr1440\vieww14580\viewh17260\viewkind0"
    "\n"
    r"\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640"
    r"\pardirnatural\partightenfactor0"
    "\n\n"
    r"\f0\fs24 \cf0 "
)


def _line(tag, value):
    return f"<{tag}>{rtf_escape(value)}\\\n"


def _raw(text):
    return f"{text}\\\n"


def build_common(data):
    return [
        _line("calendar", data["calendar"]),
        _line("calendarColor", data["calendarColor"]),
        _line("eventKind", data["eventKind"]),
        _line("eventTitle", data["eventTitle"]),
        _line("eventDate", data["eventDate"]),
        _line("eventTime", data["eventTime"]),
    ]


def build_event(data):
    parts = build_common(data)
    parts.append(_line("eventSubtitle", data["eventSubtitle"]))
    parts.append(_line("alert", data["alert"]))
    parts.append(_line("location", data["location"]))
    return parts


def build_task(data):
    parts = build_common(data)
    if data.get("repeat"):
        parts.append(_line("repeat", data["repeat"]))
    parts.append(_line("eventSubtitle", data["eventSubtitle"]))
    parts.append(_raw("<contents"))
    parts.append(_raw("<Tasks"))
    parts.append(_line("PrincipalTask", data["principalTask"]))
    for sub in data["subTasks"]:
        parts.append(_line("subTask", sub))
    parts.append(_raw(">"))
    parts.append(_raw(">"))
    return parts


def build_appointment(data):
    parts = build_common(data)
    parts.append(_line("eventSubtitle", data["eventSubtitle"]))
    parts.append(_raw("<contents"))
    for booking in data["bookings"]:
        parts.append(_raw("<bookBlock"))
        parts.append(_line("bookedDate", booking["bookedDate"]))
        parts.append(_line("bookedTime", booking["bookedTime"]))
        parts.append(_raw("<bookedBy"))
        parts.append(_line("Name", booking["name"]))
        parts.append(_line("email", booking["email"]))
        parts.append(_line("phone", booking["phone"]))
        parts.append(_raw(">"))
        parts.append(_line("service", booking["service"]))
        parts.append(_line("notes", booking["notes"]))
        parts.append(_line("location", booking["location"]))
        parts.append(_line("alert", booking["alert"]))
        parts.append(_raw(">"))
    parts.append(_raw(">"))
    return parts


BUILDERS = {
    "Event": build_event,
    "Task": build_task,
    "Appointment schedule": build_appointment,
}


def build_rtf(data):
    kind = data.get("eventKind")
    builder = BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"Unknown eventKind: {kind!r}")
    body = "".join(builder(data))
    return HEADER + body + "}"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--filename":
        print(camel_case_title(sys.argv[2]))
        return

    if len(sys.argv) != 3:
        print(
            "Usage: build_calendar_rtf.py input.json output.rtf\n"
            "       build_calendar_rtf.py --filename \"Event Title\"",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    rtf = build_rtf(data)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(rtf)

    print(f"Wrote {sys.argv[2]}")


if __name__ == "__main__":
    main()
