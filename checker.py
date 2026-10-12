import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.parse import urldefrag, urljoin, urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

SOURCE_URL = "https://www.yettel.bg/"
OUTPUT_FILE = "results.json"
REQUEST_TIMEOUT_MS = 20000
MAX_CONCURRENT_REQUESTS = 8
USER_AGENT = "YettelHomepageLinkMonitor/1.0 (+homepage link health check)"


async def discover_links(page):
    await page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(2000)

    return await page.locator("a[href]").evaluate_all(
        """anchors => {
            function clean(value) {
                return (value || '').replace(/\\\\s+/g, ' ').trim();
            }

            function nearestHeading(anchor) {
                const container = anchor.closest('section, article, nav, aside, [role="region"]');
                if (!container) return '';
                const heading = container.querySelector('h1, h2, h3, h4, [role="heading"]');
                return clean(heading?.innerText || heading?.getAttribute('aria-label') || '');
            }

            function cssPath(element) {
                if (!element) return '';
                const parts = [];
                let node = element;
                while (node && node.nodeType === 1 && parts.length < 5) {
                    let part = node.tagName.toLowerCase();
                    if (node.id) {
                        part += '#' + node.id;
                        parts.unshift(part);
                        break;
                    }
                    if (node.classList.length) {
                        part += '.' + [...node.classList].slice(0, 2).join('.');
                    }
                    parts.unshift(part);
                    node = node.parentElement;
                }
                return parts.join(' > ');
            }

            return anchors
                .filter(a => !a.closest('#CybotCookiebotDialog'))
                .map(a => {
                    const href = a.getAttribute('href') || '';
                    const text = clean(
                        a.innerText ||
                        a.getAttribute('aria-label') ||
                        a.getAttribute('title') ||
                        ''
                    );
                    const images = [...a.querySelectorAll('img')].map(img => ({
                        alt: clean(img.getAttribute('alt') || ''),
                        src: img.currentSrc || img.src || img.getAttribute('src') || ''
                    }));
                    const area = a.closest('header') ? 'header'
                        : a.closest('footer') ? 'footer'
                        : 'main/page';
                    const elementType = images.length
                        ? (text ? 'text + image' : 'image')
                        : 'text/link';

                    return {
                        href,
                        text,
                        title: a.getAttribute('title') || '',
                        area,
                        section: nearestHeading(a),
                        element_type: elementType,
                        images,
                        selector: cssPath(a)
                    };
                });
        }"""
    )


def normalize_url(href, base_url):
    if not href:
        return None

    href = href.strip()
    if not href or href.startswith("#"):
        return None
    if href.lower().startswith(("javascript:", "mailto:", "tel:", "data:")):
        return None
    if re.fullmatch(r"[\[\]{}()]+", href):
        return None
    if "(" in href or ")" in href:
        return None

    absolute = urljoin(base_url, href)
    absolute, _ = urldefrag(absolute)
    parsed = urlparse(absolute)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return absolute


async def check_one(request, semaphore, url):
    async with semaphore:
        try:
            response = await request.get(
                url,
                timeout=REQUEST_TIMEOUT_MS,
                max_redirects=10,
            )
            status = response.status
            final_url = response.url
            await response.dispose()

            if status == 404 or status == 410:
                classification = "broken"
            elif status in (401, 403, 429):
                classification = "review"
            elif status >= 500:
                classification = "review"
            elif status >= 400:
                classification = "broken"
            else:
                classification = "ok"

            return {
                "url": url,
                "status": status,
                "final_url": final_url,
                "broken": classification == "broken",
                "classification": classification,
                "error": None,
            }
        except Exception as exc:
            return {
                "url": url,
                "status": None,
                "final_url": None,
                "broken": False,
                "classification": "review",
                "error": str(exc).splitlines()[0][:500],
            }


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        raw_links = await discover_links(page)
        homepage_final_url = page.url
        await browser.close()

        grouped = {}
        for item in raw_links:
            url = normalize_url(item.get("href"), homepage_final_url)
            if not url:
                continue
            source = {
                "text": item.get("text", ""),
                "title": item.get("title", ""),
                "area": item.get("area", "main/page"),
                "section": item.get("section", ""),
                "element_type": item.get("element_type", "text/link"),
                "images": item.get("images", []),
                "selector": item.get("selector", ""),
                "href": item.get("href", ""),
            }
            grouped.setdefault(url, [])
            if source not in grouped[url]:
                grouped[url].append(source)

        request = await playwright.request.new_context(
            user_agent=USER_AGENT,
            timeout=REQUEST_TIMEOUT_MS,
            ignore_https_errors=False,
        )
        try:
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
            checks = await asyncio.gather(
                *(check_one(request, semaphore, url) for url in grouped)
            )
        finally:
            await request.dispose()

    all_links = []
    for result in checks:
        result["sources"] = grouped[result["url"]]
        all_links.append(result)

    broken_links = [item for item in all_links if item["classification"] == "broken"]
    review_links = [item for item in all_links if item["classification"] == "review"]

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_url": SOURCE_URL,
        "homepage_final_url": homepage_final_url,
        "discovered_link_count": len(raw_links),
        "checked_link_count": len(all_links),
        "broken_link_count": len(broken_links),
        "review_link_count": len(review_links),
        "broken_links": broken_links,
        "review_links": review_links,
        "all_links": all_links,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    print(f"Checked {len(all_links)} unique links.")
    print(f"Broken: {len(broken_links)} | Needs review: {len(review_links)}")
    print(f"Report written to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
