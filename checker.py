
import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import urljoin, urldefrag, urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

SOURCE_URL = "https://www.yettel.bg/"
OUTPUT_FILE = "results.json"
REQUEST_TIMEOUT_MS = 20000
MAX_CONCURRENT_REQUESTS = 8


def normalize_url(raw_href, base_url):
    if not raw_href:
        return None

    href = raw_href.strip()
    if not href or href.startswith("#"):
        return None

    absolute = urljoin(base_url, href)
    absolute, _fragment = urldefrag(absolute)
    parsed = urlparse(absolute)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None

    return absolute


async def discover_links(page):
    await page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)

    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass

    await page.wait_for_timeout(2000)

    return await page.locator("a[href]").evaluate_all(
        """anchors => anchors
            .filter(a => !a.closest('#CybotCookiebotDialog'))
            .map(a => ({
                href: a.getAttribute('href'),
                text: (a.innerText || a.getAttribute('aria-label') || a.getAttribute('title') || '')
                    .replace(/\\s+/g, ' ').trim(),
                title: a.getAttribute('title') || '',
                area: a.closest('header') ? 'header'
                    : (a.closest('footer') ? 'footer' : 'main/page')
            }))"""
    )


async def check_one(request, url, semaphore):
    async with semaphore:
        try:
            response = await request.get(
                url,
                timeout=REQUEST_TIMEOUT_MS,
                max_redirects=10,
            )

            return {
                "url": url,
                "status": response.status,
                "final_url": response.url,
                "broken": response.status >= 400,
                "error": None,
            }

        except Exception as exc:
            return {
                "url": url,
                "status": None,
                "final_url": None,
                "broken": True,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            }


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()

        try:
            raw_links = await discover_links(page)
            homepage_final_url = page.url
        finally:
            await browser.close()

        discovered = {}

        for item in raw_links:
            url = normalize_url(item.get("href"), homepage_final_url)

            if not url:
                continue

            source = {
                "text": item.get("text", ""),
                "area": item.get("area", "main/page"),
                "href": item.get("href", ""),
            }

            discovered.setdefault(url, {"url": url, "sources": []})

            if source not in discovered[url]["sources"]:
                discovered[url]["sources"].append(source)

        request = await playwright.request.new_context(
            user_agent="YettelHomepageLinkMonitor/1.0 (+homepage link health check)"
        )

        try:
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

            checks = await asyncio.gather(
                *(
                    check_one(request, url, semaphore)
                    for url in discovered
                )
            )
        finally:
            await request.dispose()

        checked_links = []
        broken_links = []

        for result in checks:
            entry = {
                **result,
                "sources": discovered[result["url"]]["sources"],
            }

            checked_links.append(entry)

            if entry["broken"]:
                broken_links.append(entry)

        output = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source_url": SOURCE_URL,
            "homepage_final_url": homepage_final_url,
            "discovered_link_count": len(discovered),
            "checked_link_count": len(checked_links),
            "broken_link_count": len(broken_links),
            "broken_links": broken_links,
            "all_links": checked_links,
        }

        with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)

        print(f"Homepage: {SOURCE_URL}")
        print(f"Unique links discovered: {len(discovered)}")
        print(f"Broken links: {len(broken_links)}")
        print(f"Full report: {OUTPUT_FILE}")

        for item in broken_links:
            print(
                f"[BROKEN] status={item['status']} "
                f"url={item['url']} "
                f"error={item['error'] or '-'}"
            )


if __name__ == "__main__":
    asyncio.run(main())
