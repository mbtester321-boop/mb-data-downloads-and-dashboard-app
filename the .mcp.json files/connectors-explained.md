# Why Your Connectors Aren't in This Project's `.mcp.json`

## The short answer

There is no `.mcp.json` in it (only `connectors.png`). That's on purpose — the connectors i'm using are **account-level integrations**, configured in Claude.ai settings, not **project-level MCP servers** defined in a local `.mcp.json` file.

## The two different systems


|                    | Project `.mcp.json`                                             | Claude.ai Connectors                                                       |
| ------------------ | --------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Where it lives** | A file inside a specific project folder                         | Your Claude account settings (claude.ai)                                   |
| **Scope**          | Only active when Claude Code is run from that project directory | Active in every conversation/session on your account, regardless of folder |
| **Who sets it up** | Me, by hand-editing JSON (server command, args, env vars)       | Me, via the Claude.ai UI (OAuth/connect flow)                              |
| **Portability**    | Tied to that one repo/folder — moves with the project           | Tied to your account — follows you everywhere you use Claude               |
| **Typical use**    | Custom/internal tools specific to one codebase                  | Third-party apps (Gmail, Notion, GitHub, etc.) you want everywhere         |


Because the connectors below are connected through me Claude.ai account (not written into a project `.mcp.json`), they show up in **every** session I start — this project included — even though no config file here declares them.

## Currently connected connectors (this account)

Based on the tools available in this session, the following connectors are active on my Claude account:

1. **Claude Docs** — create/read/edit/export living documents
2. **Claude MCP Integration (GitHub)** — repos, issues, PRs, branches, commits, reviews
3. **Gmail** — read, search, label, draft, send, and manage email
4. **Google Calendar** — list, search, create, update, and respond to events
5. **Notion** — pages, databases, comments, Notion Calendar, memory/search
6. **Zoom for Claude** — meetings, recordings, canvas files, search

Additionally, **Claude in Chrome** is enabled — this is a browser *extension* (not a claude.ai account connector) that lets Claude control your actual Chrome browser (tabs, clicks, forms, screenshots, console logs).

