# Working With Third-Party Services — Massimo Dashboard

## What this project is

This is a school project for a class on using Claude Code with third-party services. The goal was to connect Claude Code to several real online services through [MCP (Model Context Protocol)](https://modelcontextprotocol.io) servers, use Claude Code to download sample data from each one, save that data locally in a clearly documented format, and then build a small local website ("dashboard") that displays the downloaded data from every service in one place.

In short: **connect services → pull real test data → store it locally in a documented format → view it all in one dashboard.**

## Services connected

| Service | What was downloaded |
|---|---|
| **Gmail** | Test email messages (subject, body, sender/recipient, timestamp) |
| **GitHub** | Test repositories (full source files for each repo) |
| **Notion** | Test pages (exported as CSV, preserving text, formatting, and tables) |
| **Google Calendar** | Test events, tasks, and an appointment schedule |

All of these were accessed through official MCP connectors (not third-party/community ones), using throwaway test accounts created specifically for this assignment — no personal or real account data is included anywhere in this repo.

## How it's organized

```
.
├── dataExports/            # (a) The canonical downloaded data, one sub-folder per service
│   ├── Emails/
│   ├── GitHub/
│   ├── Notion/
│   └── Calendar/
├── the .claude folder/      # (b) Project-level Claude Code skills used to download & render each service's data
│   └── skills/
├── the .mcp.json files/      # (c) Notes on how the MCP connectors for this project are configured
├── index.html, *.html,       # (d) The dashboard web app itself — see README.md for how to run it
├── assets/                   #     (styles, scripts, icons, data used by the web app)
├── README.md                 # (d) Instructions for running the dashboard web app
├── README2.md                # (f) This file — project overview
├── Dashboard present.pptx     # (g) Project presentation
└── Project video.mp4          # (h) ~3 minute demo video
```

## The dashboard

The web app (`index.html` and friends) is a local, static website that reads the downloaded data above and shows it in one place. For each service you can browse every downloaded item as a card, and open a card to compare:

1. A live, interactive preview of the item,
2. The raw downloaded file(s)/metadata exactly as stored locally, and
3. A screenshot of the original item as it looked in the real service.

See **README.md** for how to run the dashboard locally.

## Claude Code skills

Repeatable, project-level Claude Code skills (stored in `the .claude folder/skills`) were built so that downloading and formatting new data from any of the four services follows the same consistent file format every time, without having to re-explain the format to Claude in a new conversation. There's a matching "download" skill and "show" skill for each service (e.g. `download-email` / `show-email`, `download-github-repo`, `download-notion-file` / `show-notion-file`, `download-calendar-event` / `show-calendar-event`), plus a `push-to-github` skill for publishing the finished project.

## Security note

This repo is public and intentionally contains **no real personal data, passwords, API keys, or OAuth secrets** — everything inside `dataExports` and the service folders is test content created in disposable test accounts for this assignment.
