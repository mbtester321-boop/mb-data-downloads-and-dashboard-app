#!/usr/bin/env python3
"""
Parse a .rtf file produced by the download-calendar-event skill back into the
same JSON shape that skill's build_calendar_rtf.py consumes. This is the exact
inverse of that script's tag format (see calendarDownloadTemplate*.rtf).

Usage:
    python3 parse_calendar_rtf.py input.rtf output.json
"""
import json
import re
import subprocess
import sys

TAG_RE = re.compile(r"^<([A-Za-z]+)>(.*)$")


def rtf_to_text(path):
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", path],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def lines_of(text):
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if line.strip() != "":
            yield line


class Parser:
    def __init__(self, text):
        self.lines = list(lines_of(text))
        self.i = 0

    def peek(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def next_line(self):
        line = self.lines[self.i]
        self.i += 1
        return line

    def expect_tag(self, name):
        line = self.next_line()
        m = TAG_RE.match(line)
        if not m or m.group(1) != name:
            raise ValueError(f"expected <{name}>..., got {line!r}")
        return m.group(2)

    def expect_raw(self, text):
        line = self.next_line()
        if line != text:
            raise ValueError(f"expected {text!r}, got {line!r}")

    def peek_tag_name(self):
        line = self.peek()
        if line is None:
            return None
        m = TAG_RE.match(line)
        return m.group(1) if m else None


def parse(text):
    p = Parser(text)

    data = {
        "calendar": p.expect_tag("calendar"),
        "calendarColor": p.expect_tag("calendarColor"),
        "eventKind": p.expect_tag("eventKind"),
        "eventTitle": p.expect_tag("eventTitle"),
        "eventDate": p.expect_tag("eventDate"),
        "eventTime": p.expect_tag("eventTime"),
    }

    kind = data["eventKind"]

    if kind == "Event":
        data["eventSubtitle"] = p.expect_tag("eventSubtitle")
        data["alert"] = p.expect_tag("alert")
        data["location"] = p.expect_tag("location")

    elif kind == "Task":
        if p.peek_tag_name() == "repeat":
            data["repeat"] = p.expect_tag("repeat")
        data["eventSubtitle"] = p.expect_tag("eventSubtitle")
        p.expect_raw("<contents")
        p.expect_raw("<Tasks")
        data["principalTask"] = p.expect_tag("PrincipalTask")
        subtasks = []
        while p.peek_tag_name() == "subTask":
            subtasks.append(p.expect_tag("subTask"))
        data["subTasks"] = subtasks
        p.expect_raw(">")  # closes Tasks
        p.expect_raw(">")  # closes contents

    elif kind == "Appointment schedule":
        data["eventSubtitle"] = p.expect_tag("eventSubtitle")
        p.expect_raw("<contents")
        bookings = []
        while p.peek() == "<bookBlock":
            p.expect_raw("<bookBlock")
            booking = {
                "bookedDate": p.expect_tag("bookedDate"),
                "bookedTime": p.expect_tag("bookedTime"),
            }
            p.expect_raw("<bookedBy")
            booking["name"] = p.expect_tag("Name")
            booking["email"] = p.expect_tag("email")
            booking["phone"] = p.expect_tag("phone")
            p.expect_raw(">")  # closes bookedBy
            booking["service"] = p.expect_tag("service")
            booking["notes"] = p.expect_tag("notes")
            booking["location"] = p.expect_tag("location")
            booking["alert"] = p.expect_tag("alert")
            p.expect_raw(">")  # closes bookBlock
            bookings.append(booking)
        p.expect_raw(">")  # closes contents
        data["bookings"] = bookings

    else:
        raise ValueError(f"Unknown eventKind: {kind!r}")

    return data


def main():
    if len(sys.argv) != 3:
        print("Usage: parse_calendar_rtf.py input.rtf output.json", file=sys.stderr)
        sys.exit(1)

    text = rtf_to_text(sys.argv[1])
    data = parse(text)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {sys.argv[2]}")


if __name__ == "__main__":
    main()
