# Dashboard Web App

This is the local dashboard website for the "Working With Third Party Services" project. It's a static, no-build web app that displays the data downloaded from Gmail, GitHub, Notion, and Google Calendar, side by side with the original content from each service.

**Live site (hosted via GitHub Pages):** https://mbtester321-boop.github.io/mb-data-downloads-and-dashboard-app/

## What it does

- A home page (`index.html`) with a tile for each connected service.
- One page per service — `gmail.html`, `github.html`, `notion.html`, `calendar.html` — each showing a grid of cards for every downloaded item from that service.
- Clicking a card opens a modal with three views:
  - **View** — a live, interactive preview of the downloaded item rendered in the browser.
  - **Downloaded File** — the raw local file(s) that were saved for that item (the actual stored data/metadata).
  - **Original** — a screenshot of the item as it appeared in the real service, for comparison.
- Keyboard navigation in the modal (←/→ to switch slides, Esc to close).

## Folder structure

```
.
├── index.html              # Landing page / service picker
├── github.html             # GitHub gallery page
├── gmail.html               # Gmail gallery page
├── calendar.html             # Google Calendar gallery page
├── notion.html               # Notion gallery page
├── assets/
│   ├── css/style.css         # Shared site styling
│   ├── js/main.js             # Shared gallery/modal rendering logic
│   ├── js/data-github.js      # GitHub item data (used by github.html)
│   ├── js/data-gmail.js       # Gmail item data (used by gmail.html)
│   ├── js/data-notion.js      # Notion item data (used by notion.html)
│   ├── js/data-calendar.js    # Calendar item data (used by calendar.html)
│   └── img/                  # Service icons + GitHub screenshot thumbnails
├── GitHub/                  # Downloaded GitHub repos (one folder per repo), used as the live previews
├── Emails/                   # Downloaded Gmail messages (one folder per email)
├── Notion/                   # Downloaded Notion pages (one .csv per page)
└── Calendar/                 # Downloaded Calendar events (one .rtf/.html per event)
```

Each `data-*.js` file defines a global array (e.g. `window.GITHUB_PROJECTS`) of objects describing one downloaded item: its title, the path to its live preview, the path to the original screenshot, and the raw file contents shown in the "Downloaded File" tab. The corresponding `*.html` page just loads that data file plus `main.js` and renders the grid — there's no backend and no build step.

## How to run it

This app is 100% static HTML/CSS/JS — it reads the data files above directly in the browser. Because the galleries load other local pages inside `<iframe>`s, open it through a local web server rather than double-clicking the file (some browsers restrict `file://` iframes/cross-file access).

From this folder, run one of:

```bash
# Python 3 (built in on macOS)
python3 -m http.server 8000

# Node (if you have it)
npx serve .
```

Then open **http://localhost:8000** in your browser and click through the tiles on the home page.

> If you only need the static preview with no interactivity, you can also just double-click `index.html` to open it directly — card thumbnails and screenshots will still show, but some live previews inside the modal may not load due to `file://` restrictions.

## Adding more data

To add another downloaded item to a service page, add a new entry to the matching `assets/js/data-<service>.js` array (same shape as the existing entries) and drop the actual downloaded file(s) into that service's data folder. No other code changes are needed — the page renders whatever is in the data array.
