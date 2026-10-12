# Yettel Homepage Link Monitor — update

This update checks links discovered dynamically on `https://www.yettel.bg/`.
It does not crawl the linked pages for further links. It requests each discovered
HTTP(S) destination only to check its response.

## Files to copy into the existing repository

- `checker.py` — replace the existing checker
- `requirements.txt` — replace the existing requirements file
- `.github/workflows/check.yml` — replace the existing workflow

`urls.json` is no longer used by this checker. It can remain in the repository,
but the new checker discovers the current links from the homepage each run.

## Run it

1. Open the repository on GitHub.
2. Open each file listed above and choose the pencil (Edit) action.
3. Replace the file contents with the matching file from this package.
4. Commit the changes.
5. Open **Actions → Yettel Homepage Link Monitor → Run workflow** to test it.
6. Open the completed run and download the `yettel-homepage-link-report` artifact.
   It contains `results.json`, including broken links and the page areas where
   those links were found.

The scheduled run is daily at 06:00 UTC. GitHub Actions schedules can start late
when GitHub is busy. Change the cron expression in `check.yml` if needed.

## What counts as broken

- HTTP status 400 or higher
- Request failures such as timeouts or DNS/TLS errors

Redirects are followed and the final status is checked. Non-HTTP links such as
`mailto:`, `tel:`, `javascript:` and in-page anchors are skipped.

The source area is recorded as `header`, `footer`, or `main/page`. Duplicate
destinations are checked once, with all discovered source locations retained.

## Limitations

- Links must exist in the rendered homepage DOM. A link that only appears after
  a specific interaction (for example, opening a menu that injects new HTML) may
  require a later targeted addition to the discovery step.
- Some destinations may block automated requests or return 403/429 to the
  checker even though they work in a normal browser. Review those results before
  treating them as confirmed site defects.
- This checks link destinations, not visual appearance, image loading, or the
  contents and links of destination pages.
