from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


@dataclass
class SearchResult:
    title: str
    summary: str
    url: str
    domain: str
    rank: int


@dataclass
class SearchOutcome:
    outcome: str  # RESULTS | ZERO_RESULTS | FAILED
    results: list[SearchResult] = field(default_factory=list)
    error_code: str | None = None


class TavilySearch:
    async def search(self, query: str, cap: int = 5) -> SearchOutcome:
        settings = get_settings()
        if not settings.search_api_key:
            return SearchOutcome(outcome="FAILED", error_code="provider_unavailable")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.search_api_key,
                        "query": query,
                        "max_results": max(1, min(cap, 8)),
                        "search_depth": "basic",
                        "include_answer": False,
                    },
                )
            if response.status_code >= 400:
                return SearchOutcome(outcome="FAILED", error_code="provider_unavailable")
            payload = response.json()
            results: list[SearchResult] = []
            for i, item in enumerate(payload.get("results", [])[:cap]):
                url = str(item.get("url", ""))
                results.append(
                    SearchResult(
                        title=str(item.get("title") or "Untitled result")[:300],
                        summary=str(item.get("content") or "")[:1200],
                        url=url,
                        domain=urlparse(url).hostname or "",
                        rank=i,
                    )
                )
            return SearchOutcome(outcome="RESULTS" if results else "ZERO_RESULTS", results=results)
        except Exception:  # noqa: BLE001
            return SearchOutcome(outcome="FAILED", error_code="provider_unavailable")


class StubSearch:
    """Deterministic development-only search. Forbidden in production by Settings."""

    async def search(self, query: str, cap: int = 5) -> SearchOutcome:
        label = query.strip()[:80]
        seed = abs(hash(label)) % 90 + 10
        results = [
            SearchResult(
                title=f"Benchmark briefing: {label}",
                summary=(
                    f"An illustrative external briefing covering {label}. It reports a "
                    f"{seed}% directional signal and summarizes three adoption patterns."
                ),
                url=f"https://example.com/research/{seed}/briefing",
                domain="example.com",
                rank=0,
            ),
            SearchResult(
                title=f"Analyst perspective on {label}",
                summary=(
                    f"A second illustrative source frames {label} as an emerging priority, "
                    "with adoption concentrated in mid-market teams."
                ),
                url=f"https://example.org/analyst/{seed}",
                domain="example.org",
                rank=1,
            ),
            SearchResult(
                title=f"Practical checklist for {label}",
                summary=(
                    f"A practitioner checklist for {label}: define the metric, pick a narrow pilot, "
                    "instrument the result, and publish the learning."
                ),
                url=f"https://example.net/checklists/{seed}",
                domain="example.net",
                rank=2,
            ),
        ]
        return SearchOutcome(outcome="RESULTS", results=results[:cap])


def make_search():
    settings = get_settings()
    if settings.search_provider == "tavily":
        return TavilySearch()
    return StubSearch()


search = make_search()


def validate_search_available() -> None:
    settings = get_settings()
    if settings.search_provider == "tavily" and not settings.search_api_key:
        raise AppError("provider_unavailable", "error.provider.unavailable")
