"""Load the versioned, offline source catalog relative to this package."""
import json
from pathlib import Path
from .model import CoverRecipe, CropCalendar, WindowRule


def load_catalog():
    data = json.loads((Path(__file__).parent / "data" / "boone.json").read_text())
    calendars = {}
    for item in data["crops"]:
        rules = None if item["rules"] is None else tuple(WindowRule(
            **dict(rule, sources=tuple(rule["sources"]))) for rule in item["rules"])
        calendars[item["id"]] = CropCalendar(item["id"], item["name"], rules,
            item.get("unavailable_reason", ""), item.get("unavailable_rules", {}))
    return data, calendars


def load_cover_recipes(data):
    """Read the catalog's published transition recipes."""
    return tuple(CoverRecipe(**item) for item in data["cover_recipes"])
