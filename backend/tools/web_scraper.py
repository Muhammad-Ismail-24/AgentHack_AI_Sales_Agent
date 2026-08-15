"""Playwright-based website scraper, cached in Redis so a URL is never fetched twice a day."""

from backend.utils.cache import get_cache, set_cache
from backend.utils.logger import logger

CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h


def _cache_key(url: str) -> str:
    return f"scrape:{url}"


async def scrape(url: str) -> str:
    """Scrape the visible text content of a page with headless Chromium.

    Cached in Redis for 24h so the same URL is never scraped twice. Returns
    "" on any failure (bad URL, timeout, blocked, no Redis) and logs the error.
    """
    if not url:
        return ""

    cached = get_cache(_cache_key(url))
    if cached is not None:
        logger.info(f"Cache hit for scrape: {url}")
        return cached

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # Strip script/style tags before extracting visible text.
                await page.evaluate(
                    """() => {
                        document.querySelectorAll('script, style').forEach(el => el.remove());
                    }"""
                )
                text = await page.inner_text("body")
            finally:
                await browser.close()

        cleaned = " ".join(text.split())
        set_cache(_cache_key(url), cleaned, ttl=CACHE_TTL_SECONDS)
        return cleaned
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return ""
