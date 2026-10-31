"""Qloo-grounded, deterministic display assignment workflow."""
import asyncio
import time
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from .metro import METROS, score_metros
from .qloo import Qloo


class Package(BaseModel):
    id: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=2, max_length=60)
    artist: str = Field(min_length=2, max_length=80)
    orientation: str = Field(default="both", pattern=r"^(both|landscape|portrait)$")


class Site(BaseModel):
    id: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=80)
    city: str
    orientation: str = Field(default="landscape", pattern=r"^(landscape|portrait)$")

    @field_validator("city")
    @classmethod
    def supported_city(cls, value: str) -> str:
        if value not in METROS:
            raise ValueError("Choose a supported US metro")
        return value


class AnalyzeRequest(BaseModel):
    packages: list[Package] = Field(min_length=2, max_length=5)
    sites: list[Site] = Field(min_length=1, max_length=12)

    @field_validator("packages")
    @classmethod
    def unique_packages(cls, value: list[Package]) -> list[Package]:
        if len({p.id for p in value}) != len(value):
            raise ValueError("Package IDs must be unique")
        return value

    @field_validator("sites")
    @classmethod
    def unique_sites(cls, value: list[Site]) -> list[Site]:
        if len({s.id for s in value}) != len(value):
            raise ValueError("Site IDs must be unique")
        return value


DEFAULT = AnalyzeRequest(
    packages=[
        Package(id="SK-101", title="Indie Afterglow", artist="Khruangbin"),
        Package(id="SK-102", title="Modern Country", artist="Kacey Musgraves"),
        Package(id="SK-103", title="Latin Pulse", artist="Bad Bunny"),
    ],
    sites=[
        Site(id="CHI-01", name="Chicago flagship", city="Chicago, IL"),
        Site(id="TUL-02", name="Tulsa lobby", city="Tulsa, OK"),
        Site(id="MIA-03", name="Miami storefront", city="Miami, FL"),
    ],
)


def _compatible(package: Package, site: Site) -> bool:
    return package.orientation == "both" or package.orientation == site.orientation


def assign(request: AnalyzeRequest, profiles: list[dict]) -> list[dict]:
    """Rank Qloo city percentiles among compatible packages; never fill missing cells."""
    out = []
    for site in request.sites:
        options = []
        for package, profile in zip(request.packages, profiles):
            metric = profile["scores"].get(site.city, {})
            options.append({"package_id": package.id, "title": package.title,
                            "artist": profile["resolved_name"],
                            "percentile": metric.get("percentile"),
                            "affinity_rank": metric.get("affinity_rank"),
                            "compatible": _compatible(package, site),
                            "eligible": _compatible(package, site) and metric.get("percentile") is not None})
        ranked = sorted((o for o in options if o["eligible"]),
                        key=lambda o: (o["percentile"], o["affinity_rank"] or 0), reverse=True)
        winner = ranked[0] if ranked else None
        runner = ranked[1] if len(ranked) > 1 else None
        gap = round(winner["percentile"] - runner["percentile"], 1) if winner and runner else None
        review = not winner or winner["percentile"] < 50 or (gap is not None and gap < 8)
        out.append({"site": site.model_dump(), "options": options,
                    "winner": winner["package_id"] if winner else None,
                    "confidence": "review" if review else "clear",
                    "reason": ("No compatible package with Qloo coverage; technician review required." if not winner
                               else "Low local fit or close alternatives; technician review required." if review
                               else f"Top eligible Qloo city percentile, {gap} points ahead of the next package." if gap is not None
                               else "Only eligible package with Qloo coverage."),
                    "gap": gap})
    return out


async def analyze(request: AnalyzeRequest) -> dict:
    started = time.perf_counter()
    q = Qloo()
    trace = []
    try:
        # Scout resolves the exact cultural anchor; ambiguous matches are surfaced.
        async def resolve(package: Package):
            results = await q.search(package.artist, types="urn:entity:artist", take=6,
                                     why=f"Resolve approved package {package.id} cultural anchor")
            if not results:
                raise ValueError(f"Qloo could not find artist '{package.artist}'.")
            exact = next((x for x in results if x.get("name", "").casefold() == package.artist.casefold()), None)
            if exact is None:
                raise ValueError(f"No exact Qloo match for '{package.artist}'. Try the full artist name.")
            return exact

        entities = await asyncio.gather(*(resolve(p) for p in request.packages))
        trace.append({"agent": "Anchor Scout", "result": "Resolved every package anchor to an exact Qloo artist entity.",
                      "calls": len(request.packages)})

        async def scan(package: Package, entity: dict):
            result = await q.insights("urn:heatmap", why=f"Measure US metro affinity for {package.id}",
                                      signal__interests__entities=entity["entity_id"],
                                      filter__location__query="United States")
            cells = result.get("heatmap", [])
            if not cells:
                raise ValueError(f"Qloo has no geographic data for '{package.artist}'.")
            scores = score_metros(cells)
            return {"package_id": package.id, "resolved_name": entity["name"],
                    "entity_id": entity["entity_id"], "cells": len(cells),
                    "scores": {name: {"percentile": s.percentile,
                                      "affinity_rank": s.affinity_rank,
                                      "geohash": s.geohash} for name, s in scores.items()}}

        profiles = await asyncio.gather(*(scan(p, e) for p, e in zip(request.packages, entities)))
        trace.append({"agent": "Geo Signal Analyst", "result": "Scored each package against 105 US metros using Qloo heatmap cells.",
                      "calls": len(request.packages)})
        assignments = assign(request, profiles)
        trace.append({"agent": "Deployment Arbiter", "result": "Ranked eligible packages per site; flagged missing data and close calls.",
                      "calls": 0})
        trace.append({"agent": "Technician Gate", "result": "Prepared assignments for technician approval before export.",
                      "calls": 0})
        return {"packages": [p.model_dump() for p in request.packages],
                "sites": [s.model_dump() for s in request.sites],
                "profiles": [{k: v for k, v in p.items() if k != "scores"} for p in profiles],
                "assignments": assignments, "trace": trace,
                "qloo_calls": [{"endpoint": c.endpoint, "purpose": c.why, "status": c.status,
                                "ms": c.ms, "cached": c.cached} for c in q.calls],
                "elapsed_ms": round((time.perf_counter() - started) * 1000)}
    finally:
        await q.aclose()
