import re
import logging
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Browser
from .base import BaseScraper, JobItem

logger = logging.getLogger(__name__)

LOCATION_MAP = {
    "hcm": "ho-chi-minh",
    "hn": "ha-noi",
    "dn": "da-nang",
    "hải phòng": "hai-phong",
    "cần thơ": "can-tho",
}


class TopCVScraper(BaseScraper):
    BASE_URL = "https://www.topcv.vn/tim-viec-lam"

    async def search(self, keyword: str, location: str, limit: int = 20) -> list[JobItem]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            try:
                return await self._scrape(browser, keyword, location, limit)
            except Exception as e:
                logger.exception("TopCV scrape error: %s", e)
                return []
            finally:
                await browser.close()

    async def _scrape(self, browser: Browser, keyword: str, location: str, limit: int) -> list[JobItem]:
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )

        loc_slug = LOCATION_MAP.get(location.lower(), location.lower())
        encoded_keyword = quote_plus(keyword.strip())
        url = f"{self.BASE_URL}?keyword={encoded_keyword}&city={loc_slug}"

        logger.info("[TopCV] keyword=%r", keyword)
        logger.info("[TopCV] url=%s", url)

        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        cards = await page.query_selector_all(".job-item-search-result")
        logger.info("[TopCV] cards found: %s", len(cards))

        jobs: list[JobItem] = []

        for card in cards[:limit]:
            try:
                title_el = await card.query_selector(".title")
                company_el = await card.query_selector(".company")
                salary_el = await card.query_selector(".salary")
                location_el = await card.query_selector(".location")
                link_el = await card.query_selector("a")

                title = (await title_el.inner_text()).strip() if title_el else ""
                company = (await company_el.inner_text()).strip() if company_el else ""
                salary = (await salary_el.inner_text()).strip() if salary_el else ""
                loc = (await location_el.inner_text()).strip() if location_el else location
                href = await link_el.get_attribute("href") if link_el else ""

                if not title or not href:
                    continue

                job_url = href if href.startswith("http") else f"https://www.topcv.vn{href}"
                description = await self._fetch_description(browser, job_url)
                sal_min, sal_max = self._parse_salary(salary)

                jobs.append(
                    JobItem(
                        title=title,
                        company=company,
                        location=loc,
                        description=description,
                        url=job_url,
                        source="topcv",
                        salary_min=sal_min,
                        salary_max=sal_max,
                    )
                )
            except Exception as e:
                logger.warning("TopCV parse card error: %s", e)
                continue

        await page.close()
        return jobs

    async def _fetch_description(self, browser: Browser, url: str) -> str:
        page = None
        try:
            page = await browser.new_page()
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            el = await page.query_selector(".job-description__text")
            text = (await el.inner_text()).strip() if el else ""
            return text[:3000]
        except Exception:
            return ""
        finally:
            if page:
                await page.close()

    def _parse_salary(self, text: str) -> tuple[int | None, int | None]:
        nums = re.findall(r"\d+", text.replace(",", "").replace(".", ""))
        if len(nums) >= 2:
            return int(nums[0]) * 1_000_000, int(nums[1]) * 1_000_000
        return None, None