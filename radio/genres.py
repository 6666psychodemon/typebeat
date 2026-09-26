"""
Radio genre station map.

Maps UI labels → filters against beats.genre (from tagger.py) plus
title / artist_style keyword fallbacks for stations that aren't fully
covered by the existing tagger buckets.

Default station is All (full catalog under the harvest views cap) — genre
chips are optional filters. View tiers + Free / Free for profit chips
narrow rotation without exposing per-track view counts in the player.

Like/dislike: unauth opens invite request; authed persists reactions + events.
  "Not fit for station" is separate — per-genre hide list in localStorage.
  Full accounts / synced favorites still deferred.
"""

from __future__ import annotations

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

# ~10 genre stations + default All. Labels are listener-facing.
# `db_genres` hits tagged rows; `keywords` soft-match Underground title+artist_style.
# When a station has both, the queue unions them (keyword hits stay in rotation).
# `deep_mix` = no genre filter (full catalog).
RADIO_GENRES: list[dict] = [
    {
        "id": "all",
        "label": "All",
        "db_genres": [],
        "keywords": [],
        "deep_mix": True,
    },
    {
        "id": "rage",
        "label": "Rage Trap",
        "db_genres": ["Rage/Opium"],
        "keywords": ["rage", "opium", "ken carson", "yeat", "carti", "f1lthy"],
    },
    {
        "id": "pluggnb",
        "label": "Pluggnb",
        "db_genres": ["Plugg/Pluggnb"],
        "keywords": ["plugg", "pluggnb", "mexikodro", "cashcache", "stoopidxool"],
    },
    {
        "id": "ambient",
        "label": "Ambient",
        "db_genres": ["Ambient/Cloud"],
        "keywords": ["ambient", "cloud rap", "ethereal", "spacey", "clams casino"],
    },
    {
        "id": "experimental",
        "label": "Experimental",
        "db_genres": ["Experimental/Glitch"],
        "keywords": ["sigilkore", "glitchcore", "hexd", "drain", "bladee", "scenecore"],
    },
    {
        "id": "boombap",
        "label": "Boom Bap",
        "db_genres": ["Boom Bap/Old School"],
        "keywords": ["boom bap", "lofi", "90s", "east coast", "old school"],
    },
    {
        "id": "drill",
        "label": "Drill",
        "db_genres": ["Drill"],
        "keywords": ["drill", "ny drill", "uk drill", "pop smoke", "central cee"],
    },
    {
        "id": "dark",
        "label": "Dark Trap",
        "db_genres": ["Dark/Aggressive"],
        "keywords": ["dark", "evilgiane", "thraxx", "city morgue", "zillakami"],
    },
    {
        "id": "melodic",
        "label": "Melodic Trap",
        "db_genres": ["Melodic Trap"],
        "keywords": [
            "melodic",
            "guitar",
            "sad",
            "emo",
            "heartbreak",
            "piano",
            "emotional",
        ],
    },
    {
        "id": "jersey",
        "label": "Jersey Club",
        "db_genres": ["Jersey Club"],
        "keywords": ["jersey", "jersey club", "krush", "jerk", "baile funk"],
    },
    {
        "id": "rnb",
        "label": "R&B",
        "db_genres": ["R&B"],
        "keywords": ["r&b", "rnb", "rn&b", "trapsoul", "trap soul"],
    },
    {
        "id": "detroit",
        "label": "Detroit",
        "db_genres": ["Detroit"],
        "keywords": ["detroit", "babytron", "veeze", "baby smoove", "kasher quon"],
    },
    {
        "id": "chill",
        "label": "Chill",
        "db_genres": ["Chill"],
        "keywords": ["chill", "chillhop"],
    },
    {
        "id": "jazz",
        "label": "Jazz",
        "db_genres": ["Jazz"],
        "keywords": ["jazz", "jazzy"],
    },
    {
        "id": "hiphop",
        "label": "Hip-Hop",
        "db_genres": ["Hip-Hop"],
        "keywords": ["hip-hop", "hip hop", "pop hip hop", "pop/hip-hop"],
    },
    {
        "id": "east_coast",
        "label": "East Coast",
        "db_genres": ["East Coast"],
        "keywords": ["east coast", "eastcoast"],
    },
    {
        "id": "southern",
        "label": "Southern",
        "db_genres": ["Southern"],
        "keywords": ["southern", "dirty south"],
    },
    {
        "id": "west_coast",
        "label": "West Coast",
        "db_genres": ["West Coast"],
        "keywords": ["west coast", "westcoast"],
    },
    {
        "id": "midwest",
        "label": "Midwest",
        "db_genres": ["Midwest"],
        "keywords": ["midwest", "midwest rap"],
    },
    {
        "id": "conscious",
        "label": "Conscious",
        "db_genres": ["Conscious"],
        "keywords": ["conscious"],
    },
    {
        "id": "crunk",
        "label": "Crunk",
        "db_genres": ["Crunk"],
        "keywords": ["crunk"],
    },
    {
        "id": "gfunk",
        "label": "G-Funk",
        "db_genres": ["G-Funk"],
        "keywords": ["g-funk", "g funk", "gfunk"],
    },
    {
        "id": "pop_rap",
        "label": "Pop Rap",
        "db_genres": ["Pop Rap"],
        "keywords": ["pop rap"],
    },
    {
        "id": "afropop",
        "label": "Afropop",
        "db_genres": ["Afropop"],
        "keywords": ["afropop", "afro pop"],
    },
    {
        "id": "afrofusion",
        "label": "Afrofusion",
        "db_genres": ["Afrofusion"],
        "keywords": ["afrofusion", "afro fusion"],
    },
    {
        "id": "afrobeat",
        "label": "Afrobeat",
        "db_genres": ["Afrobeat (Classic)"],
        "keywords": ["afrobeat", "afrobeats"],
    },
    {
        "id": "highlife",
        "label": "Highlife",
        "db_genres": ["Highlife"],
        "keywords": ["highlife"],
    },
    {
        "id": "amapiano",
        "label": "Amapiano",
        "db_genres": ["Amapiano-Afrobeats"],
        "keywords": ["amapiano"],
    },
    {
        "id": "funk",
        "label": "Funk",
        "db_genres": ["Funk"],
        "keywords": ["funk"],
    },
    {
        "id": "classic_soul",
        "label": "Classic Soul",
        "db_genres": ["Classic Soul"],
        "keywords": ["classic soul"],
    },
    {
        "id": "psychedelic_soul",
        "label": "Psychedelic Soul",
        "db_genres": ["Psychedelic Soul"],
        "keywords": ["psychedelic soul"],
    },
    {
        "id": "ragga",
        "label": "Ragga",
        "db_genres": ["Ragga"],
        "keywords": ["ragga", "dancehall"],
    },
    {
        "id": "roots_reggae",
        "label": "Roots Reggae",
        "db_genres": ["Roots Reggae"],
        "keywords": ["roots reggae", "reggae"],
    },
    {
        "id": "dance_pop",
        "label": "Dance Pop",
        "db_genres": ["Dance Pop"],
        "keywords": ["dance pop"],
    },
    {
        "id": "trap",
        "label": "Trap",
        "db_genres": ["Trap"],
        # Artist names only. The bare word "trap" is on almost every type beat.
        "keywords": [
            "kodak black",
            "dababy",
            "da baby",
            "key glock",
            "g herbo",
            "21 savage",
            "nardo wick",
            "moneybagg yo",
        ],
    },
    {
        "id": "underground",
        "label": "UG MIX",
        "db_genres": ["Underground"],
        "keywords": [],
    },
    {
        "id": "uk_drill",
        "label": "UK Drill",
        "db_genres": ["Drill"],
        "keywords": ["uk drill", "drill uk", "headie one", "digga d", "central cee"],
    },
    {
        "id": "grime",
        "label": "Grime",
        "db_genres": ["Grime"],
        "keywords": ["grime", "skepta", "stormzy", "wiley", "dizzee", "giggs"],
    },
    {
        "id": "uk_garage",
        "label": "UK Garage",
        "db_genres": ["UK Garage"],
        "keywords": ["uk garage", "2step", "speed garage", "mj cole", "so solid"],
    },
    {
        "id": "afroswing",
        "label": "Afroswing",
        "db_genres": ["Afroswing"],
        "keywords": ["afroswing", "afro swing", "afro trap", "j hus", "kojo funds"],
    },
    {
        "id": "road_rap",
        "label": "Road Rap",
        "db_genres": ["Road Rap"],
        "keywords": ["road rap", "uk rap", "trap rap uk", "nines", "mo stack"],
    },
    {
        "id": "uk_rap",
        "label": "UK Rap",
        "db_genres": ["UK Rap"],
        # "uk rap" stays on Road Rap too. No bare "dave" — that substring is everywhere.
        "keywords": [
            "uk rap",
            "santan dave",
            "potter payper",
            "marnz malone",
            "d block europe",
            "bugzy malone",
            "unknown t",
            "clavish",
            "nemzzz",
            "knucks",
        ],
    },
    {
        "id": "dancehall",
        "label": "Dancehall",
        "db_genres": ["Dancehall"],
        # "dancehall" stays on Ragga as well so that station's keyword union still hits.
        "keywords": ["dancehall", "skillibeng", "vybz kartel", "popcaan", "shenseea"],
    },
    {
        "id": "brazilian_funk",
        "label": "Brazilian Funk",
        "db_genres": ["Brazilian Funk"],
        # "baile funk" stays on Jersey Club. Not bare "funk", and not MC Stan.
        "keywords": ["brazilian funk", "baile funk", "funk carioca"],
    },
    {
        "id": "brazilian_phonk",
        "label": "Brazilian Phonk",
        "db_genres": ["Brazilian Phonk"],
        # Bare "phonk" is intentionally absent so US phonk does not land here.
        "keywords": ["brazilian phonk", "funk phonk"],
    },
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
