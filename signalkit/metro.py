"""Turn a Qloo US heatmap into a per-metro demand percentile."""
from dataclasses import dataclass

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

# ~100 largest US metros (principal city center).
METROS: dict[str, tuple[float, float]] = {
    "New York, NY": (40.71, -74.01), "Los Angeles, CA": (34.05, -118.24), "Chicago, IL": (41.88, -87.63),
    "Dallas, TX": (32.78, -96.80), "Houston, TX": (29.76, -95.37), "Washington, DC": (38.91, -77.04),
    "Philadelphia, PA": (39.95, -75.17), "Miami, FL": (25.76, -80.19), "Atlanta, GA": (33.75, -84.39),
    "Boston, MA": (42.36, -71.06), "Phoenix, AZ": (33.45, -112.07), "San Francisco, CA": (37.77, -122.42),
    "Riverside, CA": (33.95, -117.40), "Detroit, MI": (42.33, -83.05), "Seattle, WA": (47.61, -122.33),
    "Minneapolis, MN": (44.98, -93.27), "San Diego, CA": (32.72, -117.16), "Tampa, FL": (27.95, -82.46),
    "Denver, CO": (39.74, -104.99), "Baltimore, MD": (39.29, -76.61), "St. Louis, MO": (38.63, -90.20),
    "Orlando, FL": (28.54, -81.38), "Charlotte, NC": (35.23, -80.84), "San Antonio, TX": (29.42, -98.49),
    "Portland, OR": (45.52, -122.68), "Sacramento, CA": (38.58, -121.49), "Pittsburgh, PA": (40.44, -80.00),
    "Austin, TX": (30.27, -97.74), "Las Vegas, NV": (36.17, -115.14), "Cincinnati, OH": (39.10, -84.51),
    "Kansas City, MO": (39.10, -94.58), "Columbus, OH": (39.96, -83.00), "Indianapolis, IN": (39.77, -86.16),
    "Cleveland, OH": (41.50, -81.69), "San Jose, CA": (37.34, -121.89), "Nashville, TN": (36.16, -86.78),
    "Virginia Beach, VA": (36.85, -75.98), "Providence, RI": (41.82, -71.41), "Jacksonville, FL": (30.33, -81.66),
    "Milwaukee, WI": (43.04, -87.91), "Raleigh, NC": (35.78, -78.64), "Oklahoma City, OK": (35.47, -97.52),
    "Memphis, TN": (35.15, -90.05), "Richmond, VA": (37.54, -77.44), "Louisville, KY": (38.25, -85.76),
    "New Orleans, LA": (29.95, -90.07), "Salt Lake City, UT": (40.76, -111.89), "Hartford, CT": (41.76, -72.69),
    "Buffalo, NY": (42.89, -78.88), "Birmingham, AL": (33.52, -86.80), "Rochester, NY": (43.16, -77.61),
    "Grand Rapids, MI": (42.96, -85.67), "Tucson, AZ": (32.22, -110.97), "Honolulu, HI": (21.31, -157.86),
    "Tulsa, OK": (36.15, -95.99), "Fresno, CA": (36.74, -119.79), "Worcester, MA": (42.26, -71.80),
    "Omaha, NE": (41.26, -95.93), "Bridgeport, CT": (41.19, -73.20), "Greenville, SC": (34.85, -82.40),
    "Albuquerque, NM": (35.08, -106.65), "Bakersfield, CA": (35.37, -119.02), "Albany, NY": (42.65, -73.76),
    "Knoxville, TN": (35.96, -83.92), "El Paso, TX": (31.76, -106.49), "Baton Rouge, LA": (30.45, -91.19),
    "McAllen, TX": (26.20, -98.23), "New Haven, CT": (41.31, -72.92), "Allentown, PA": (40.60, -75.49),
    "Oxnard, CA": (34.20, -119.18), "Columbia, SC": (34.00, -81.03), "North Port, FL": (27.04, -82.24),
    "Dayton, OH": (39.76, -84.19), "Charleston, SC": (32.78, -79.93), "Greensboro, NC": (36.07, -79.79),
    "Stockton, CA": (37.96, -121.29), "Cape Coral, FL": (26.56, -81.95), "Boise, ID": (43.62, -116.20),
    "Colorado Springs, CO": (38.83, -104.82), "Little Rock, AR": (34.75, -92.29), "Lakeland, FL": (28.04, -81.95),
    "Akron, OH": (41.08, -81.52), "Des Moines, IA": (41.59, -93.62), "Springfield, MA": (42.10, -72.59),
    "Ogden, UT": (41.22, -111.97), "Madison, WI": (43.07, -89.40), "Winston-Salem, NC": (36.10, -80.24),
    "Deltona, FL": (28.90, -81.26), "Syracuse, NY": (43.05, -76.15), "Provo, UT": (40.23, -111.66),
    "Toledo, OH": (41.65, -83.54), "Wichita, KS": (37.69, -97.34), "Durham, NC": (35.99, -78.90),
    "Augusta, GA": (33.47, -81.97), "Palm Bay, FL": (28.03, -80.59), "Jackson, MS": (32.30, -90.18),
    "Harrisburg, PA": (40.27, -76.88), "Spokane, WA": (47.66, -117.43), "Chattanooga, TN": (35.05, -85.31),
    "Scranton, PA": (41.41, -75.66), "Lancaster, PA": (40.04, -76.31), "Modesto, CA": (37.64, -121.00),
    "Portland, ME": (43.66, -70.26), "Lexington, KY": (38.04, -84.50), "Asheville, NC": (35.60, -82.55),
}


def geohash(lat: float, lon: float, precision: int = 4) -> str:
    lat_rng, lon_rng = [-90.0, 90.0], [-180.0, 180.0]
    out, bits, even = "", 0, True
    n = 0
    while len(out) < precision:
        rng, v = (lon_rng, lon) if even else (lat_rng, lat)
        mid = (rng[0] + rng[1]) / 2
        bit = 1 if v >= mid else 0
        bits = (bits << 1) | bit
        rng[1 - bit] = mid
        even = not even
        n += 1
        if n == 5:
            out += _BASE32[bits]
            bits, n = 0, 0
    return out


@dataclass
class MetroScore:
    metro: str
    geohash: str
    affinity_rank: float | None
    popularity: float | None
    percentile: float | None   # 0–100 vs the other metros, by affinity_rank
    rank: int | None            # 1 = strongest metro
    hype_gap: float | None      # popularity − affinity_rank; large positive = known, not loved


def score_metros(heatmap: list[dict]) -> dict[str, MetroScore]:
    """Read each metro's cell from a US heatmap and rank metros against each other."""
    cells = {c["location"]["geohash"]: c.get("query", {}) for c in heatmap}
    raw = {}
    for name, (lat, lon) in METROS.items():
        gh = geohash(lat, lon)
        q = cells.get(gh)
        raw[name] = (gh, q.get("affinity_rank") if q else None, q.get("popularity") if q else None)
    present = sorted((v[1] for v in raw.values() if v[1] is not None), reverse=True)
    out = {}
    for name, (gh, aff, pop) in raw.items():
        if aff is None:
            out[name] = MetroScore(name, gh, None, None, None, None, None)
            continue
        rank = present.index(aff) + 1
        pct = 100.0 * (len(present) - rank) / max(len(present) - 1, 1)
        out[name] = MetroScore(name, gh, aff, pop, round(pct, 1), rank,
                               round(pop - aff, 3) if pop is not None else None)
    return out
