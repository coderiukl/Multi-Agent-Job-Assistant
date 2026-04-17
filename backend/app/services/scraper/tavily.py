import logging
import re
from typing import Any

import httpx

from .base import BaseScraper, JobItem

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"

SITE_MAP = {
    "itviec": "site:itviec.com",
    "topcv": "site:topcv.vn",
    "vietnamworks": "site:vietnamworks.com",
    "linkedin": "site:linkedin.com/jobs",
}


class TavilyScraper(BaseScraper):
    def __init__(self, api_key: str, sites: list[str] | None = None):
        self.api_key = api_key
        self.sites = sites or ['itviec', 'topcv']

    async def search(self, keyword: str, location: str, limit: int = 10) ->list[JobItem]:
        jobs: list[JobItem] = []

        for site in self.sites:
            site_filter = SITE_MAP.get(site, f"site:{site}")
            query = f"{keyword} {location} {site_filter}"

            try:
                results = await self._tavily_search(query, max_results = limit)
                for r in results:
                    item = self._to_job_item(r, source=site)
                    if item:
                        jobs.append(item)
            except Exception as e:
                logger.error("[Tavily] site=%s error: %s", site, e)
        return jobs[:limit]
        
    async def _tavily_search(self, query: str, max_results: int = 10):
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "include_answer": False,
            "max_results": max_results
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(TAVILY_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
        
        logger.info("[Tavily] query=%r -> %d results", query, len(data.get("results", [])))
        return data.get("results", [])
    
    def _to_job_item(self, result: dict, source: str) -> JobItem | None:
        title = result.get("title", "").strip()
        url = result.get("url", "").strip()

        description = result.get("content", "").strip()[:3000]

        if not title or not url:
            return None
        
        company = self._extract_company(title, result)
        location = self._extract_location(result)
        salary_min, salary_max = self._extract_salary(description)

        return JobItem(
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source=source,
            salary_min=salary_min,
            salary_max=salary_max,
        )
        
    def _extract_company(self, title: str, result: dict) -> str:
        match = re.search(r"\bat\s+(.+)$", title, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return result.get("metadata", {}).get("company", "")
    
    def _extract_location(self, result: dict) -> str:
        content = result.get("content", "")
        for loc in ["Ho Chi Minh", "Hanoi", "Da Nang", "Hà Nội", "TP.HCM", "Đà Nẵng"]:
            if loc.lower() in content.lower():
                return loc
        return ""
    
    def _extract_salary(self, text: str) -> tuple[int | None, int | None]: 
        usd = re.findall(r"\$\s*(\d+(?:,\d+)?)", text)
        if len(usd) >= 2:
            return int(usd[0].replace(",", "")) * 1000, int(usd[1].replace(",", "")) * 1000
        
        vnd = re.findall(r"(\d+)\s*(?:triệu|tr|million)", text, re.IGNORECASE)
        if len(vnd) >= 2:
            return int(vnd[0]) * 1_000_000, int(vnd[1]) * 1_000_000
        
        return None, None



        