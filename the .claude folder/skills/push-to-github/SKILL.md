---
name: push-to-github
description: Use when the user says "push to github" (or asks to publish the current project to GitHub). Creates a public GitHub repo, pushes the project, adds a generated README.md, tags the last commit v1.0, and pushes the tag.
---

# Push to GitHub

Publish the current project to the user's GitHub as a **public** repo, add a README, and tag a v1.0 release. Run every step from the project's root folder.

## 0. Preflight

1. Confirm `git` and the GitHub CLI `gh` are installed (`git --version`, `gh --version`). If `gh` is missing, tell the user how to install it (https://cli.github.com) and stop.
2. Run `gh auth status`. If not logged in, ask the user to run `gh auth login` themselves, then continue. Never type tokens or passwords on their behalf.
3. Repo name = the project folder's name (lowercase, spaces → hyphens) unless the user gave one. Run `gh repo view <user>/<name>`; if it already exists, ask whether to use a different name or push to the existing repo.

## 1. Safety check before going public

The repo will be **public**, so before the first commit:

- Make sure a `.gitignore` exists and covers the obvious: `.env*`, `node_modules/`, `__pycache__/`, `.venv/`, `dist/`, `build/`, `.DS_Store`, and anything else fitting the project's language.
- Scan the files to be committed for secrets (API keys, tokens, private keys, passwords, `.env` files, credentials JSON). If anything looks like a secret, **stop** and show the user the file and line. Do not push until they decide.

## 2. Create the repo, commit and push the project

```bash
git init -b main            # skip if already a git repo
git add -A
git commit -m "Initial commit"   # skip if nothing to commit
gh repo create <name> --public --source=. --remote=origin --push
```

If an `origin` remote already exists, ask before replacing it.

## 3. Generate README.md, commit and push it

Read the project (entry points, package.json / pyproject.toml / requirements.txt / Cargo.toml / go.mod, main source files) and write a `README.md` with:

- Project title and a one-paragraph description of what it does
- Features (short bullets, only what the code actually does)
- Tech stack
- Installation / setup steps
- Usage (commands or a short example)
- Project structure (top-level folders/files, one line each)
- License line (only if a LICENSE file exists; otherwise omit)

Base everything on the real code — don't invent features. If a README.md already exists, ask whether to overwrite it or improve it.

```bash
git add README.md
git commit -m "Add README"
git push origin main
```

## 4. Tag v1.0 and push the tag

```bash
git tag -a v1.0 -m "Release v1.0"
git push origin v1.0
```

If `v1.0` already exists locally or on the remote, ask before moving or replacing it.

## 5. Report back

Tell the user, briefly:
- The repo URL (`gh repo view --json url -q .url`)
- That it's public, the README was added, and `v1.0` points at the README commit
- Anything that was skipped or needs their attention
