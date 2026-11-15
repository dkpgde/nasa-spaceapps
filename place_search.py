"""Offline place and decimal coordinate search for the map."""

import csv
import gzip
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from locations import SITES


GAZETTEER = Path(__file__).with_name("data") / "geonames-cities.tsv.gz"
GEONAMES_SOURCE = "https://www.geonames.org/export/"
NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
COORDINATES = re.compile(
    rf"\s*({NUMBER})\s*°?\s*([NS])?(?:\s*[,;]\s*|\s+)({NUMBER})\s*°?\s*([EW])?\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Place:
    label: str
    latitude: float
    longitude: float
    zoom: float = 12.5


def coordinate_place(text: str) -> Place | None:
    """Recognize signed decimal pairs or pairs with N/S and E/W hemispheres."""
    match = COORDINATES.fullmatch(text)
    if match is None:
        return None
    latitude, north_south, longitude, east_west = match.groups()
    lat, lon = float(latitude), float(longitude)
    if north_south:
        lat = abs(lat) * (-1 if north_south.upper() == "S" else 1)
    if east_west:
        lon = abs(lon) * (-1 if east_west.upper() == "W" else 1)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Enter latitude from −90 to 90 and longitude from −180 to 180.")
    return Place(f"{lat:.5f}, {lon:.5f}", lat, lon, zoom=14)


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", without_marks))


@lru_cache(maxsize=1)
def gazetteer():
    with gzip.open(GAZETTEER, "rt", encoding="utf-8", newline="") as source:
        cities = [
            (
                Place(label, float(lat), float(lon)),
                tuple(dict.fromkeys(normalize(name) for name in (name, ascii_name, *aliases.split("|")) if name)),
                frozenset(normalize(qualifiers).split()),
                int(population),
            )
            for name, ascii_name, label, qualifiers, lat, lon, population, aliases
            in csv.reader(source, delimiter="\t")
        ]
    for name, lat, lon in SITES.values():
        site, region = name.split(", ", 1)
        cities.append((Place(name, lat, lon, zoom=14), (normalize(site),),
                       frozenset(normalize(region + " US USA United States").split()), 0))
    return cities


def search_places(text: str, limit: int = 8) -> list[Place]:
    if point := coordinate_place(text):
        return [point]
    query = normalize(text)
    if len(query) < 2:
        return []

    words = set(query.split())
    results = []
    for place, names, qualifiers, population in gazetteer():
        if query in names:
            rank = 0
        elif any(query.startswith(name + " ") and set(query[len(name):].split()) <= qualifiers for name in names):
            rank = 1
        elif any(name.startswith(query) for name in names):
            rank = 2
        elif any(words <= set(name.split()) | qualifiers and words.intersection(name.split()) for name in names):
            rank = 3
        else:
            continue
        results.append((rank, -population, place.label, place))
    results.sort(key=lambda result: result[:3])
    unique = {}
    for *_, place in results:
        unique.setdefault(place.label, place)
    return list(unique.values())[:limit]
