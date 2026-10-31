"""Thin async client for the Qloo hackathon API."""
import asyncio
import os
import random
import time
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE_URL = os.environ.get("QLOO_BASE_URL", "https://hackathon.api.qloo.com")

# Shared across every run on this instance: the hackathon key rate-limits bursts, so cap
# concurrent Qloo requests and reuse identical responses (private server-side cache is
# allowed by the hackathon terms; nothing is written to the repo).
MAX_IN_FLIGHT = int(os.environ.get("QLOO_MAX_IN_FLIGHT", "4"))
CACHE_TTL_S = 6 * 3600
RETRIES = 6
_gate: asyncio.Semaphore | None = None
_cache: dict[tuple, tuple[float, dict]] = {}


def _semaphore() -> asyncio.Semaphore:
    global _gate
    if _gate is None:
        _gate = asyncio.Semaphore(MAX_IN_FLIGHT)
    return _gate


class QlooError(Exception):
    pass


@dataclass
class QlooCall:
    """One API call, recorded for the audit trail."""
    endpoint: str
    params: dict
    status: int
    ms: int
    why: str = ""
    cached: bool = False
    retries: int = 0


@dataclass
class Qloo:
    api_key: str = field(default_factory=lambda: os.environ["QLOO_API_KEY"])
    timeout: float = 15.0
    calls: list[QlooCall] = field(default_factory=list)

    def __post_init__(self):
        self._http = httpx.AsyncClient(
            base_url=BASE_URL, headers={"X-Api-Key": self.api_key}, timeout=self.timeout
        )

    async def get(self, endpoint: str, params: dict, why: str = "") -> dict:
        t0 = time.perf_counter()
        key = (endpoint, tuple(sorted((k, str(v)) for k, v in params.items())))
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            self.calls.append(QlooCall(endpoint, params, 200, int((time.perf_counter() - t0) * 1000),
                                       why, cached=True))
            return hit[1]

        retries = 0
        for attempt in range(RETRIES):
            async with _semaphore():
                try:
                    resp = await self._http.get(endpoint, params=params)
                except httpx.TimeoutException:
                    resp = None
            if resp is not None and resp.status_code not in (429, 500, 502, 503, 504):
                break
            retries += 1
            if attempt < RETRIES - 1:
                wait = float(resp.headers.get("retry-after", 0) or 0) if resp is not None else 0
                await asyncio.sleep(max(wait, 0.6 * 2**attempt) + random.uniform(0, 0.4))
        status = resp.status_code if resp is not None else 504
        self.calls.append(QlooCall(endpoint, params, status, int((time.perf_counter() - t0) * 1000),
                                   why, retries=retries))
        if status != 200:
            body = resp.text[:200] if resp is not None else "timeout"
            raise QlooError(f"{endpoint} {status}: {body}")
        data = resp.json()
        _cache[key] = (time.time(), data)
        return data

    async def search(self, query: str, types: str = "urn:entity:artist", take: int = 3, why: str = ""):
        data = await self.get("/search", {"query": query, "types": types, "take": take}, why)
        return data.get("results", [])

    async def insights(self, filter_type: str, why: str = "", **params) -> dict:
        # Qloo params are dotted (signal.interests.entities); callers pass them with "__".
        q = {"filter.type": filter_type}
        q.update({k.replace("__", "."): v for k, v in params.items()})
        return (await self.get("/v2/insights", q, why)).get("results", {})

    async def aclose(self):
        await self._http.aclose()
