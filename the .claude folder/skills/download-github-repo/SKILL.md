---
name: download-github-repo
description: Use when the user says "download github repository" / "download this repo" / "download repo from github" / "get me this github repo" / pastes a github.com repo link and wants its files locally. Downloads all files from a GitHub repository URL into a plain folder (named after the repo) in the current working directory — not a git clone the user will keep working in, just the files.
---

# Download GitHub Repository

Get every file from a GitHub repo URL into a plain folder in the current working directory. The result is a snapshot of the files, not a usable git repo — no `.git` directory, no history, nothing to commit to.

## 1. Parse the URL

Accepted forms:
- `https://github.com/owner/repo`
- `https://github.com/owner/repo.git`
- `https://github.com/owner/repo/tree/<branch>` (and deeper paths under it)
- `git@github.com:owner/repo.git`

Extract `owner`, `repo` (strip a trailing `.git`), and — if the URL points at a specific branch via `/tree/<branch>` — that `branch`. Otherwise use the repo's default branch.

The target folder name is just `repo`, created directly in the current working directory (not nested under anything else) unless the user asked for a different location or name.

If a folder with that name already exists there, stop and ask the user whether to overwrite it, pick a different name, or cancel — don't clobber something that might be their own work.

## 2. Download it

Prefer `git` since it's simpler and handles branches cleanly:

```bash
git clone --depth 1 ${branch:+--branch "$branch"} "<repo-url>" "<target-folder>"
rm -rf "<target-folder>/.git"
```

`--depth 1` skips downloading full history since only the current files are wanted.

If `git` isn't available, or the clone fails with an auth/network error worth falling back on, use the GitHub API + zip archive instead:

```bash
# Resolve the default branch if none was given in the URL
branch=$(curl -fsSL "https://api.github.com/repos/<owner>/<repo>" | grep -m1 '"default_branch"' | cut -d'"' -f4)

curl -fsSL "https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip" -o /tmp/repo.zip
unzip -q /tmp/repo.zip -d /tmp/repo-extract
mv /tmp/repo-extract/<repo>-<branch> "<target-folder>"
rm -rf /tmp/repo.zip /tmp/repo-extract
```

GitHub's zip archive always names the extracted folder `<repo>-<branch>` (slashes in the branch name become dashes), so adjust that match accordingly.

## 3. Handle private repos

If the clone/download fails with a 404 or auth error, the repo may be private. Check `gh auth status` — if the user is logged into the GitHub CLI, re-try the clone (it will use those credentials automatically) or use `gh repo clone owner/repo "<target-folder>"` instead. If they're not authenticated, tell them so and don't attempt to guess credentials.

## 4. Report back

Tell the user, briefly:
- Where the folder landed (path, relative to the working directory)
- Which branch/ref was downloaded
- A one-line sense of what's in it (e.g. "142 files" or the top-level entries) — a quick `ls` or `find . -type f | wc -l` in the new folder is enough, no need to summarize contents in depth
