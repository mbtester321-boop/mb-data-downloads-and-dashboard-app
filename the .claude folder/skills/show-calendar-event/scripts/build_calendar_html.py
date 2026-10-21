#!/usr/bin/env python3
"""
Render a calendar-event JSON (the same shape download-calendar-event's
build_calendar_rtf.py consumes, and parse_calendar_rtf.py produces) into a
self-contained .html file containing one styled <div class="calendar-card">,
matching EventTemplate.pdf / TaskTemplate.pdf / appointmentScheduleTemplate.pdf.

Usage:
    python3 build_calendar_html.py input.json output.html
"""
import datetime
import html
import json
import re
import sys

# ---------------------------------------------------------------- color math

def hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c))) for c in rgb))


def mix(hex_a, hex_b, t):
    """t=0 -> hex_a, t=1 -> hex_b."""
    a, b = hex_to_rgb(hex_a), hex_to_rgb(hex_b)
    return rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def lighten(hex_color, amount=0.35):
    return mix(hex_color, "#ffffff", amount)


def banner_gradient_css(hex_color):
    """Gradient from calendarColor to a lighter version of it, with the
    50/50 blend point placed 1/3 of the way UP from the bottom (i.e. 67%
    down from the top) rather than at the usual 50% — keeps the banner's
    upper two-thirds close to the base color, then lightens quickly near
    the bottom, per the design spec."""
    light = lighten(hex_color, 0.38)
    midpoint = mix(hex_color, light, 0.5)
    return f"linear-gradient(to bottom, {hex_color} 0%, {midpoint} 67%, {light} 100%)"


def readable_text_color(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1c1c1e" if luminance > 0.72 else "#ffffff"


# ----------------------------------------------------------------- text util

def esc(value):
    return html.escape(str(value), quote=True)


def shorten_alert(alert):
    """'30 minutes before' -> '30 min before'; 'None' -> None."""
    if not alert or alert.strip().lower() == "none":
        return None
    return re.sub(r"\bminutes?\b", "min", alert.strip())


MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def parse_mdy(date_str):
    m, d, y = date_str.strip().split("/")
    return datetime.date(int(y), int(m), int(d))


def parse_event_date(event_date):
    """'10/27/2026' -> (date, None); '10/19/2026-10/23/2026' -> (date, date)."""
    parts = event_date.split("-")
    start = parse_mdy(parts[0])
    end = parse_mdy(parts[1]) if len(parts) > 1 else None
    return start, end


def parse_hour_label(label):
    """'9am' / '1:30pm' -> 24-hour integer hour (minutes dropped for the
    schedule grid, which is laid out in whole-hour rows)."""
    m = re.match(r"\s*(\d+)(?::\d+)?\s*([ap]m)\s*$", label, re.I)
    if not m:
        raise ValueError(f"can't parse hour label: {label!r}")
    hour = int(m.group(1)) % 12
    if m.group(2).lower() == "pm":
        hour += 12
    return hour


def format_hour_label(hour24):
    h = hour24 % 12
    h = 12 if h == 0 else h
    suffix = "am" if hour24 < 12 else "pm"
    return f"{h}{suffix}"


def weekday_month_day_year(date_obj):
    return date_obj.strftime("%A"), date_obj.strftime("%B %-d, %Y")


def month_day_lower(date_obj):
    return date_obj.strftime("%b %-d").lower()


def parse_booked_date(booked_date, year):
    """'Monday, October 19' (no year in the source data) -> date, paired
    with the schedule's own start-date year."""
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})\s*$", booked_date)
    month_name, day = m.group(1), int(m.group(2))
    month = MONTHS[month_name.lower()]
    return datetime.date(year, month, day)


# --------------------------------------------------------------------- shell

PAGE_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
<div class="calendar-card-page">
{card}
</div>
</body>
</html>
"""

BASE_CSS = """
:root {
  color-scheme: light;
}
body {
  margin: 0;
  background: #eef0f3;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif;
}
.calendar-card-page {
  min-height: 100vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 20px;
  box-sizing: border-box;
}
.calendar-card {
  width: 100%;
  border-radius: 28px;
  box-shadow: 0 10px 34px rgba(20, 20, 30, 0.16);
  overflow: visible;
  background: #fff;
}
.calendar-card__banner {
  border-radius: 28px 28px 0 0;
  padding: 30px 28px 26px;
  text-align: center;
  color: #fff;
  box-sizing: border-box;
}
.calendar-card__banner .weekday,
.calendar-card__banner .date {
  font-size: 34px;
  font-weight: 500;
  line-height: 1.18;
  margin: 0;
}
.calendar-card__banner .title {
  font-size: 38px;
  font-weight: 600;
  margin: 6px 0;
}
.calendar-card__body {
  border-radius: 0 0 28px 28px;
  background: #fff;
  padding: 26px 28px 6px;
  box-sizing: border-box;
}
.calendar-card__title {
  font-size: 27px;
  font-weight: 600;
  color: #111113;
  margin: 0 0 8px;
  line-height: 1.22;
}
.calendar-card__footer {
  text-align: center;
  color: #c3c3c8;
  font-size: 15px;
  padding: 18px 28px 26px;
}
"""

EVENT_CSS = """
.event-meta {
  font-size: 18px;
  color: #9a9aa0;
  margin: 0 0 14px;
}
.event-meta .alert {
  color: #c3c3c8;
  margin-left: 8px;
}
.event-subtitle {
  font-size: 19px;
  color: #1c1c1e;
  line-height: 1.4;
  margin: 0 0 12px;
}
.event-location {
  font-size: 16px;
  color: #9a9aa0;
  margin: 0 0 6px;
}
"""

TASK_CSS = """
.task-repeat {
  font-size: 17px;
  color: #9a9aa0;
  margin: 0 0 16px;
}
.task-list {
  list-style: none;
  margin: 0;
  padding: 0 0 10px;
}
.task-list li {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  font-size: 19px;
  color: #1c1c1e;
  padding: 6px 0;
  line-height: 1.35;
}
.task-bullet {
  width: 15px;
  height: 15px;
  border: 2px solid #c3c3c8;
  border-radius: 50%;
  flex: 0 0 auto;
  margin-top: 5px;
}
.task-list .task-principal .task-subtitle {
  color: #9a9aa0;
  font-weight: 400;
  margin-left: 6px;
}
"""

SCHEDULE_CSS = """
.schedule-range {
  display: flex;
  justify-content: space-between;
  padding: 22px 28px 2px;
  font-size: 15px;
  font-weight: 500;
  box-sizing: border-box;
}
.schedule-grid-wrap {
  display: flex;
  align-items: flex-start;
  padding: 0 28px 4px;
  box-sizing: border-box;
}
.schedule-hours {
  flex: 0 0 auto;
  width: 50px;
  padding-right: 8px;
  box-sizing: border-box;
}
.schedule-hour {
  height: 72px;
  font-size: 14px;
  font-weight: 500;
  padding-top: 2px;
  text-align: right;
  box-sizing: border-box;
}
.schedule-grid {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: repeat(var(--days), 1fr);
  grid-auto-rows: 72px;
  border-top: var(--grid-border-width) solid var(--grid-border-color);
  border-left: var(--grid-border-width) solid var(--grid-border-color);
}
.schedule-cell {
  border-right: var(--grid-border-width) solid var(--grid-border-color);
  border-bottom: var(--grid-border-width) solid var(--grid-border-color);
  min-height: 72px;
  position: relative;
}
.booking {
  position: absolute;
  inset: 2px;
  border-radius: 10px;
  padding: 7px 9px;
  box-sizing: border-box;
  color: #fff;
  cursor: default;
  z-index: 1;
}
.booking__name {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.2;
}
.booking__service {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.25;
  margin-top: 2px;
}
.booking__details {
  position: absolute;
  left: 0;
  right: 0;
  top: 100%;
  margin-top: -10px;
  padding: 14px 9px 10px;
  border-radius: 0 0 10px 10px;
  font-size: 12px;
  line-height: 1.4;
  opacity: 0;
  transform: translateY(-4px);
  pointer-events: none;
  transition: opacity 0.12s ease, transform 0.12s ease;
  z-index: 2;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.12);
}
.booking:hover {
  z-index: 10;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
}
.booking:hover .booking__details {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}
.booking__notes {
  margin-bottom: 6px;
}
.booking__contact {
  opacity: 0.92;
}
.booking__alert {
  margin-top: 6px;
  opacity: 0.92;
}
"""


def render_shell(title, extra_css, card_html):
    return PAGE_SHELL.format(title=esc(title), css=BASE_CSS + extra_css, card=card_html)


# ---------------------------------------------------------------- Event card

def render_event(data):
    color = data["calendarColor"]
    text_color = readable_text_color(color)
    date_obj, _ = parse_event_date(data["eventDate"])
    weekday, month_day_year = weekday_month_day_year(date_obj)

    alert_html = ""
    alert = shorten_alert(data.get("alert"))
    if alert:
        alert_html = f'<span class="alert">(notify {esc(alert)})</span>'

    card = f"""<div class="calendar-card calendar-card--event">
  <div class="calendar-card__banner" style="background:{banner_gradient_css(color)}; color:{text_color};">
    <p class="weekday">{esc(weekday)}</p>
    <p class="date">{esc(month_day_year)}</p>
  </div>
  <div class="calendar-card__body">
    <h1 class="calendar-card__title">{esc(data['eventTitle'])}</h1>
    <p class="event-meta">{esc(data['eventTime'])} {alert_html}</p>
    <p class="event-subtitle">{esc(data['eventSubtitle'])}</p>
    <p class="event-location">Location: {esc(data['location'])}</p>
  </div>
  <div class="calendar-card__footer">Calendar: {esc(data['calendar'])}</div>
</div>"""
    return render_shell(data["eventTitle"], EVENT_CSS, card)


# ----------------------------------------------------------------- Task card

def render_task(data):
    color = data["calendarColor"]
    text_color = readable_text_color(color)
    date_obj, _ = parse_event_date(data["eventDate"])
    weekday, month_day_year = weekday_month_day_year(date_obj)

    repeat_html = ""
    if data.get("repeat"):
        repeat_html = f'<p class="task-repeat">Repeats {esc(data["repeat"])}</p>'

    items = [
        f'<li class="task-principal"><span class="task-bullet"></span>'
        f'<span><strong>{esc(data["principalTask"])}</strong> '
        f'<span class="task-subtitle">{esc(data["eventSubtitle"])}</span></span></li>'
    ]
    for sub in data.get("subTasks", []):
        items.append(f'<li><span class="task-bullet"></span><span>{esc(sub)}</span></li>')

    card = f"""<div class="calendar-card calendar-card--task">
  <div class="calendar-card__banner" style="background:{banner_gradient_css(color)}; color:{text_color};">
    <p class="weekday">{esc(weekday)}</p>
    <p class="date">{esc(month_day_year)}</p>
  </div>
  <div class="calendar-card__body">
    <h1 class="calendar-card__title">{esc(data['eventTitle'])}</h1>
    {repeat_html}
    <ul class="task-list">
      {''.join(items)}
    </ul>
  </div>
  <div class="calendar-card__footer">Calendar: {esc(data['calendar'])}</div>
</div>"""
    return render_shell(data["eventTitle"], TASK_CSS, card)


# ---------------------------------------------------------- Appointment card

def render_appointment(data):
    color = data["calendarColor"]
    text_color = readable_text_color(color)
    header_text_color = "#ffffff"
    start_date, end_date = parse_event_date(data["eventDate"])
    if end_date is None:
        end_date = start_date
    num_days = (end_date - start_date).days + 1

    start_hour = parse_hour_label(data["eventTime"].split("-")[0].strip())
    num_rows = 8

    hour_labels = [format_hour_label(start_hour + r) for r in range(num_rows)]

    # Build empty day x hour slots, then drop each booking into its cell.
    slots = {(d, r): [] for d in range(num_days) for r in range(num_rows)}
    for booking in data.get("bookings", []):
        b_date = parse_booked_date(booking["bookedDate"], start_date.year)
        day_idx = (b_date - start_date).days
        hour_idx = parse_hour_label(booking["bookedTime"]) - start_hour
        if 0 <= day_idx < num_days and 0 <= hour_idx < num_rows:
            slots[(day_idx, hour_idx)].append(booking)

    booking_bg = color
    details_bg = lighten(color, 0.22)

    hours_html = []
    cells_html = []
    for r in range(num_rows):
        hours_html.append(f'<div class="schedule-hour" style="color:{color};">{esc(hour_labels[r])}</div>')
        for d in range(num_days):
            bookings_here = slots[(d, r)]
            inner = ""
            for booking in bookings_here:
                alert = shorten_alert(booking.get("alert"))
                alert_html = f'<div class="booking__alert">\U0001F514 {esc(alert)}</div>' if alert else ""
                inner += f"""<div class="booking" style="background:{booking_bg}; color:{text_color};">
  <div class="booking__name">{esc(booking['name'])}</div>
  <div class="booking__service">{esc(booking['service'])}</div>
  <div class="booking__details" style="background:{details_bg}; color:{text_color};">
    <div class="booking__notes">{esc(booking['notes'])}</div>
    <div class="booking__contact">{esc(booking['email'])}<br>{esc(booking['phone'])}</div>
    {alert_html}
  </div>
</div>"""
            cells_html.append(f'<div class="schedule-cell">{inner}</div>')

    card = f"""<div class="calendar-card calendar-card--appointment">
  <div class="calendar-card__banner" style="background:{banner_gradient_css(color)}; color:{header_text_color};">
    <p class="title">{esc(data['eventTitle'])}</p>
  </div>
  <div class="calendar-card__body" style="padding-left:0; padding-right:0;">
    <div class="schedule-range" style="color:{color};">
      <span>{esc(month_day_lower(start_date))}</span>
      <span>{esc(month_day_lower(end_date))}</span>
    </div>
    <div class="schedule-grid-wrap">
      <div class="schedule-hours">
        {''.join(hours_html)}
      </div>
      <div class="schedule-grid" style="--days:{num_days}; --grid-border-color:{color}; --grid-border-width:1.5px;">
        {''.join(cells_html)}
      </div>
    </div>
  </div>
  <div class="calendar-card__footer">Calendar: {esc(data['calendar'])}</div>
</div>"""
    return render_shell(data["eventTitle"], SCHEDULE_CSS, card)


RENDERERS = {
    "Event": render_event,
    "Task": render_task,
    "Appointment schedule": render_appointment,
}


def main():
    if len(sys.argv) != 3:
        print("Usage: build_calendar_html.py input.json output.html", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    renderer = RENDERERS.get(data.get("eventKind"))
    if renderer is None:
        raise ValueError(f"Unknown eventKind: {data.get('eventKind')!r}")

    html_out = renderer(data)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"Wrote {sys.argv[2]}")


if __name__ == "__main__":
    main()
