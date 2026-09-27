"""
Radio genre station map.

Main buttons are parents with show_on_radio in data/genres.db.
A button plays beats.parent_genre. All and UG MIX do not.
Thin parents (Country, and 80s when the pile is small) stay on the genre map
with no chip. Keyword lists still union with Underground titles.

Default station is All (full catalog under the harvest views cap) — genre
chips are optional filters. View tiers + Free / Free for profit chips
narrow rotation without exposing per-track view counts in the player.

Like/dislike: unauth opens invite request; authed persists reactions + events.
  "Not fit for station" is separate — per-genre hide list in localStorage.
  Full accounts / synced favorites still deferred.
"""

from __future__ import annotations

import json
from pathlib import Path

# Catalog was harvested with an underground ~≤50k philosophy.
CATALOG_MAX_VIEWS = 50_000
CATALOG_MIN_VIEWS = 1

# Discrete view bands for the Radio UI (range chips only — no per-track counts).
# Default = full catalog under the harvest cap (~≤50k).
VIEW_TIERS: list[dict] = [
    {
        "id": "all",
        "label": "All",
        "hint": "Full ≤50k rotation",
        "min_views": CATALOG_MIN_VIEWS,
        "max_views": CATALOG_MAX_VIEWS,
    },
    {
        "id": "lt1k",
        "label": "<1k",
        "hint": "Under 1,000 views",
        "min_views": CATALOG_MIN_VIEWS,
        "max_views": 999,
    },
    {
        "id": "1k5k",
        "label": "1k–5k",
        "hint": "1,000–5,000 views",
        "min_views": 1_000,
        "max_views": 5_000,
    },
    {
        "id": "5k10k",
        "label": "5k–10k",
        "hint": "5,001–10,000 views",
        "min_views": 5_001,
        "max_views": 10_000,
    },
    {
        "id": "10k25k",
        "label": "10k–25k",
        "hint": "10,001–25,000 views",
        "min_views": 10_001,
        "max_views": 25_000,
    },
    {
        "id": "25k50k",
        "label": "25k–50k",
        "hint": "25,001–50,000 views",
        "min_views": 25_001,
        "max_views": CATALOG_MAX_VIEWS,
    },
]

DEFAULT_VIEW_TIER_ID = "all"

_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "genre_taxonomy.json"


def _strip_artists(data: dict) -> dict:
    parents = []
    for parent in data.get("parents") or []:
        if not isinstance(parent, dict):
            continue
        item = {k: v for k, v in parent.items() if k != "artists"}
        subs = []
        for sub in parent.get("subgenres") or []:
            if not isinstance(sub, dict):
                continue
            subs.append({k: v for k, v in sub.items() if k != "artists"})
        item["subgenres"] = subs
        parents.append(item)
    return {"parents": parents, "borders": list(data.get("borders") or [])}


def load_taxonomy() -> dict:
    """The map and the station list read genres.db. JSON is only a seed file."""
    try:
        from .genre_db import read_taxonomy

        data = read_taxonomy()
    except Exception:
        data = None
    if data and data.get("parents"):
        return _strip_artists(data)
    try:
        raw = json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"parents": [], "borders": []}
    if not isinstance(raw, dict):
        return {"parents": [], "borders": []}
    return _strip_artists(raw)


_TAXONOMY = load_taxonomy()
_PARENT_OF: dict[str, str] = {}
_SUBGENRES_OF: dict[str, list[str]] = {}
for _parent in _TAXONOMY.get("parents") or []:
    if not isinstance(_parent, dict):
        continue
    _pname = str(_parent.get("name") or "")
    _subs: list[str] = []
    for _sub in _parent.get("subgenres") or []:
        if not isinstance(_sub, dict):
            continue
        _sname = str(_sub.get("name") or "")
        if not _sname:
            continue
        _subs.append(_sname)
        _PARENT_OF[_sname] = _pname
    if _pname:
        _SUBGENRES_OF[_pname] = _subs


def parent_of(genre: str | None) -> str | None:
    if not genre:
        return None
    return _PARENT_OF.get(genre)


def subgenres_of(parent: str | None) -> list[str]:
    if not parent:
        return []
    return list(_SUBGENRES_OF.get(parent) or [])


def taxonomy_public() -> dict:
    return _TAXONOMY


def parent_has_button(name: str | None) -> bool:
    if not name:
        return False
    for parent in _TAXONOMY.get("parents") or []:
        if not isinstance(parent, dict):
            continue
        if str(parent.get("name") or "") == name:
            return bool(parent.get("button", True))
    return False


# Main buttons are parents with show_on_radio. `parent` is the
# beats.parent_genre value. `keywords` still soft-match Underground.
# `deep_mix` = no genre filter (full catalog). All and UG MIX do not use
# the parent_genre predicate.
_STATIONS: list[dict] = [
    {
        "id": "all",
        "label": "All",
        "db_genres": [],
        "keywords": [],
        "deep_mix": True,
    },
    {
        "id": "trap",
        "label": "Trap",
        "parent": "Trap",
        "db_genres": ["Trap", "Melodic Trap", "Dark/Aggressive", "Trapsoul", "Hoodtrap", "Supertrap", "Detroit"],
        "keywords": [
            "trap type beat",
            "type beat trap",
            "melodic trap",
            "dark trap",
            "trapsoul",
            "trap soul",
            "hoodtrap",
            "supertrap",
            "detroit",
            "kodak black",
            "dababy",
            "da baby",
            "key glock",
            "g herbo",
            "21 savage",
            "nardo wick",
            "moneybagg yo",
            "travis scott",
            "metro boomin",
            "babytron",
            "veeze",
            "evilgiane",
            "thraxx",
        ],
    },
    {
        "id": "rage",
        "label": "Rage",
        "parent": "Rage",
        "db_genres": ["Rage/Opium"],
        "keywords": ["rage", "opium", "ken carson", "yeat", "carti", "f1lthy"],
    },
    {
        "id": "drill",
        "label": "Drill",
        "parent": "Drill",
        "db_genres": ["Drill"],
        "keywords": [
            "drill",
            "ny drill",
            "uk drill",
            "drill uk",
            "pop smoke",
            "central cee",
            "headie one",
            "digga d",
        ],
    },
    {
        "id": "y2010s",
        "label": "2010s",
        "parent": "2010s",
        "db_genres": ["Plugg/Pluggnb", "Emo Rap", "Phonk"],
        "keywords": [
            "plugg",
            "pluggnb",
            "emo rap",
            "drift phonk",
            "phonk",
            "lil peep",
            "xxxtentacion",
            "lil tracy",
        ],
    },
    {
        "id": "boombap",
        "label": "Boom Bap",
        "parent": "Boom Bap",
        "db_genres": ["Boom Bap/Old School", "East Coast", "Conscious"],
        "keywords": [
            "boom bap",
            "old school",
            "east coast",
            "eastcoast",
            "conscious",
            "dj premier",
            "pete rock",
        ],
    },
    {
        "id": "west",
        "label": "West Coast",
        "parent": "West Coast",
        "db_genres": ["West Coast", "G-Funk"],
        "keywords": ["west coast", "westcoast", "g-funk", "g funk", "gfunk"],
    },
    {
        "id": "southern",
        "label": "Southern",
        "parent": "Southern",
        "db_genres": ["Southern", "Crunk"],
        "keywords": ["southern", "dirty south", "crunk"],
    },
    {
        "id": "rap",
        "label": "Rap",
        "parent": "Rap",
        "db_genres": ["Hip-Hop", "Midwest", "Pop Rap"],
        "keywords": ["hip-hop", "hip hop", "midwest rap", "pop rap"],
    },
    {
        "id": "rnb",
        "label": "R&B",
        "parent": "R&B",
        "db_genres": ["R&B", "Classic Soul", "Psychedelic Soul", "Funk"],
        "keywords": ["r&b", "rnb", "rn&b", "classic soul", "psychedelic soul"],
    },
    {
        "id": "uk",
        "label": "UK",
        "parent": "UK",
        "db_genres": ["UK Rap", "Grime", "UK Garage", "Road Rap", "Afroswing"],
        "keywords": [
            "uk rap",
            "grime",
            "uk garage",
            "road rap",
            "afroswing",
            "afro swing",
            "skepta",
            "stormzy",
            "wiley",
            "dizzee",
            "giggs",
            "santan dave",
            "potter payper",
            "marnz malone",
            "d block europe",
            "bugzy malone",
            "unknown t",
            "clavish",
            "nemzzz",
            "knucks",
            "loyle carner",
            "2step",
            "speed garage",
            "j hus",
            "not3s",
            "kojo funds",
        ],
    },
    {
        "id": "afro",
        "label": "Afro",
        "parent": "Afro",
        "db_genres": [
            "Afrobeat (Classic)",
            "Afropop",
            "Afrofusion",
            "Amapiano-Afrobeats",
            "Highlife",
        ],
        "keywords": [
            "afrobeat",
            "afrobeats",
            "afropop",
            "afro pop",
            "afrofusion",
            "afro fusion",
            "amapiano",
            "highlife",
            "3 step",
            "jazzworx",
        ],
    },
    {
        "id": "caribbean",
        "label": "Caribbean",
        "parent": "Caribbean",
        "db_genres": ["Dancehall", "Dembow", "Reggaeton"],
        "keywords": [
            "dancehall",
            "dembow",
            "reggaeton",
            "skillibeng",
            "vybz kartel",
            "popcaan",
            "shenseea",
            "el alfa",
        ],
    },
    {
        "id": "latin",
        "label": "Latin",
        "parent": "Latin",
        "db_genres": [
            "Cumbia",
            "Brazilian Funk",
            "Brazilian Phonk",
            "Corridos Tumbados",
            "Latin Trap",
            "RKT",
        ],
        "keywords": [
            "cumbia",
            "brazilian funk",
            "baile funk",
            "funk carioca",
            "brazilian phonk",
            "funk phonk",
            "corridos tumbados",
            "corridos",
            "latin trap",
            "rkt",
        ],
    },
    {
        "id": "club",
        "label": "Club",
        "parent": "Club",
        "db_genres": ["Club", "Jersey Club", "Dance Pop"],
        "keywords": [
            "deep house",
            "club banger",
            "edm",
            "jersey club",
            "jersey",
            "dance pop",
        ],
    },
    {
        "id": "alt",
        "label": "Alt",
        "parent": "Alt",
        "db_genres": [
            "Alternative Rock",
            "Indie Rock",
            "Grunge",
            "Shoegaze",
            "Midwest Emo",
            "Nirvana",
        ],
        "keywords": [
            "shoegaze",
            "shoegazing",
            "grunge",
            "nirvana",
            "midwest emo",
            "indie rock",
            "alternative rock",
            "alt rock",
            "alt-rock",
        ],
    },
    {
        "id": "lofi",
        "label": "Lo-fi",
        "parent": "Lo-fi",
        "db_genres": ["Lo-fi/Chill", "Jazz"],
        "keywords": ["lo-fi", "lofi", "lo fi", "chill", "chillhop", "jazz", "jazzy"],
    },
    {
        "id": "90s",
        "label": "90s",
        "parent": "90s",
        "db_genres": ["90s"],
        "keywords": ["90s", "90's"],
    },
    {
        "id": "2000s",
        "label": "2000s",
        "parent": "2000s",
        "db_genres": ["2000s"],
        "keywords": ["2000s", "2000's", "neptunes", "pharrell", "timbaland"],
    },
    {
        "id": "80s",
        "label": "80s",
        "parent": "80s",
        "db_genres": ["80s"],
        "keywords": ["80s", "80's"],
    },
    {
        "id": "country",
        "label": "Country",
        "parent": "Country",
        "db_genres": ["Country"],
        "keywords": ["country type beat", "country folk", "country rap", "zach bryan", "dylan gossett"],
    },
    {
        "id": "meme",
        "label": "Meme",
        "parent": "Meme",
        "db_genres": ["Meme"],
        "keywords": [
            "skibidi",
            "trollge",
            "500 cigarettes",
            "among us",
            "goofy ahh",
            "subway surfer",
            "meme type beat",
            "deez nuts",
            "smurf cat",
        ],
    },
    {
        "id": "underground",
        "label": "UG MIX",
        "parent": "Underground",
        "db_genres": ["Underground"],
        "keywords": [],
    },
]

RADIO_GENRES: list[dict] = [
    station
    for station in _STATIONS
    if station.get("deep_mix") or parent_has_button(station.get("parent"))
]


# Default = full catalog under views cap (not a forced genre).
DEFAULT_GENRE_ID = "all"
# Broadest sensible default = full harvest-cap rotation.
DEFAULT_MAX_VIEWS = CATALOG_MAX_VIEWS
DEFAULT_MIN_VIEWS = CATALOG_MIN_VIEWS

# Tagged radio genres (legacy HQ cross-genre pool — still used if callers ask).
HQ_MIX_DB_GENRES: list[str] = [
    "Rage/Opium",
    "Drill",
    "Dark/Aggressive",
    "Boom Bap/Old School",
    "Plugg/Pluggnb",
    "Ambient/Cloud",
    "Experimental/Glitch",
]

# First-paint / refill batch size. Stations page through the filtered
# catalog in batches so a session can exhaust matching tracks.
QUEUE_BATCH = 80
# Legacy alias for anything still importing QUEUE_SIZE
QUEUE_SIZE = QUEUE_BATCH


def get_genre(genre_id: str) -> dict | None:
    for g in RADIO_GENRES:
        if g["id"] == genre_id:
            return g
    return None


def get_view_tier(tier_id: str | None) -> dict:
    tid = (tier_id or DEFAULT_VIEW_TIER_ID).strip().lower()
    for t in VIEW_TIERS:
        if t["id"] == tid:
            return t
    return VIEW_TIERS[0]


def genre_list_public() -> list[dict]:
    return [{"id": g["id"], "label": g["label"]} for g in RADIO_GENRES]


def view_tiers_public() -> list[dict]:
    return [
        {
            "id": t["id"],
            "label": t["label"],
            "hint": t.get("hint") or "",
            "min_views": t["min_views"],
            "max_views": t["max_views"],
        }
        for t in VIEW_TIERS
    ]
