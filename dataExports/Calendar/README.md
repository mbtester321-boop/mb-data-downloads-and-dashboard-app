# How to read the downloaded Google Calendar data

Each sub-folder here is one downloaded calendar item (an Event, a Task, or a week of an Appointment schedule), named:

```
<eventTitleInCamelCase>_<mmddyyyy>
```

e.g. `Empire State Building/empireStateBuildingObservationDeck_10092026` → the event "Empire State Building Observation Deck" on 10/09/2026. Inside each folder:

| File | What it is |
|---|---|
| `<name>_<date>.rtf` | **The actual downloaded data** — the event's fields written using the fixed notation described below. This is the file to read for the raw local copy of the calendar item. |
| `<name>_<date>.html` | An auto-generated preview page (built from the `.rtf`) used by the dashboard website to show a live rendering of the event card in the browser. Not part of the raw downloaded format itself. |
| `*.png` | A screenshot of the real event as it appears on Google Calendar, for side-by-side comparison. |

The three `calendarDownloadTemplate*.rtf` files in this folder (`...Event.rtf`, `...Task.rtf`, `...Appointment.rtf`) are the **blank templates/legends** — they are not real events, they're the three patterns a downloaded `.rtf` can follow, one per `eventKind`.

## Opening a `.rtf` file

Plain RTF — open with Preview/TextEdit/Word, or from the Terminal:

```bash
textutil -convert txt -stdout "Calendar/<folder>/<name>_<date>.rtf"
```

## Fields every calendar file starts with

```
<calendar>Calendar name
<calendarColor>#RRGGBB
<eventKind>Event | Task | Appointment schedule
<eventTitle>Title of the item
<eventDate>mm/dd/yyyy                          (or mm/dd/yyyy-mm/dd/yyyy for a schedule's week)
<eventTime>6pm-9pm | AllDay | 9am-4pm
```

What follows depends on `<eventKind>`:

### `eventKind = Event`

```
<eventSubtitle>Description of the event
<alert>10 minutes before   (or "None" if there's no reminder)
<location>Address or place name
```

**Example** (`Empire State Building/empireStateBuildingObservationDeck_10092026.rtf`):
```
<calendar>Personal
<calendarColor>#D81B60
<eventKind>Event
<eventTitle>Empire State Building Observation Deck
<eventDate>10/09/2026
<eventTime>6pm-8pm
<eventSubtitle>Sunset views from the 86th floor observation deck.
<alert>None
<location>20 W 34th St, New York, NY 10001
```

### `eventKind = Task`

A Google Tasks checklist shown as an all-day chip on the calendar:

```
<repeat>Weekly on Sunday            (omitted if the task doesn't repeat)
<eventSubtitle>Description of the task
<contents
<Tasks
<PrincipalTask>Title of the checklist
<subTask>1. First checklist item
<subTask>2. Second checklist item
>
>
```
`<contents` and `<Tasks` are each closed by their own `>` on a line by itself, in order (innermost first).

### `eventKind = Appointment schedule`

One file covers a whole week of bookings:

```
<eventSubtitle>Description of the schedule
<contents
<bookBlock
<bookedDate>Monday, October 19
<bookedTime>10am
<bookedBy
<Name>Alex Morgan
<email>alex.morgan@example.com
<phone>(212) 555-0148
>
<service>30-min strategy consultation
<notes>Free-text notes about this booking
<location>meet.google.com/xxx-xxxx-xxx
<alert>30 minutes before
>
... one <bookBlock ... > per booking that week ...
>
```
`<bookedBy` closes with its own `>`, each `<bookBlock` closes with its own `>`, and a final `>` closes `<contents` after the last booking.

## Quick reference: what each symbol/field means

| Field | Meaning |
|---|---|
| `<calendarColor>` | The hex color of the calendar the item lives on, as shown in Google Calendar's sidebar. |
| `<eventTime>` | 12-hour, lowercase am/pm, no space, `:00` minutes dropped (e.g. `6:30pm-9pm`); `AllDay` for Tasks. |
| `<alert>` | The reminder offset in effect for this item (its own override, or the calendar's default); `None` if no reminder applies. |
| `<bookedTime>` | A single start time for that booking (not a range). |
