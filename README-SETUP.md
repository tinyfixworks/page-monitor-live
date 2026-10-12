# Linkwatch — Yettel homepage link monitor

This package updates the current homepage checker and adds a static dashboard.

## Files to copy into the repository root

- `checker.py`
- `index.html`
- `app.js`
- `style.css`
- `.github/workflows/check.yml`

Keep your existing `requirements.txt`. It must include `playwright` (and any other packages already required by your checker).

## What it does

- Checks unique HTTP(S) links found on the Yettel homepage.
- Ignores links inside `#CybotCookiebotDialog`.
- Records source text, page area, nearest section heading, image alt/src, element type and a DOM path.
- Saves `results.json` and commits the latest report so GitHub Pages can read it.
- Runs daily at 06:00 UTC.
- The dashboard has no button to start a check. `workflow_dispatch` remains available only from GitHub Actions to users with repository permissions.

Status handling:
- 404/410 and other unambiguous HTTP 4xx responses are classified as broken.
- 401/403/429, 5xx and request/network exceptions are classified as needs review, since they do not always mean the destination is broken.

## GitHub Pages setup

1. Copy the files above into the repository, replacing the existing versions.
2. Commit and push the changes.
3. Open **Settings → Pages** in the repository.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select the default branch and `/ (root)`, then save.
6. Open **Actions**, run **Yettel Homepage Link Monitor** once manually, and wait for it to finish. This produces and commits `results.json`.
7. Open the GitHub Pages URL shown in **Settings → Pages**.

The first dashboard visit may show “Report unavailable” until the first successful workflow has generated `results.json`.

## Security / public repository

The dashboard intentionally has no “run check” button and does not call the GitHub API to trigger a workflow. The workflow's manual trigger can only be started by someone with suitable repository permissions. The public dashboard displays the report committed to the public repository.
