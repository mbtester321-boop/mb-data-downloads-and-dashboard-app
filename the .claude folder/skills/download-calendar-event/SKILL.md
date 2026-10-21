---
name: download-calendar-event
description: Use when the user says "download the Google Calendar event(s)" / "save this calendar event" / "download [event title]" referring to something on their Google Calendar. Saves each Task or Event as its own .rtf file (built from calendarDownloadTemplate*.rtf); an Appointment schedule is saved one week at a time as a single .rtf containing every booking that week. Files are named eventTitleInCamelCase_mmddyyyy.rtf.
---

# Download Calendar Event

Save Google Calendar items to local `.rtf` files that follow the three patterns
in `assets/calendarDownloadTemplateEvent.rtf`, `assets/calendarDownloadTemplateTask.rtf`,
and `assets/calendarDownloadTemplateAppointment.rtf`. All three start with the
same six fields (`calendar`, `calendarColor`, `eventKind`, `eventTitle`,
`eventDate`, `eventTime`); what follows depends on `eventKind`.

Use the `mcp__claude_ai_Google_Calendar__*` tools to fetch data — never ask the
user to paste event details by hand unless those tools are unavailable or the
data genuinely isn't reachable through them (see step 1b).

## 0. Identify the target

Figure out which calendar item(s) the user means (by title, date, or what's
currently open). If ambiguous, ask.

A single request can mean:
- **One Task or Event** → one output file.
- **An Appointment schedule for a week** → one output file covering that whole
  week (Mon–Sun as named, or whatever span the user gives).

## 1a. Fetch Event / Task data (Calendar API)

Use `list_calendars` to find the calendar, then `list_events` (or `get_event`)
to fetch the item. Map fields:

- `calendar` = the calendar's `summary`.
- `eventTitle` = the event's `summary`.
- `eventDate` = `start.date`/`start.dateTime` as `mm/dd/yyyy`.
- `eventTime` = `start`–`end` as `6pm-9pm` (12-hour, lowercase am/pm, no space,
  drop `:00` minutes but keep them if non-zero, e.g. `6:30pm-9pm`).
- `eventSubtitle` = the event's `description`.
- `location` = the event's `location`.
- `alert`:
  - If `overrideReminders` is present, use its `minutes` value as `"N minutes
    before"`.
  - Else if `useDefaultReminders` is true, use the **calendar's** own
    `defaultReminders` (from `list_events`' top-level response for that
    calendar) the same way.
  - If neither exists (calendar has no default notification configured),
    write `"None"` — don't invent a value.

**A regular `Event`** (eventType `DEFAULT`, not a Tasks item) uses
`calendarDownloadTemplateEvent.rtf`'s shape: `eventSubtitle`, `alert`,
`location`.

## 1b. Fetch Task data — Google Tasks are NOT in the Calendar API

A "Task" here means a Google Tasks list item that shows as an all-day chip on
the calendar. **The Calendar API tools cannot read these** — `list_events`
will not return them, and there's no Tasks-API tool available. To fetch a
Task's content, use Claude in Chrome (load its tools per the chrome-browser
skill) against `calendar.google.com`:

1. Make sure the right Google account is active in the browser tab (check the
   account switcher — a test/secondary Google account won't be the browser's
   default signed-in one; switch to it first if needed, and navigate with the
   matching `/calendar/u/N/...` index).
2. Navigate to the week containing the task; click the task's chip to open its
   small popup (title, date, `Weekly on <Day>` repeat info if any,
   description, and a link to its Tasks list).
3. Click that Tasks-list link to open the full list in the right-hand Tasks
   panel — this is where the numbered checklist items actually live; the
   small popup alone doesn't show them.
4. Read off: title (`eventTitle` / `principalTask`), date, repeat line
   (strip any `", until ..."` clause — just keep `"Weekly on <Day>"`),
   description (`eventSubtitle`), and each checklist line in order
   (`subTasks`, keep the user's own numbering/text as-is).
5. For `calendarColor`: open the calendar's `⋮` menu in the left sidebar
   (**not** its checkbox — toggling that changes what's visible; restore any
   checkbox you accidentally click before moving on) and read which swatch is
   checked. Get its exact hex via
   `javascript_tool`: query every `[aria-label*="set calendar color"]`
   element's `getComputedStyle(el).backgroundColor`, find the one with
   `aria-checked="true"` (filter to `offsetParent !== null` — closed menus
   leave stale nodes in the DOM), and convert that `rgb(...)` to hex.

`eventTime` is always `AllDay`. `eventKind` is `Task`. Shape follows
`calendarDownloadTemplateTask.rtf`: optional `repeat`, `eventSubtitle`,
`<contents<Tasks<PrincipalTask>...` then one `<subTask>` per checklist item,
closed by two `>` lines (closes `Tasks`, then `contents`).

## 1c. Fetch an Appointment schedule's week (Calendar API)

Each booking is its own Calendar event on the bookings calendar, titled like
`"Book Me (Alex Morgan)"`, with a `description` such as:

```
<b>Booked by</b>
Alex Morgan
alex.morgan@example.com
(212) 555-0148
<br><b>Service</b>
30-min strategy consultation
<br><b>Notes</b>
First-time client, wants to discuss Q4 marketing plan.
```

Use `list_events` on that calendar across the requested week. For each
booking, parse the description into `name`/`email`/`phone` (the three lines
after "Booked by"), `service` (line after "Service"), and `notes` (text after
"Notes"). `location` = `conferenceUrl` with the `https://` prefix stripped.
`bookedDate` = `"<Weekday>, <Month> <Day>"` from the booking's `start`.
`bookedTime` = the booking's own start time only (not a range), same
12-hour/no-colon-on-the-hour convention as `eventTime`, e.g. `10am` or
`1:30pm`. `alert` = same reminder logic as step 1a, evaluated per booking
(it's usually the calendar's own `defaultReminders`, since bookings typically
use `useDefaultReminders: true`).

Top-level fields for the file: `calendar` = the schedule calendar's name,
`eventTitle` = the schedule's own name (e.g. "Book Me" — visible in the
"Booking pages" section of the sidebar, or strip the `" (Name)"` suffix off
any booking's `summary`), `eventDate` = `"mm/dd/yyyy-mm/dd/yyyy"` for the
week's start–end, `eventTime` = the earliest booking start to the latest
booking end that week as `9am-4pm` (the schedule's actual configured
availability window isn't exposed by these tools, so this span is a
reasonable stand-in — say so if the user cares about exact hours).
`eventSubtitle` = a short description of the schedule (reuse the schedule's
own description if you have it, otherwise something like `"<duration> min
bookable appointments"` inferred from the bookings).

Shape follows `calendarDownloadTemplateAppointment.rtf`: `<contents` then one
`<bookBlock ... >` per booking — `bookedDate`, then `bookedTime`, then its
internally-closed `<bookedBy ... >` block, then `service`/`notes`/`location`/
`alert` — and a final `>` closing `contents`.

## 2. Build the .rtf

Write a JSON file matching the schema documented at the top of
`scripts/build_calendar_rtf.py`, then run:

```bash
python3 ~/.claude/skills/download-calendar-event/scripts/build_calendar_rtf.py <input.json> "<filename>.rtf"
```

This script — not hand-typed RTF — produces the file; the RTF control codes
and nesting (which tags get a closing `>` line and which don't) are easy to
get subtly wrong by hand. Reference the three files in `assets/` if you need
to double-check the tag conventions for a given `eventKind`.

Sanity-check the result once per session (not required every run) with:
```bash
textutil -convert txt -stdout "<filename>.rtf"
```
If that errors, the RTF is malformed — fix the script input, don't hand-patch
the `.rtf` output.

## 3. Name and save the file

`eventTitleCamelCase_mmddyyyy.rtf`, where:
- The camelCase conversion: lowercase the first word entirely; for every
  later word, capitalize its first letter and lowercase the rest; drop all
  spaces and punctuation. Get this directly from the script rather than
  doing it by hand:
  ```bash
  python3 ~/.claude/skills/download-calendar-event/scripts/build_calendar_rtf.py --filename "Walk the Brooklyn Bridge"
  # -> walkTheBrooklynBridge
  ```
- `mmddyyyy` = the event's date (for a Task/Event: its own date; for an
  Appointment schedule: the **start** of the downloaded week).

Save directly in the **current working directory** (no folder needed — unlike
emails, there's no attachment to bundle) unless the user names a different
destination. If a file with this exact name already exists, ask before
overwriting.

## 4. Report back

Tell the user, briefly: the filename(s) written, the `eventKind` used for
each, and for an Appointment schedule, how many bookings it contains. Flag
anything you had to approximate (e.g. a missing default reminder written as
`"None"`, or an inferred `eventTime` span for a booking week).
