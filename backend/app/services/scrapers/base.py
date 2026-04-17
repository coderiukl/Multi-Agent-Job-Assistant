from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class JobItem:
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    salary_min: int | None = None
    salary_max: int | None = None


class BaseScraper(ABC):
    @abstractmethod
    async def search(self, keyword: str, location: str, limit: int = 20) -> list[JobItem]:
        ...