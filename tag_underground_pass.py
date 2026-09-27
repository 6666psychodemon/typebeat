#!/usr/bin/env python3
"""Retag beats that are still genre='Underground'.

Does not touch any other genre. Does not score rows with Jev. Does not write
jev_error. One process, short transactions, Underground only.

A title is decided in this order:

1. Quoted text is the beat's own name and is removed first. [FREE], (FREE),
   [SOLD], and prod-by tails are structure, not style.
2. Explicit style phrases outside quotes. A more specific phrase beats a
   generic one: "melodic trap" and "dark trap" beat "trap type beat";
   "uk drill" / "drill" beat trap; "afroswing" beats dancehall and R&B;
   "dancehall" beats R&B; "trapsoul" is R&B. "trap type beat" and "trap beat"
   are Trap. Bare "trap", "hoodtrap", and "trap instrumental" are not.
3. Known artists. Unknown collaborators are ignored. Majority of known genres
   wins. A tie stays Underground.
4. An explicit phrase wins when it is at least as specific as the artist
   default ("Drake x Rihanna | Dancehall Type Beat" → Dancehall,
   "Drake | Trap Type Beat" → Trap). A more specific artist keeps their
   genre against a generic trap suffix ("Giggs Type Beat | Trap Instrumental"
   and "Gunna | Trap Type Beat" stay Grime and Melodic Trap).

Giggs defaults to Grime, not UK Rap: he is a grime artist, and UK Rap would
flatten him into the broader bucket. UK Rap is for Dave (UK, exact token
only), Nines, Potter Payper, Marnz Malone, Clavish, D Block Europe,
Bugzy Malone, Knucks, Nemzzz, and Unknown T. Central Cee and Headie One
stay Drill.

Lo-fi and chill are one genre, Lo-fi/Chill (lo-fi, lofi, chill, chillhop;
"chill" does not match inside a longer word). Loyle Carner is UK Rap.
Little Simz stays Conscious. Shoegaze, Grunge, Nirvana, and Alternative
Rock are separate strings. When one title names more than one of those
four, Shoegaze beats Grunge, then Nirvana, then Alternative Rock.

Artist genres, in order: hand overrides, data/djcrates_artist_genres.json,
an optional short Wikidata pass, then TypeSafe Choice on at most 2000
unmatched names. LLM judgments are cached in data/artist_genre_library.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "typebeats.db"
DJCRATES_PATH = ROOT / "data" / "djcrates_artist_genres.json"
LIB_PATH = ROOT / "data" / "artist_genre_library.json"

BATCH = 2000
READ_BATCH = 8000
MIN_FREE = 3 * 1024**3
LLM_CAP = 2000
LLM_MIN_CONF = 0.40
WIKI_CAP = 60
WIKI_TIMEOUT = 20

# Higher wins. A phrase replaces an artist only when its score is >= the
# artist's score, so generic Trap does not override Grime, Drill, or
# Melodic Trap, and Dancehall does override Hip-Hop / R&B.
SPEC = {
    "Brazilian Phonk": 99,
    "Brazilian Funk": 97,
    "Afroswing": 93,
    "Dancehall": 90,
    "Drill": 86,
    "Melodic Trap": 82,
    "Dark/Aggressive": 80,
    "Grime": 78,
    "Rage/Opium": 76,
    "Plugg/Pluggnb": 76,
    "UK Rap": 74,
    "Afrobeat (Classic)": 74,
    "Amapiano-Afrobeats": 73,
    "UK Garage": 73,
    "Jazz": 72,
    "Jersey Club": 71,
    "West Coast": 70,
    "East Coast": 70,
    "Southern": 70,
    "Midwest": 70,
    "G-Funk": 70,
    "Highlife": 70,
    "Afropop": 68,
    "Afrofusion": 68,
    "Boom Bap/Old School": 68,
    "Detroit": 66,
    "Crunk": 66,
    "Shoegaze": 69,
    "Grunge": 67,
    "Nirvana": 65,
    "Alternative Rock": 59,
    "Roots Reggae": 64,
    "Ragga": 64,
    "Conscious": 63,
    "Road Rap": 62,
    "Classic Soul": 60,
    "Psychedelic Soul": 60,
    "Experimental/Glitch": 58,
    "Ambient/Cloud": 58,
    "Dance Pop": 57,
    "R&B": 55,
    "Trapsoul": 56,
    "Funk": 50,
    "Hoodtrap": 48,
    "Supertrap": 48,
    "Pop Rap": 44,
    "Trap": 42,
    "Lo-fi/Chill": 40,
    "Hip-Hop": 22,
    "Club": 58,
    "Midwest Emo": 62,
    "Indie Rock": 60,
    "Dembow": 88,
    "Reggaeton": 87,
    "Cumbia": 85,
    "Corridos Tumbados": 86,
    "Latin Trap": 80,
    "RKT": 86,
    "80s": 72,
    "90s": 72,
    "2000s": 72,
    "Country": 66,
    "Meme": 89,
    "Emo Rap": 83,
    "Phonk": 84,
}

HIPHOP_SUB_GENRE = {
    "East Coast": "East Coast",
    "Southern": "Southern",
    "West Coast": "West Coast",
    "Midwest": "Midwest",
    "Conscious": "Conscious",
    "Crunk": "Crunk",
    "G-Funk": "G-Funk",
    "Pop Rap": "Pop Rap",
    "Boom Bap": "Boom Bap/Old School",
    "Old School": "Boom Bap/Old School",
    "Cloud Rap": "Ambient/Cloud",
    "Trap": "Trap",
    "Drill": "Drill",
}

# Hand beats djcrates. Giggs is Grime on purpose (see module docstring).
# MC Stan is Hip-Hop, not Brazilian funk. Freddie Dredd is left unmapped.
HAND: dict[str, str] = {
    # R&B
    "chris brown": "R&B",
    "bryson tiller": "R&B",
    "partynextdoor": "R&B",
    "party next door": "R&B",
    "pnd": "R&B",
    "sza": "R&B",
    "summer walker": "R&B",
    "brent faiyaz": "R&B",
    "6lack": "R&B",
    "the weeknd": "R&B",
    "weeknd": "R&B",
    "tory lanez": "R&B",
    "kehlani": "R&B",
    "giveon": "R&B",
    "jhene aiko": "R&B",
    "jhené aiko": "R&B",
    "ella mai": "R&B",
    "frank ocean": "R&B",
    "daniel caesar": "R&B",
    "dvsn": "R&B",
    "ty dolla sign": "R&B",
    "ty dolla $ign": "R&B",
    "khalid": "R&B",
    "jacquees": "R&B",
    "snoh aalegra": "R&B",
    "lucky daye": "R&B",
    "mahalia": "R&B",
    "jeremih": "R&B",
    "omarian": "R&B",
    "omarion": "R&B",
    "trey songz": "R&B",
    "ne-yo": "R&B",
    "neyo": "R&B",
    "aaliyah": "R&B",
    "miguel": "R&B",
    "usher": "R&B",
    "rihanna": "R&B",
    "h.e.r.": "R&B",
    "her": "R&B",
    "4batz": "R&B",
    "d4vd": "R&B",
    # Hip-Hop. Drake stays generic unless the title names a tighter style.
    "drake": "Hip-Hop",
    "doechii": "Hip-Hop",
    "young m.a": "Hip-Hop",
    "young ma": "Hip-Hop",
    "mc stan": "Hip-Hop",
    "mcstan": "Hip-Hop",
    # Melodic Trap
    "gunna": "Melodic Trap",
    "lil baby": "Melodic Trap",
    "don toliver": "Melodic Trap",
    "toosii": "Melodic Trap",
    "rod wave": "Melodic Trap",
    "future": "Melodic Trap",
    "young thug": "Melodic Trap",
    "lil tjay": "Melodic Trap",
    "polo g": "Melodic Trap",
    "a boogie": "Melodic Trap",
    "a boogie wit da hoodie": "Melodic Trap",
    "nav": "Melodic Trap",
    "juice wrld": "Melodic Trap",
    "juice world": "Melodic Trap",
    "roddy ricch": "Melodic Trap",
    "ynw melly": "Melodic Trap",
    # Rage / plugg
    "sofaygo": "Rage/Opium",
    "so faygo": "Rage/Opium",
    "che": "Rage/Opium",
    "osamason": "Rage/Opium",
    "osama son": "Rage/Opium",
    "kai angel": "Rage/Opium",
    "destroy lonely": "Rage/Opium",
    "ken carson": "Rage/Opium",
    "homixide gang": "Rage/Opium",
    "homixide": "Rage/Opium",
    "yeat": "Rage/Opium",
    "playboi carti": "Rage/Opium",
    "carti": "Rage/Opium",
    "lancey foux": "Rage/Opium",
    "kankan": "Rage/Opium",
    "summrs": "Plugg/Pluggnb",
    "autumn": "Plugg/Pluggnb",
    "autumn!": "Plugg/Pluggnb",
    "xavier sobased": "Plugg/Pluggnb",
    "xaviersobased": "Plugg/Pluggnb",
    "nettspend": "Plugg/Pluggnb",
    "rich amiri": "Plugg/Pluggnb",
    # Drill. Headie One and Central Cee are Drill, not UK Rap.
    "lil durk": "Drill",
    "durkio": "Drill",
    "fivio foreign": "Drill",
    "fivio": "Drill",
    "king von": "Drill",
    "kay flock": "Drill",
    "sheff g": "Drill",
    "sleepy hallow": "Drill",
    "22gz": "Drill",
    "digga d": "Drill",
    "headie one": "Drill",
    "headie": "Drill",
    "pop smoke": "Drill",
    "central cee": "Drill",
    "cenc": "Drill",
    "onefour": "Drill",
    "one four": "Drill",
    "loski": "Drill",
    # Trap
    "kodak black": "Trap",
    "kodak": "Trap",
    "dababy": "Trap",
    "da baby": "Trap",
    "key glock": "Trap",
    "g herbo": "Trap",
    "21 savage": "Trap",
    "21": "Trap",
    "nardo wick": "Trap",
    "moneybagg yo": "Trap",
    "moneybagg": "Trap",
    "young dolph": "Trap",
    "pooh shiesty": "Trap",
    "est gee": "Trap",
    "sauce walka": "Trap",
    "metro boomin": "Trap",
    "9lokknine": "Trap",
    "9lokk nine": "Trap",
    "9 lokknine": "Trap",
    # Detroit
    "babytron": "Detroit",
    "baby tron": "Detroit",
    "veeze": "Detroit",
    "baby smoove": "Detroit",
    "kasher quon": "Detroit",
    "babyface ray": "Detroit",
    "icewear vezzo": "Detroit",
    "sada baby": "Detroit",
    "rio da yung og": "Detroit",
    "rmc mike": "Detroit",
    "peezy": "Detroit",
    "yn jay": "Detroit",
    "skilla baby": "Detroit",
    "42 dugg": "Detroit",
    "42": "Detroit",
    # Coasts and UK
    "shoreline mafia": "West Coast",
    "shoreline": "West Coast",
    "larry june": "West Coast",
    "jay worthy": "West Coast",
    "ohgeesy": "West Coast",
    "fenix flexin": "West Coast",
    "drakeo the ruler": "West Coast",
    "ralfy the plug": "West Coast",
    "03 greedo": "West Coast",
    "dave": "UK Rap",
    "santan dave": "UK Rap",
    "nines": "UK Rap",
    "potter payper": "UK Rap",
    "marnz malone": "UK Rap",
    "clavish": "UK Rap",
    "d block europe": "UK Rap",
    "dblock europe": "UK Rap",
    "bugzy malone": "UK Rap",
    "bugzy": "UK Rap",
    "knucks": "UK Rap",
    "nemzzz": "UK Rap",
    "unknown t": "UK Rap",
    "aj tracey": "UK Rap",
    "aitch": "UK Rap",
    "giggs": "Grime",
    "dizzee rascal": "Grime",
    "dizzee": "Grime",
    "skepta": "Grime",
    "stormzy": "Grime",
    "wiley": "Grime",
    "kano": "Grime",
    "ghetts": "Grime",
    "jme": "Grime",
    "j me": "Grime",
    "chip": "Grime",
    "flowdan": "Grime",
    # Dancehall / afro / jazz / boom bap / conscious
    "j hus": "Afroswing",
    "nsg": "Afroswing",
    "not3s": "Afroswing",
    "kojo funds": "Afroswing",
    "skillibeng": "Dancehall",
    "skilli beng": "Dancehall",
    "vybz kartel": "Dancehall",
    "popcaan": "Dancehall",
    "shenseea": "Dancehall",
    "spice": "Dancehall",
    "alkaline": "Dancehall",
    "masicka": "Dancehall",
    "rema": "Afrobeat (Classic)",
    "omah lay": "Afrobeat (Classic)",
    "omah": "Afrobeat (Classic)",
    "tyla": "Amapiano-Afrobeats",
    "loyle carner": "UK Rap",
    "little simz": "Conscious",
    "simz": "Conscious",
    "nujabes": "Jazz",
    "mick jenkins": "Boom Bap/Old School",
    "joey bada$$": "Boom Bap/Old School",
    "joey badass": "Boom Bap/Old School",
    "mf doom": "Boom Bap/Old School",
    "madlib": "Boom Bap/Old School",
    "j dilla": "Boom Bap/Old School",
    "jdilla": "Boom Bap/Old School",
    # Dark trap / phonk-adjacent, not Brazilian Phonk.
    "suicideboys": "Dark/Aggressive",
    "$uicideboy$": "Dark/Aggressive",
    "pouya": "Dark/Aggressive",
    # High-frequency names the labeler missed or filed too loosely.
    "pierre bourne": "Plugg/Pluggnb",
    "lucki": "Plugg/Pluggnb",
    "lil peep": "Emo Rap",
    "lilpeep": "Emo Rap",
    "xxxtentacion": "Emo Rap",
    "xxx tentacion": "Emo Rap",
    "lil tracy": "Emo Rap",
    "southside": "Trap",
    "808 mafia": "Trap",
    "smokepurpp": "Trap",
    "smoke purpp": "Trap",
    "comethazine": "Trap",
    "ebk jaaybo": "West Coast",
    "iayze": "Rage/Opium",
    "bossman dlow": "Trap",
    "bigxthaplug": "Southern",
    "big xtha plug": "Southern",
    "brakence": "Experimental/Glitch",
    "young chop": "Drill",
    "three 6 mafia": "Crunk",
    "three six mafia": "Crunk",
    "rome streetz": "Boom Bap/Old School",
    "hopsin": "Conscious",
    "the neptunes": "2000s",
    "neptunes": "2000s",
    "pharrell": "2000s",
    "pharrell williams": "2000s",
    "chad hugo": "2000s",
    "timbaland": "2000s",
    "scott storch": "2000s",
    "just blaze": "2000s",
    "mannie fresh": "2000s",
    "polow da don": "2000s",
    "polow": "2000s",
    "danja": "2000s",
    "jazze pha": "2000s",
    "erykah badu": "R&B",
    "erykah": "R&B",
    "badu": "R&B",
    "hamza": "R&B",
    "smino": "Hip-Hop",
    "travis scott": "Trap",
    "travisscott": "Trap",
    "julio foolio": "Trap",
    "foolio": "Trap",
    "fredo bang": "Trap",
    "lil double 0": "Trap",
    "hurricane wisdom": "Trap",
    "el alfa": "Dembow",
    "blessd": "Reggaeton",
    "lomiiel": "Reggaeton",
    "jazzworx": "Amapiano-Afrobeats",
    "dlala thukzin": "Amapiano-Afrobeats",
    "thukzin": "Amapiano-Afrobeats",
    "zach bryan": "Country",
    "dylan gossett": "Country",
    "dj premier": "Boom Bap/Old School",
    "premier": "Boom Bap/Old School",
    "pete rock": "Boom Bap/Old School",
    "rza": "Boom Bap/Old School",
    "mobb deep": "Boom Bap/Old School",
    "dr dre": "G-Funk",
    "dr. dre": "G-Funk",
}

# Single-token aliases that are ordinary words. Multi-word names that contain
# these ("lil baby", "pop smoke", "ice spice") are still indexed.
DENY = frozenset({
    "dream", "today", "next", "guy", "total", "problem", "roger", "ice", "baby",
    "king", "young", "big", "love", "star", "rich", "money", "real", "hard",
    "sad", "dark", "hot", "cold", "night", "day", "best", "new", "old", "raw",
    "lit", "fire", "god", "life", "time", "world", "city", "boy", "girl", "man",
    "kid", "lil", "yung", "the", "and", "for", "with", "from", "trap", "drill",
    "funk", "phonk", "jazz", "rap", "hop", "hip", "rnb", "rb", "pop", "soul",
    "beat", "type", "free", "prod", "dj", "mc", "og", "ak", "abc", "cnn", "ya",
    "yo", "da", "la", "el", "lo", "hi", "my", "me", "we", "up", "of", "to", "in",
    "on", "at", "it", "is", "am", "be", "or", "an", "as", "by", "do", "go", "no",
    "so", "if", "ok", "vs", "ft", "pt", "vol", "bpm", "key", "mix", "edit",
    "loop", "sample", "hook", "bass", "guitar", "piano", "slow", "fast", "soft",
    "deep", "high", "low", "mad", "bad", "emo", "west", "east", "south", "north",
    "coast", "uk", "ny", "atl", "bay", "area", "rage", "chill", "reggae",
    "dancehall", "grime", "afro", "afrobeat", "afrobeats", "soul", "phonk",
    "plug", "plugg", "jerk", "detroit", "experimental", "ambient", "jersey",
    "westcoast", "eastcoast", "reggaeton", "hiphop", "lofi", "crunk",
    "grunge", "nirvana", "shoegaze", "shoegazing",
})

SKIP_NAMES = frozenset({
    "rb", "rnb", "r b", "hip hop", "trap", "drill", "funk", "phonk", "jazz",
    "rap", "pop", "soul", "reggae", "dancehall", "grime", "afrobeat",
    "afrobeats", "west coast", "east coast", "uk rap", "boom bap",
    "grunge", "nirvana", "shoegaze", "shoegazing", "alternative rock",
    "alt rock", "lo fi", "lofi", "chill", "chillhop",
    "jay z", "jayz",
    "lil uzi vert", "lil uzi", "uzi vert",
})

# Genre words and non-rap misfiles. Phrase rules still catch "{style} type beat".
LLM_NAME_BLOCK = frozenset({
    "reggaeton", "jerk", "plug", "plugg", "westcoast", "eastcoast", "hiphop",
    "deftones", "phonk", "trap", "drill", "funk",
    # Ordinary words and genre tokens that would match inside unrelated titles.
    "cloud", "dembow", "jungle", "monk", "war",
    "grunge", "nirvana", "shoegaze", "shoegazing", "chill", "lofi",
    "alternative rock", "alt rock",
    # Reggaeton artists are not Dancehall. Leave them Underground.
    "daddy yankee", "yandel", "farruko", "sech", "nicky jam", "ozuna",
    "el alfa", "chencho corleone", "j balvin", "jhay cortez", "anuel",
    "anuel aa", "tainy", "eladio carrion",
    "cuco", "blackbear", "big yavo",
})

# Longer tokens that must be the whole artist clause ("future bass" is not Future).
EXACT_EXTRA = frozenset({
    "future", "autumn", "gunna", "spice", "nines", "kodak", "fivio", "veeze",
    "mustard", "prince", "hammer", "lloyd", "mario", "usher", "miguel", "peezy",
    "game", "yeat", "nav", "che", "dave", "sza", "rema",
})

STRUCTURE = frozenset({
    "type", "beat", "beats", "typebeat", "free", "prod", "produced",
    "instrumental", "instrumentals", "for", "profit", "sold", "exclusive",
    "untagged", "tagged", "official", "download", "ffp", "lease", "youtube",
    "copyright", "instru", "inst", "remix", "version", "vol", "volume", "non",
    "not", "by", "made", "studio", "fl",
})

NAME_STOP = DENY | STRUCTURE | frozenset({
    "freestyle", "upbeat", "slowed", "reverb", "nightcore", "emotional",
    "smooth", "aggressive", "melodic", "hard", "sad", "dark", "guitar",
    "piano", "boombap", "instrumental", "instru", "bpm", "hook", "loop",
    "sample", "type", "beat", "beats", "free", "prod", "sold", "exclusive",
    "official", "download", "remix", "edit", "radio", "vol", "part", "pt",
    "with", "from", "this", "that", "your", "our", "just", "like", "feat",
    "ft", "vs", "and", "the", "for", "non", "not",
})

# (regex, genre). First matching pattern is not "the" winner — highest SPEC is.
ANYWHERE_SRC: list[tuple[str, str]] = [
    (r"\b(?:brazilian\s+phonk|funk\s+phonk)\b", "Brazilian Phonk"),
    (r"\b(?:drift\s+)?phonk\b", "Phonk"),
    (r"\b(?:brazilian\s+funk|baile\s+funk|funk\s+carioca)\b", "Brazilian Funk"),
    (r"\b(?:uk|ny)\s+drill\b|\bdrill\s+uk\b|\bukdrill\b|\bnydrill\b", "Drill"),
    (r"\bafro\s*swing\b", "Afroswing"),
    (r"\b(?:melodic|emo)\s+trap\b", "Melodic Trap"),
    (r"\bdark\s+trap\b", "Dark/Aggressive"),
    (r"\btrap\s*soul\b|\btrapsoul\b", "Trapsoul"),
    (r"\bhoodtraps?\b", "Hoodtrap"),
    (r"\bsupertraps?\b", "Supertrap"),
    (r"\bdance\s*hall\b", "Dancehall"),
    (r"\bgrime\b", "Grime"),
    (r"\bdrill\b", "Drill"),
    (r"\bafrobeats?\b|\bafro\s+beats?\b", "Afrobeat (Classic)"),
    (r"\brn\s*&\s*b\b|\br\s*&\s*b\b|\br\s+and\s+b\b|\brnb\b", "R&B"),
    # Generic trap phrases. Not bare "trap", not "trap instrumental", not afrotrap.
    # Hoodtrap and supertrap are their own strings above. Trapsoul is Trapsoul.
    (r"\btrap\s+metal\b", "Trap"),
    (r"\btrap\s+type\s*beats?\b", "Trap"),
    (r"\btype\s*beats?\s+trap\b", "Trap"),
    (r"\btrap\s+beats?\b", "Trap"),
    # Four separate genres. Scores put Shoegaze above Grunge, then Nirvana,
    # then Alternative Rock, so a title that names several lands on the first.
    (r"\bshoegaz(?:e|ing)\b", "Shoegaze"),
    (r"\bgrunge\b", "Grunge"),
    (r"\bnirvana\b", "Nirvana"),
    (r"\b(?:alternative|alt)\s+rock\b", "Alternative Rock"),
    # Whole words only: "chill" does not match inside "chilling".
    (r"\blo\s*fi\b", "Lo-fi/Chill"),
    (r"\bchillhop\b|\bchill\b", "Lo-fi/Chill"),
    (r"\bdeep\s+house\b|\bhouse\b", "Club"),
    (r"\bclub\s+bangers?\b|\bedm\b|(?<!strip\s)\bclub\b", "Club"),
    (r"\bmidwest\s+emo\b", "Midwest Emo"),
    (r"\bindie\s+rock\b|\bindie\s+(?:alternative|alt)\b|\b(?:alternative|alt)\s+indie\b", "Indie Rock"),
    (r"\bdembow\b", "Dembow"),
    (r"\breggaeton\b|\bregueton\b", "Reggaeton"),
    (r"\bcumbia\b", "Cumbia"),
    (r"\bcorridos(?:\s+tumbados)?\b", "Corridos Tumbados"),
    (r"\blatin\s+trap\b", "Latin Trap"),
    (r"\brkt\b", "RKT"),
    (r"\bspeed\s+garage\b|\b2\s*[- ]?\s*steps?\b|\buk\s+garage\b", "UK Garage"),
    (r"\bjerk\s+type\s*beats?\b", "Plugg/Pluggnb"),
    (r"\bwest\s+coast\b", "West Coast"),
    (r"\beast\s+coast\b", "East Coast"),
    (r"\bdirty\s+south\b|\bsouthern\b", "Southern"),
    (r"\bboom\s*baps?\b|\bold\s+school\b", "Boom Bap/Old School"),
    (r"\bg[\s-]*funk\b", "G-Funk"),
    (r"\buk\s+rap\b", "UK Rap"),
    (r"\broad\s+rap\b", "Road Rap"),
    (r"\bjersey\s+club\b", "Jersey Club"),
    (r"\bdance\s+pop\b", "Dance Pop"),
    (r"\bpop\s+rap\b", "Pop Rap"),
    (r"\b3\s*steps?\b|\bthree\s+steps?\b", "Amapiano-Afrobeats"),
    (r"\b80'?s\b", "80s"),
    (r"\b90'?s\b", "90s"),
    (r"\b2000'?s\b", "2000s"),
    (r"\bcountry\b", "Country"),
    (r"\b500\s+cigarettes\b", "Meme"),
    (r"\bskibidi\b", "Meme"),
    (r"\btrollge\b", "Meme"),
    (r"\bmeme\s+cockroach\b", "Meme"),
    (r"\bamong\s+us\b|\bamogus\b", "Meme"),
    (r"\bgoofy\s+ahh\b", "Meme"),
    (r"\bsubway\s+surfers?\b", "Meme"),
    (r"\brat\s+dance\b|\bdancing\s+rat\b", "Meme"),
    (r"\bshrek\s+type\s*beats?\b", "Meme"),
    (r"\bsmurf\s+cats?\b", "Meme"),
    (r"\bdeez\s+nuts\b", "Meme"),
    (r"\bmeme\s+rap\b|\bmeme\s+type\s*beats?\b", "Meme"),
    (r"\bemo\s+rap\b", "Emo Rap"),
]

STYLES: list[tuple[str, str]] = [
    ("psychedelic soul", "Psychedelic Soul"),
    ("classic soul", "Classic Soul"),
    ("roots reggae", "Roots Reggae"),
    ("dirty south", "Southern"),
    ("west coast", "West Coast"),
    ("east coast", "East Coast"),
    ("cloud rap", "Ambient/Cloud"),
    ("pop rap", "Pop Rap"),
    ("road rap", "Road Rap"),
    ("uk rap", "UK Rap"),
    ("uk garage", "UK Garage"),
    ("jersey club", "Jersey Club"),
    ("dance pop", "Dance Pop"),
    ("afro swing", "Afroswing"),
    ("afro pop", "Afropop"),
    ("afro fusion", "Afrofusion"),
    ("boom bap", "Boom Bap/Old School"),
    ("old school", "Boom Bap/Old School"),
    ("hip hop", "Hip-Hop"),
    ("g funk", "G-Funk"),
    ("boombap", "Boom Bap/Old School"),
    ("gfunk", "G-Funk"),
    ("southern", "Southern"),
    ("midwest", "Midwest"),
    ("highlife", "Highlife"),
    ("amapiano", "Amapiano-Afrobeats"),
    ("afropop", "Afropop"),
    ("afrofusion", "Afrofusion"),
    ("afroswing", "Afroswing"),
    ("conscious", "Conscious"),
    ("experimental", "Experimental/Glitch"),
    ("ambient", "Ambient/Cloud"),
    ("detroit", "Detroit"),
    ("pluggnb", "Plugg/Pluggnb"),
    ("grime", "Grime"),
    ("crunk", "Crunk"),
    ("ragga", "Ragga"),
    ("reggae", "Roots Reggae"),
    ("jazz", "Jazz"),
    ("jazzy", "Jazz"),
    ("plugg", "Plugg/Pluggnb"),
    ("opium", "Rage/Opium"),
    ("rage", "Rage/Opium"),
    ("melodic", "Melodic Trap"),
    ("jersey", "Jersey Club"),
    ("funk", "Funk"),
    ("soul", "R&B"),
    ("dark", "Dark/Aggressive"),
    ("pop", "Dance Pop"),
]

LLM_MAP = {
    "brazilian_phonk": "Brazilian Phonk",
    "brazilian_funk": "Brazilian Funk",
    "afroswing": "Afroswing",
    "dancehall": "Dancehall",
    "drill": "Drill",
    "melodic_trap": "Melodic Trap",
    "dark": "Dark/Aggressive",
    "grime": "Grime",
    "uk_rap": "UK Rap",
    "afrobeat": "Afrobeat (Classic)",
    "rage": "Rage/Opium",
    "plugg": "Plugg/Pluggnb",
    "amapiano": "Amapiano-Afrobeats",
    "uk_garage": "UK Garage",
    "jazz": "Jazz",
    "jersey": "Jersey Club",
    "west_coast": "West Coast",
    "east_coast": "East Coast",
    "southern": "Southern",
    "midwest": "Midwest",
    "g_funk": "G-Funk",
    "boom_bap": "Boom Bap/Old School",
    "detroit": "Detroit",
    "conscious": "Conscious",
    "rnb": "R&B",
    "dance_pop": "Dance Pop",
    "afropop": "Afropop",
    "afrofusion": "Afrofusion",
    "trap": "Trap",
    "hiphop": "Hip-Hop",
    "funk": "Funk",
    "ambient": "Ambient/Cloud",
    "experimental": "Experimental/Glitch",
    "road_rap": "Road Rap",
    "other": None,
}

WIKI_MAP = {
    "drill": "Drill",
    "drill music": "Drill",
    "uk drill": "Drill",
    "chicago drill": "Drill",
    "brooklyn drill": "Drill",
    "grime": "Grime",
    "grime music": "Grime",
    "dancehall": "Dancehall",
    "dancehall music": "Dancehall",
    "afrobeats": "Afrobeat (Classic)",
    "afrobeat": "Afrobeat (Classic)",
    "contemporary r&b": "R&B",
    "alternative r&b": "R&B",
    "rhythm and blues": "R&B",
    "boom bap": "Boom Bap/Old School",
    "west coast hip hop": "West Coast",
    "east coast hip hop": "East Coast",
    "southern hip hop": "Southern",
    "g-funk": "G-Funk",
    "crunk": "Crunk",
    "jazz rap": "Jazz",
    "uk rap": "UK Rap",
    "british hip hop": "UK Rap",
    "funk carioca": "Brazilian Funk",
    "baile funk": "Brazilian Funk",
    "amapiano": "Amapiano-Afrobeats",
    "jersey club": "Jersey Club",
    "conscious hip hop": "Conscious",
    "cloud rap": "Ambient/Cloud",
    "reggae": "Roots Reggae",
    "roots reggae": "Roots Reggae",
    "ragga": "Ragga",
    # Ordinary phonk is not Brazilian Phonk. Ignore the label.
    "phonk": None,
}

QUOTE_RES = (
    re.compile(r'"[^"]*"'),
    re.compile(r"“[^”]*”"),
    re.compile(r"«[^»]*»"),
    re.compile(r"„[^“]*“"),
)
FREE_TAG_RE = re.compile(
    r"[\[\(\{*]+\s*(?:free(?:\s+for\s+profit)?|f\s*f\s*p|ffp|sold|not\s+free)\s*[\]\)\}*]+",
    re.IGNORECASE,
)
# Stop at the next clause. A prod credit must not swallow "Trap Type Beat" after it.
PROD_TAIL_RE = re.compile(
    r"(?:"
    r"\((?:prod|produced)[^)]*\)"
    r"|\|\s*(?:prod|produced)\b[^|]*"
    r"|\b(?:prod|produced)\.?\s*by\s+\S+"
    r")",
    re.IGNORECASE,
)
SKIP_RE = re.compile(r"\bhow to make\b|\btutorials?\b|\bcompilations?\b", re.IGNORECASE)
TYPEBEAT_RE = re.compile(r"\btype\s*beats?\b", re.IGNORECASE)
INSTRUMENTAL_RE = re.compile(r"\binstrumentals?\b", re.IGNORECASE)
SPLIT_RE = re.compile(
    r"\s*(?:,|\bx\b|\bw/|\bfeat\.?|\bft\.?|\bvs\.?|\band\b)\s*|[×+]",
    re.IGNORECASE,
)
AMP_RE = re.compile(r"\s+&\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+")
ANYWHERE = [(re.compile(p), g) for p, g in ANYWHERE_SRC]

_STYLE_MAP: dict[str, str] = {}
_style_parts: list[str] = []
for _phrase, _genre in sorted(STYLES, key=lambda item: len(item[0]), reverse=True):
    _STYLE_MAP[_phrase] = _genre
    _style_parts.append(re.escape(_phrase).replace(r"\ ", r"\s+"))
STYLE_RE = re.compile(
    r"\b(?P<style>" + "|".join(_style_parts) + r")\s+type\s*beats?\b"
)

ALIAS: dict[tuple[str, ...], str] = {}
EXACT: set[str] = set()
SQUEEZE: set[str] = set()
MAX_ALIAS_LEN = 1

_CHARMAP = str.maketrans({
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "á": "a", "à": "a", "â": "a", "ä": "a",
    "í": "i", "ì": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "ö": "o",
    "ú": "u", "ù": "u", "ü": "u",
    "ñ": "n", "ç": "c",
    "'": "", "’": "", "`": "", "´": "",
})


def spec_of(genre: str) -> int:
    return SPEC.get(genre, 50)


def canon(text: str) -> str:
    s = text.lower().replace("$", "s").replace("€", "e").replace("£", "")
    s = s.replace("&", " & ").translate(_CHARMAP)
    s = s.replace(".", " ")
    s = re.sub(r"[-_/]+", " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def collapse_initials(tokens: list[str]) -> list[str]:
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        if len(buf) >= 2:
            out.append("".join(buf))
        else:
            out.extend(buf)
        buf.clear()

    for tok in tokens:
        if len(tok) == 1 and tok.isalpha():
            buf.append(tok)
        else:
            flush()
            out.append(tok)
    flush()
    return out


def tokenize(text: str) -> list[str]:
    return collapse_initials(TOKEN_RE.findall(canon(text)))


def name_key(text: str) -> str:
    return " ".join(tokenize(text))


def add_alias(name: str, genre: str) -> None:
    global MAX_ALIAS_LEN
    if genre not in SPEC:
        return
    toks = tokenize(name)
    if not toks or len(toks) > 6:
        return
    joined = " ".join(toks)
    if joined in SKIP_NAMES:
        return
    if len(toks) == 1:
        tok = toks[0]
        if len(tok) < 2 or tok in DENY:
            return
    key = tuple(toks)
    ALIAS[key] = genre
    MAX_ALIAS_LEN = max(MAX_ALIAS_LEN, len(key))
    SQUEEZE.add("".join(key))
    if len(key) == 1 and (len(key[0]) <= 4 or key[0] in EXACT_EXTRA):
        EXACT.add(key[0])
    if len(key) > 1:
        squeezed = "".join(key)
        if len(squeezed) >= 5 and squeezed not in DENY:
            ALIAS[(squeezed,)] = genre
            SQUEEZE.add(squeezed)


def reset_index() -> None:
    global MAX_ALIAS_LEN
    ALIAS.clear()
    EXACT.clear()
    SQUEEZE.clear()
    MAX_ALIAS_LEN = 1


def source_genre(row: dict) -> str:
    genre = row.get("genre") or ""
    sub = (row.get("sub") or "").strip()
    if genre == "Hip-Hop":
        return HIPHOP_SUB_GENRE.get(sub, "Hip-Hop")
    return genre


def load_cached_remote() -> dict[str, dict]:
    if not LIB_PATH.is_file():
        return {}
    try:
        rows = json.loads(LIB_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    cached: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("source") not in ("llm", "wikidata"):
            continue
        name = name_key(str(row.get("name") or ""))
        if not name:
            continue
        cached[name] = {
            "name": name,
            "genre": row.get("genre"),
            "source": row["source"],
            "choice": row.get("choice"),
            "confidence": row.get("confidence"),
        }
    return cached


def entry_genre(entry: dict) -> str | None:
    source = entry.get("source")
    if source in ("hand", "djcrates", "wikidata"):
        genre = entry.get("genre")
        return genre if isinstance(genre, str) and genre in SPEC else None
    if source != "llm":
        return None
    choice = entry.get("choice")
    if not choice or choice == "other" or choice not in LLM_MAP:
        return None
    try:
        confidence = float(entry.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < LLM_MIN_CONF:
        return None
    name = entry.get("name") or ""
    if name in _STYLE_MAP or name in SKIP_NAMES or name in LLM_NAME_BLOCK:
        return None
    if re.search(r"\b(?:19|20)\d{2}\b", name):
        return None
    genre = LLM_MAP[choice]
    # Title phrases already cover these stations. Do not file a rapper there
    # unless the name itself says funk/phonk or the judgment is very sure.
    if genre in ("Brazilian Funk", "Brazilian Phonk") and not re.search(
        r"brazil|baile|carioca|funk", name
    ):
        if confidence < 0.85:
            return None
    if genre == "Brazilian Funk" and "stan" in name.split():
        return None
    return genre


def build_entries(cached: dict[str, dict] | None = None) -> dict[str, dict]:
    remote = load_cached_remote() if cached is None else cached
    entries: dict[str, dict] = {}
    if DJCRATES_PATH.is_file():
        rows = json.loads(DJCRATES_PATH.read_text(encoding="utf-8"))
        for row in rows:
            name = name_key(str(row.get("name") or ""))
            if not name or name in SKIP_NAMES:
                continue
            genre = source_genre(row)
            if genre not in SPEC:
                continue
            entries[name] = {"name": name, "genre": genre, "source": "djcrates"}
    for alias, genre in HAND.items():
        name = name_key(alias)
        if not name:
            continue
        entries[name] = {"name": name, "genre": genre, "source": "hand"}
    for name, row in remote.items():
        if name not in entries:
            entries[name] = row
    return entries


def save_library(entries: dict[str, dict]) -> None:
    LIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in sorted(entries.values(), key=lambda row: row["name"]):
        item = {
            "name": entry["name"],
            "genre": entry.get("genre"),
            "source": entry["source"],
        }
        if entry.get("choice"):
            item["choice"] = entry["choice"]
        if entry.get("confidence") is not None:
            item["confidence"] = entry["confidence"]
        rows.append(item)
    tmp = LIB_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LIB_PATH)


def install_phrases(rows: list[dict]) -> None:
    """Compile phrase rules from genres.db. The full title is what gets matched."""
    global ANYWHERE, _STYLE_MAP, STYLE_RE
    anywhere: list[tuple[re.Pattern[str], str]] = []
    styles: list[tuple[str, str]] = []
    for row in rows:
        genre = str(row["genre"])
        pattern = row.get("pattern")
        scope = row.get("scope") or "anywhere"
        if pattern:
            anywhere.append((re.compile(str(pattern)), genre))
        elif scope == "typebeat":
            styles.append((str(row["phrase"]), genre))
        else:
            phrase = str(row["phrase"])
            pat = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"
            anywhere.append((re.compile(pat), genre))
    if not anywhere and not styles:
        return
    ANYWHERE = anywhere
    _STYLE_MAP = {}
    parts: list[str] = []
    for phrase, genre in sorted(styles, key=lambda item: len(item[0]), reverse=True):
        _STYLE_MAP[phrase] = genre
        parts.append(re.escape(phrase).replace(r"\ ", r"\s+"))
    if parts:
        STYLE_RE = re.compile(
            r"\b(?P<style>" + "|".join(parts) + r")\s+type\s*beats?\b"
        )
    else:
        STYLE_RE = re.compile(r"(?!)")


def rebuild_index(entries: dict[str, dict] | None = None) -> None:
    reset_index()
    from radio.genre_db import alias_rows, phrase_rows, subgenre_weights

    weights = subgenre_weights()
    if weights:
        SPEC.update(weights)
        for name, genre in alias_rows():
            add_alias(name, genre)
        install_phrases(phrase_rows())
        return
    if not entries:
        return
    grouped: dict[str, list[dict]] = {"llm": [], "wikidata": [], "djcrates": [], "hand": []}
    for entry in entries.values():
        grouped.setdefault(entry["source"], []).append(entry)
    for source in ("llm", "wikidata", "djcrates", "hand"):
        for entry in grouped.get(source, []):
            genre = entry_genre(entry)
            if genre:
                add_alias(entry["name"], genre)


def strip_quotes(title: str) -> str:
    """Keep every word. Quote marks are separators, not deletions."""
    text = title
    for ch in "\"“”„«»❝❞〝〞＂":
        text = text.replace(ch, " ")
    return text


def phrase_surface(title: str) -> str:
    text = strip_quotes(title).lower()
    text = text.replace("’", "'").replace("`", "'").replace("´", "'")
    text = FREE_TAG_RE.sub(" ", text)
    text = PROD_TAIL_RE.sub(" ", text)
    # Subtitle dashes split artist clauses without deleting either side.
    text = re.sub(r"\s+[-–—~]+\s+", " | ", text)
    text = text.replace("-", " ").replace("_", " ").replace("/", " ")
    text = re.sub(r"[\[\]\(\)\{\}*]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def phrase_genre(surface: str) -> str | None:
    text = surface.replace("|", " ")
    text = re.sub(r"\s+", " ", text)
    best: str | None = None
    best_spec = -1
    for cre, genre in ANYWHERE:
        if cre.search(text) and spec_of(genre) > best_spec:
            best = genre
            best_spec = spec_of(genre)
    for match in STYLE_RE.finditer(text):
        style = re.sub(r"\s+", " ", match.group("style"))
        genre = _STYLE_MAP.get(style)
        if genre and spec_of(genre) > best_spec:
            best = genre
            best_spec = spec_of(genre)
    return best


def strip_channel(surface: str, channel: str | None) -> str:
    if not channel:
        return surface
    raw = channel.lower().strip()
    if len(raw) < 4:
        return surface
    squeezed = "".join(tokenize(raw))
    if squeezed in SQUEEZE:
        return surface
    return surface.replace(raw, " ")


def artist_blob(surface: str, channel: str | None) -> str:
    text = TYPEBEAT_RE.sub(" ", surface)
    text = INSTRUMENTAL_RE.sub(" ", text)
    text = strip_channel(text, channel)
    return text


def iter_clauses(text: str):
    for part in text.split("|"):
        for bit in AMP_RE.split(part):
            for clause in SPLIT_RE.split(bit):
                clause = clause.strip(" -~:.;")
                if clause:
                    yield clause


def match_raw(tokens: list[str]) -> list[str]:
    found: list[str] = []
    index = 0
    count = len(tokens)
    while index < count:
        matched = False
        upper = min(MAX_ALIAS_LEN, count - index)
        for length in range(upper, 0, -1):
            window = tuple(tokens[index : index + length])
            genre = ALIAS.get(window)
            if genre is None:
                continue
            if length == 1 and window[0] in EXACT and tuple(tokens) != window:
                continue
            found.append(genre)
            index += length
            matched = True
            break
        if not matched:
            index += 1
    return found


def match_tokens(tokens: list[str]) -> list[str]:
    tokens = [tok for tok in tokens if tok not in STRUCTURE]
    found = match_raw(tokens)
    if found:
        return found
    if tokens and tokens[0] in {"the", "a", "an"}:
        return match_raw(tokens[1:])
    return []


def majority(genres: list[str]) -> str | None:
    if not genres:
        return None
    ranked = Counter(genres).most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def artist_genres(surface: str, channel: str | None) -> list[str]:
    found: list[str] = []
    for clause in iter_clauses(artist_blob(surface, channel)):
        found.extend(match_tokens(tokenize(clause)))
    return found


def resolve(phrase: str | None, artist: str | None) -> str | None:
    if phrase and artist:
        if spec_of(phrase) >= spec_of(artist):
            return phrase
        return artist
    return phrase or artist


def _scene_adjust(surface: str, genre: str | None) -> str | None:
    """A few artists only move when the title names the scene.

    A tighter phrase (drill, for example) still wins. Midwest emo is not emo rap.
    """
    emo = re.search(r"(?<!midwest\s)\bemo\b", surface)
    if re.search(r"\blil uzi(?: vert)?\b|\buzi vert\b", surface):
        if re.search(r"\brage\b|\bopium\b", surface):
            if genre is None or spec_of(genre) <= spec_of("Rage/Opium"):
                return "Rage/Opium"
        elif emo or re.search(r"\bsoundcloud\b", surface):
            if genre is None or spec_of(genre) <= spec_of("Emo Rap"):
                return "Emo Rap"
    if re.search(r"\bjuice w(?:rld|orld)\b", surface) and emo:
        if genre is None or spec_of(genre) <= spec_of("Emo Rap"):
            return "Emo Rap"
    return genre


def classify(title: str | None, channel: str | None = None) -> str | None:
    if not title:
        return None
    surface = phrase_surface(title)
    if not surface or SKIP_RE.search(surface):
        return None
    phrase = phrase_genre(surface)
    artist = majority(artist_genres(surface, channel))
    return _scene_adjust(surface, resolve(phrase, artist))


def unmatched_names(title: str, channel: str | None) -> list[str]:
    surface = phrase_surface(title)
    if not surface or SKIP_RE.search(surface):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for clause in iter_clauses(artist_blob(surface, channel)):
        tokens = [tok for tok in tokenize(clause) if tok not in STRUCTURE]
        if not tokens or len(tokens) > 4:
            continue
        if match_tokens(tokens):
            continue
        if all(tok in NAME_STOP for tok in tokens):
            continue
        if len(tokens) == 1 and (len(tokens[0]) < 3 or tokens[0] in NAME_STOP):
            continue
        if not any(char.isalpha() for char in "".join(tokens)):
            continue
        name = " ".join(tokens)
        if name in seen or name in SKIP_NAMES:
            continue
        seen.add(name)
        names.append(name)
    return names


def _self_check() -> None:
    cases = [
        ("NEIGHBORHOOD | Trap Type Beat | Freestyle Beat", "Trap"),
        ("Trap Type Beat", "Trap"),
        ("trap beat", "Trap"),
        ("trap instrumental", None),
        ("hoodtrap type beat", "Hoodtrap"),
        ("evil jerk + hoodtrap type beat", "Hoodtrap"),
        ("SuperTrap Type Beat", "Supertrap"),
        ("supertrap type beat", "Supertrap"),
        ("afrotrap type beat", None),
        ('"trap" type beat', "Trap"),
        ('Drake Type Beat "Trap"', "Trap"),
        ('Something "Trap Type Beat"', "Trap"),
        ("Drake Type Beat | Trap Type Beat", "Trap"),
        ("Gunna Type Beat | Trap Type Beat", "Melodic Trap"),
        ("West Coast Type Beat", "West Coast"),
        ("Shoreline Mafia x West Coast Type Beat", "West Coast"),
        ("East Coast Type Beat", "East Coast"),
        ("Southern Type Beat", "Southern"),
        ("Midwest Type Beat", "Midwest"),
        (
            '(FREE) R&B Dancehall Type Beat x Afro R&B Type Beat "Slow Burn" Afroswing Instrumental',
            "Afroswing",
        ),
        ("R&B Dancehall Type Beat", "Dancehall"),
        ("Dancehall Type Beat", "Dancehall"),
        ("R&B Type Beat", "R&B"),
        ("trapsoul type beat", "Trapsoul"),
        ("Trapsoul x Drake Type Beat", "Trapsoul"),
        ("Metro Boomin x 21 Savage x JID Type Beat", "Trap"),
        ("JID Type Beat", "Conscious"),
        ("J.I.D Type Beat", "Conscious"),
        ("Rema Afrobeat Type Beat", "Afrobeat (Classic)"),
        ("Afrobeats Type Beat", "Afrobeat (Classic)"),
        ("afro beat type beat", "Afrobeat (Classic)"),
        ("Rema Type Beat", "Afrobeat (Classic)"),
        ("Omah Lay Type Beat", "Afrobeat (Classic)"),
        ("Dizzee Rascal Type Beat", "Grime"),
        ("Headie One x Teeway Type Beat", "Drill"),
        ("Giggs Type Beat | Trap Instrumental", "Grime"),
        ("Giggs Type Beat | Trap Type Beat", "Grime"),
        ("Drake x Rihanna Type Beat | Dancehall Type Beat", "Dancehall"),
        ("Drake x Rihanna Type Beat", None),
        ("Drake Type Beat", "Hip-Hop"),
        ("Rihanna Type Beat", "R&B"),
        ("Rihanna Dance Pop Type Beat", "Dance Pop"),
        ("Doechii Type Beat", "Hip-Hop"),
        ("Doechii x Drake Type Beat", "Hip-Hop"),
        ("Frank Ocean Type Beat", "R&B"),
        ("Dave Type Beat", "UK Rap"),
        ("Santan Dave Type Beat", "UK Rap"),
        ("Dave x Zzzunknown Type Beat", "UK Rap"),
        ("big dave type beat", None),
        ("Dave East Type Beat", "East Coast"),
        ("Davido Type Beat", "R&B"),
        ("Central Cee Type Beat", "Drill"),
        ("Headie One x Central Cee Type Beat", "Drill"),
        ("Dave x Giggs Type Beat", None),
        ("Unknown T x Dave Type Beat", "UK Rap"),
        ("Santan Dave x Central Cee Type Beat", None),
        ("Nines Type Beat", "UK Rap"),
        ("Potter Payper Type Beat", "UK Rap"),
        ("Marnz Malone Type Beat", "UK Rap"),
        ("Clavish Type Beat", "UK Rap"),
        ("D Block Europe Type Beat", "UK Rap"),
        ("Bugzy Malone Type Beat", "UK Rap"),
        ("Knucks Type Beat", "UK Rap"),
        ("Nemzzz Type Beat", "UK Rap"),
        ("Unknown T Type Beat", "UK Rap"),
        ("AJ Tracey Type Beat", "UK Rap"),
        ("Skepta Type Beat", "Grime"),
        ("Stormzy Type Beat", "Grime"),
        ("Kodak Black x Zzzquux Type Beat", "Trap"),
        ("melodic trap type beat", "Melodic Trap"),
        ("dark trap type beat", "Dark/Aggressive"),
        ("Kodak Black Dark Type Beat", "Dark/Aggressive"),
        ("uk drill type beat", "Drill"),
        ("drill type beat", "Drill"),
        ("phonk type beat", "Phonk"),
        ("Brazilian Phonk Type Beat", "Brazilian Phonk"),
        ("funk phonk type beat", "Brazilian Phonk"),
        ("Baile Funk Type Beat", "Brazilian Funk"),
        ("Brazilian Funk Type Beat", "Brazilian Funk"),
        ("MC STAN Type Beat", "Hip-Hop"),
        ("Freddie Dredd Type Beat", None),
        ("Skillibeng Type Beat", "Dancehall"),
        ("Popcaan Type Beat", "Dancehall"),
        ("Vybz Kartel Type Beat", "Dancehall"),
        ("Gunna x Roddy Ricch Type Beat", "Melodic Trap"),
        ("YNW Melly Type Beat", "Melodic Trap"),
        ("Larry June Type Beat", "West Coast"),
        ("Jay Worthy Type Beat", "West Coast"),
        ("Ohgeesy Type Beat", "West Coast"),
        ("Loyle Carner Type Beat", "UK Rap"),
        ("Loyle Carner x Little Simz Type Beat", None),
        ("Loyle Carner x J. Cole x Little Simz Type Beat", "Conscious"),
        ("Little Simz Type Beat", "Conscious"),
        ("lo-fi type beat", "Lo-fi/Chill"),
        ("lofi type beat", "Lo-fi/Chill"),
        ("chill type beat", "Lo-fi/Chill"),
        ("chillhop type beat", "Lo-fi/Chill"),
        ("chilling type beat", None),
        ('"chill" type beat', "Lo-fi/Chill"),
        ("Nirvana x Grunge x Alternative Rock Type Beat", "Grunge"),
        ("Shoegaze x Grunge Type Beat", "Shoegaze"),
        ("shoegaze type beat", "Shoegaze"),
        ("shoegazing type beat", "Shoegaze"),
        ("grunge type beat", "Grunge"),
        ("nirvana type beat", "Nirvana"),
        ("alt-rock type beat", "Alternative Rock"),
        ("alternative rock type beat", "Alternative Rock"),
        ("Nujabes Type Beat", "Jazz"),
        ("Mick Jenkins Type Beat", "Boom Bap/Old School"),
        ("Joey Bada$$ Type Beat", "Boom Bap/Old School"),
        ("MF DOOM Type Beat", "Boom Bap/Old School"),
        ("Onefour Type Beat", "Drill"),
        ("Young M.A Type Beat", "Hip-Hop"),
        ("9lokknine Type Beat", "Trap"),
        ("future bass type beat", None),
        ("Future Type Beat", "Melodic Trap"),
        ("Autumn! Type Beat", "Plugg/Pluggnb"),
        ("autumn leaves type beat", None),
        ("How To Make A Drake Type Beat Tutorial", None),
        ("Nas Type Beat", "Boom Bap/Old School"),
        ("Wizkid Type Beat", "Afropop"),
        ("Burna Boy Type Beat", "Afrofusion"),
        ("Kendrick Lamar Type Beat", "West Coast"),
        ("J. Cole Type Beat", "Conscious"),
        ("The Weeknd Type Beat", "R&B"),
        ("H.E.R. Type Beat", "R&B"),
        ("N.W.A Type Beat", "West Coast"),
        ("A Boogie Type Beat", "Melodic Trap"),
        ("The Game Type Beat", "West Coast"),
        ("Playboi Carti Type Beat", "Rage/Opium"),
        ("Che x Summrs Type Beat", None),
        ("Che Type Beat", "Rage/Opium"),
        ("Summrs x Autumn Type Beat", "Plugg/Pluggnb"),
        ("Gunna x Young Thug Type Beat", "Melodic Trap"),
        ("21 Savage x Key Glock Type Beat", "Trap"),
        ("G Herbo x Veeze Type Beat", None),
        ("Lil Durk Type Beat", "Drill"),
        ("Pop Smoke Type Beat", "Drill"),
        ("Ice Spice Type Beat", "Drill"),
        ("DaBaby Type Beat", "Trap"),
        ("Young Thug Type Beat", "Melodic Trap"),
        ("Big Sean Type Beat", "Southern"),
        ("Lil Baby Type Beat", "Melodic Trap"),
        ("OsamaSon x SoFaygo Type Beat", "Rage/Opium"),
        ("spice type beat", "Dancehall"),
        ("old spice type beat", None),
        ("Digga D Type Beat", "Drill"),
        ("Loski Type Beat", "Drill"),
        ("Chief Keef Type Beat", "Drill"),
        ("Metro Boomin Type Beat", "Trap"),
        ("Tyla Type Beat", "Amapiano-Afrobeats"),
        ('Drake Type Beat "West Coast"', "West Coast"),
        ("type beat compilation vol 3", None),
        ("Detroit Type Beat", "Detroit"),
        ("Experimental Type Beat", "Experimental/Glitch"),
        ("Pierre Bourne Type Beat", "Plugg/Pluggnb"),
        ("Lucki Type Beat", "Plugg/Pluggnb"),
        ("EBK Jaaybo Type Beat", "West Coast"),
        ("Iayze Type Beat", "Rage/Opium"),
        ("Plug Type Beat", None),
        ("Jerk Type Beat", "Plugg/Pluggnb"),
        ("Corridos Tumbados Type Beat", "Corridos Tumbados"),
        ("Peso Pluma Type Beat", "Corridos Tumbados"),
        ("latin trap type beat", "Latin Trap"),
        ("RKT Type Beat", "RKT"),
        ("speed garage type beat", "UK Garage"),
        ("2-step type beat", "UK Garage"),
        ("Cloud Type Beat", None),
        ("Dembow Type Beat", "Dembow"),
        ("BigXthaPlug Type Beat", "Southern"),
        ("Young Chop Type Beat", "Drill"),
        ("Three 6 Mafia Type Beat", "Crunk"),
        ("Rome Streetz Type Beat", "Boom Bap/Old School"),
        (
            '[FREE] Trap Type Beat - "ROLLIN" | Type Beat | Freestyle Beat | Rap Type Beat 2026',
            "Trap",
        ),
        (
            '"ESCAPE" | Trap Type Beat | Freestyle Beat | Type Beat | Hard Type Beat | Rap Type Beat 2026',
            "Trap",
        ),
        ("type beat trap", "Trap"),
        ("trap metal type beat", "Trap"),
        ("deep house type beat", "Club"),
        ("edm club banger", "Club"),
        ("sad midwest emo / acoustic type beat", "Midwest Emo"),
        ("indie rock type beat", "Indie Rock"),
        ("indie type beat", None),
        ("cumbia type beat", "Cumbia"),
        ("The Neptunes Type Beat", "2000s"),
        ("Pharrell Type Beat", "2000s"),
        ("groovy 80s type beat", "80s"),
        ("90s type beat", "90s"),
        ("Travis Scott Type Beat", "Trap"),
        ("Travis Scott Rage Type Beat", "Rage/Opium"),
        ("500 Cigarettes Type Beat", "Meme"),
        ("SKIBIDI TOILET TYPE BEAT", "Meme"),
        ("Cigarettes After Sex Type Beat", None),
        ("Lil Peep Type Beat", "Emo Rap"),
        ("Juice WRLD Type Beat", "Melodic Trap"),
        ("Juice WRLD Emo Type Beat", "Emo Rap"),
        ("Lil Uzi Vert Type Beat", None),
        ("Lil Uzi Vert Rage Type Beat", "Rage/Opium"),
        ("Lil Uzi Vert Soundcloud Type Beat", "Emo Rap"),
        ("XXXTentacion Type Beat", "Emo Rap"),
        ("DJ Premier Type Beat", "Boom Bap/Old School"),
        ("Jay-Z Type Beat", None),
        ("El Alfa Type Beat", "Dembow"),
        ("Hamza Type Beat", "R&B"),
        ("Smino Type Beat", "Hip-Hop"),
        ("J Hus Type Beat", "Afroswing"),
    ]
    failed = 0
    for title, expected in cases:
        got = classify(title, "")
        if got != expected:
            failed += 1
            print(f"FAIL {title!r} -> {got!r} expected {expected!r}")
    from radio.genres import RADIO_GENRES, get_genre, parent_has_button, parent_of

    trap = get_genre("trap")
    rap = get_genre("rap")
    west = get_genre("west")
    boombap = get_genre("boombap")
    south = get_genre("southern")
    y2010 = get_genre("y2010s")
    lofi = get_genre("lofi")
    caribbean = get_genre("caribbean")
    latin = get_genre("latin")
    uk = get_genre("uk")
    nineties = get_genre("90s")
    y2000 = get_genre("2000s")
    latin_kw = latin["keywords"] if latin else []
    checks = [
        get_genre("hiphop") is None,
        get_genre("throwback") is None,
        get_genre("plugg") is None,
        get_genre("jazz") is None,
        trap and "Trapsoul" in trap["db_genres"] and "Hoodtrap" in trap["db_genres"],
        rap and rap["db_genres"] == ["Hip-Hop", "Midwest", "Pop Rap"],
        rap and "East Coast" not in rap["db_genres"] and "G-Funk" not in rap["db_genres"],
        west and west["db_genres"] == ["West Coast", "G-Funk"],
        boombap and boombap["db_genres"] == ["Boom Bap/Old School", "East Coast", "Conscious"],
        boombap and "90s" not in boombap["keywords"] and "lofi" not in boombap["keywords"],
        south and south["db_genres"] == ["Southern", "Crunk"],
        y2010 and y2010["db_genres"] == ["Plugg/Pluggnb", "Emo Rap", "Phonk"],
        y2010 and "Brazilian Phonk" not in y2010["db_genres"],
        lofi and lofi["db_genres"] == ["Lo-fi/Chill", "Jazz"],
        lofi and "lofi" in lofi["keywords"] and "jazz" in lofi["keywords"],
        caribbean and caribbean["db_genres"] == ["Dancehall", "Dembow", "Reggaeton"],
        caribbean and "Cumbia" not in caribbean["db_genres"],
        latin and "Cumbia" in latin["db_genres"] and "Brazilian Phonk" in latin["db_genres"],
        latin and "Corridos Tumbados" in latin["db_genres"],
        "phonk" not in latin_kw and "funk" not in latin_kw,
        "brazilian phonk" in latin_kw and "baile funk" in latin_kw,
        uk and "Afroswing" in uk["db_genres"],
        nineties and nineties["parent"] == "90s",
        y2000 and y2000["db_genres"] == ["2000s"],
        bool(get_genre("country")) == parent_has_button("Country"),
        bool(get_genre("80s")) == parent_has_button("80s"),
        parent_of("Hoodtrap") == "Trap",
        parent_of("Trapsoul") == "Trap",
        parent_of("Jazz") == "Lo-fi",
        parent_of("90s") == "90s",
        parent_of("Boom Bap/Old School") == "Boom Bap",
        parent_of("G-Funk") == "West Coast",
        parent_of("East Coast") == "Boom Bap",
        parent_of("Hip-Hop") == "Rap",
        parent_of("Plugg/Pluggnb") == "2010s",
        parent_of("Phonk") == "2010s",
        parent_of("Emo Rap") == "2010s",
        parent_of("Afroswing") == "UK",
        parent_of("Reggaeton") == "Caribbean",
        parent_of("Cumbia") == "Latin",
        parent_of("Brazilian Phonk") == "Latin",
        parent_of("RKT") == "Latin",
        not any(g["label"] in ("Hip-Hop", "Throwback", "Plugg", "Jazz") for g in RADIO_GENRES),
    ]
    if not all(checks):
        failed += 1
        print("FAIL station wiring", checks)
    if failed:
        raise SystemExit(f"{failed} classifier checks failed")
    print(f"classifier checks ok ({len(cases)}) aliases {len(ALIAS)}", flush=True)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def free_bytes() -> int:
    return shutil.disk_usage(ROOT).free


def foreign_writers() -> list[str]:
    me = os.getpid()
    parent = os.getppid()
    needles = (
        "tag_by_artist.py",
        "tag_underground_rules.py",
        "tag_underground_pass.py",
        "jev_sweep.py",
        "tagger.py",
    )
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    hits = []
    for line in out.splitlines():
        if not any(needle in line for needle in needles):
            continue
        pid_text = line.strip().split(" ", 1)[0]
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid in (me, parent):
            continue
        command = line.strip().split(" ", 1)[1] if " " in line.strip() else ""
        if command.startswith(("/bin/zsh", "/bin/bash", "zsh ", "bash ")):
            continue
        hits.append(line.strip())
    return hits


def assert_safe_to_write() -> None:
    hits = foreign_writers()
    if hits:
        raise SystemExit("another genre writer is running:\n" + "\n".join(hits))
    free = free_bytes()
    gib = free / (1024**3)
    print(f"free disk {gib:.2f} GiB", flush=True)
    if free < MIN_FREE:
        raise SystemExit(f"disk is tight ({gib:.2f} GiB free, need 3 GiB); not writing")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    conn.execute("PRAGMA busy_timeout=120000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-262144")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def _wal_bytes() -> int:
    wal = DB_PATH.with_name("typebeats.db-wal")
    try:
        return wal.stat().st_size
    except OSError:
        return 0


def _checkpoint(conn: sqlite3.Connection, truncate: bool = False) -> None:
    mode = "TRUNCATE" if truncate else "PASSIVE"
    try:
        conn.execute(f"PRAGMA wal_checkpoint({mode})")
    except sqlite3.Error:
        return


def _rowid_bounds(conn: sqlite3.Connection) -> tuple[int, int]:
    low, high = conn.execute("SELECT MIN(rowid), MAX(rowid) FROM beats").fetchone()
    return int(low or 1), int(high or 0)


def iter_underground(conn: sqlite3.Connection, span: int = 50000):
    """Sequential rowid slices. A views keyset random-reads one page per title."""
    low, high = _rowid_bounds(conn)
    cursor = low - 1
    while cursor < high:
        end = cursor + span
        rows = conn.execute(
            """
            SELECT video_id, title, channel_name
            FROM beats
            WHERE rowid > ? AND rowid <= ? AND genre = 'Underground'
            """,
            (cursor, end),
        ).fetchall()
        cursor = end
        if rows:
            yield rows


def scan_unmatched(conn: sqlite3.Connection) -> Counter[str]:
    counts: Counter[str] = Counter()
    scanned = 0
    started = time.time()
    for rows in iter_underground(conn):
        for _video_id, title, channel in rows:
            scanned += 1
            if classify(title, channel):
                continue
            for name in unmatched_names(title, channel):
                counts[name] += 1
        if scanned // 200000 != (scanned - len(rows)) // 200000:
            elapsed = max(time.time() - started, 0.001)
            print(f"name scan {scanned:,} ({scanned / elapsed:,.0f} rows/s)", flush=True)
    print(f"name scan done {scanned:,} unique {len(counts):,}", flush=True)
    return counts


def wikidata_lookup(names: list[str]) -> dict[str, str]:
    """One SPARQL request. Empty dict if it stalls or errors."""
    safe = []
    for name in names:
        if re.fullmatch(r"[a-z0-9 ]+", name) and " " in name:
            safe.append(name)
        if len(safe) >= WIKI_CAP:
            break
    if not safe:
        print("wikidata skipped: no multi-word names", flush=True)
        return {}
    values = " ".join(json.dumps(name.title()) for name in safe)
    query = f"""
    SELECT ?name ?genreLabel WHERE {{
      VALUES ?name {{ {values} }}
      ?artist rdfs:label ?name.
      ?artist wdt:P136 ?genre.
      FILTER(LANG(?name) = "en")
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    req = urllib.request.Request(
        "https://query.wikidata.org/sparql",
        data=data,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "TypebeatLocalTagger/1.0 (personal music library)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=WIKI_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"wikidata skipped: {type(exc).__name__}", flush=True)
        return {}
    by_name: dict[str, list[str]] = {}
    for row in payload.get("results", {}).get("bindings", []):
        label = row.get("name", {}).get("value", "")
        genre_label = (row.get("genreLabel", {}).get("value") or "").strip().lower()
        key = name_key(label)
        if not key or genre_label not in WIKI_MAP:
            continue
        mapped = WIKI_MAP[genre_label]
        if mapped:
            by_name.setdefault(key, []).append(mapped)
    chosen: dict[str, str] = {}
    for key, genres in by_name.items():
        ranked = sorted(set(genres), key=spec_of, reverse=True)
        if len(ranked) > 1 and spec_of(ranked[0]) == spec_of(ranked[1]):
            continue
        chosen[key] = ranked[0]
    print(f"wikidata labeled {len(chosen)} of {len(safe)}", flush=True)
    return chosen


def llm_questions():
    from typesafe_sdk import Choice

    criteria = {
        "brazilian_phonk": "Brazilian funk phonk only. Not US phonk, drift phonk, or $uicideboy$.",
        "brazilian_funk": "Baile funk or funk carioca. Not MC Stan and not US funk.",
        "afroswing": "UK afroswing (J Hus, Not3s, Kojo Funds).",
        "dancehall": "Jamaican dancehall (Skillibeng, Vybz Kartel, Popcaan).",
        "drill": "Drill, including UK drill (Headie One, Central Cee) and NY/Chicago drill.",
        "melodic_trap": "Melodic, emo, or guitar trap (Gunna, Lil Baby, Roddy Ricch, YNW Melly).",
        "dark": "Dark, horror, or aggressive trap, or US phonk that is not Brazilian.",
        "grime": "Grime (Skepta, Stormzy, Dizzee Rascal, Giggs, Wiley).",
        "uk_rap": "UK rap that is not grime and not drill (Dave, Loyle Carner, Nines; Central Cee is drill).",
        "afrobeat": "Afrobeats or classic afrobeat (Rema, Omah Lay, Wizkid, Burna Boy, Fela).",
        "rage": "Rage or opium (Playboi Carti, Yeat, Ken Carson, Destroy Lonely).",
        "plugg": "Plugg or pluggnb (Summrs, Autumn, Xavier Sobased).",
        "amapiano": "Amapiano.",
        "uk_garage": "UK garage or 2-step.",
        "jazz": "Jazz or jazz-rap (Nujabes, Robert Glasper).",
        "jersey": "Jersey club.",
        "west_coast": "West Coast hip-hop (Shoreline Mafia, Larry June, Kendrick).",
        "east_coast": "East Coast hip-hop that is not boom bap and not drill.",
        "southern": "Southern hip-hop that is not trap.",
        "midwest": "Midwest hip-hop.",
        "g_funk": "G-funk.",
        "boom_bap": "Boom bap or 90s hip-hop (Nas, Joey Bada$$, MF DOOM).",
        "detroit": "Detroit rap (Babytron, Veeze, 42 Dugg).",
        "conscious": "Conscious or alternative rap (Little Simz, J. Cole). Loyle Carner is UK rap.",
        "rnb": "R&B, including trapsoul. Not dancehall.",
        "dance_pop": "Dance pop.",
        "afropop": "Afropop that is not specifically afrobeats.",
        "afrofusion": "Afrofusion (Burna Boy) when it is not straight afrobeats.",
        "trap": "Generic trap (21 Savage, Metro Boomin, Kodak Black), not melodic and not drill.",
        "hiphop": "Mainstream hip-hop with no tighter station (Drake).",
        "funk": "US funk, not baile funk.",
        "ambient": "Ambient or cloud rap.",
        "experimental": "Experimental, glitch, or sigilkore.",
        "road_rap": "UK road rap that is not grime or drill.",
        "other": "Unknown, not a musician, a mood word, a beat title, or no clear station.",
    }
    return {
        "station": Choice(
            instructions=(
                "Which radio station fits type beats in the style of `artist`? "
                "Choose other when `artist` is not a musician you know, is a mood "
                "or beat title, or the style is unclear. Ordinary phonk is dark or "
                "other, never Brazilian Phonk. MC Stan is not Brazilian Funk. "
                "Central Cee and Headie One are drill, not UK rap. Giggs is grime."
            ),
            criteria=criteria,
        )
    }


async def label_names(names: list[str], entries: dict[str, dict]) -> str:
    """Return 'ok', 'missing', 'auth', or '402'. Never prints the API key."""
    import logging

    load_dotenv(ROOT / ".env")
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        print("LLM skipped: TYPESAFE_API_KEY missing", flush=True)
        return "missing"
    logging.getLogger("typesafe_sdk").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpx2").setLevel(logging.ERROR)
    from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy, TypeSafeAPIError, TypeSafeAuthenticationError

    questions = llm_questions()
    stop = asyncio.Event()
    applied = 0
    cached = 0
    status = "ok"
    sem = asyncio.Semaphore(6)

    async def one(client, name: str):
        if stop.is_set():
            return None
        async with sem:
            if stop.is_set():
                return None
            try:
                response = await client.system_one({"artist": name}, questions)
            except TypeSafeAuthenticationError:
                stop.set()
                return ("auth", name)
            except TypeSafeAPIError as exc:
                if exc.status == 402:
                    stop.set()
                    return ("402", name)
                return ("http", name, exc.status)
            except Exception:
                return ("err", name)
        answer = response.choices["station"]
        return ("ok", name, answer.choice, float(answer.confidence))

    client_retry = RetryPolicy(max_retries=0, timeout=30.0)
    try:
        async with AsyncTypeSafeClient(timeout=25.0, retry=client_retry) as client:
            pending = list(names)
            while pending and not stop.is_set():
                wave = pending[:40]
                pending = pending[40:]
                results = await asyncio.gather(*(one(client, name) for name in wave))
                for result in results:
                    if not result:
                        continue
                    kind = result[0]
                    if kind == "402":
                        status = "402"
                        print("LLM stopped: HTTP 402", flush=True)
                        stop.set()
                        break
                    if kind == "auth":
                        status = "auth"
                        print("LLM skipped: authentication failed", flush=True)
                        stop.set()
                        break
                    if kind != "ok":
                        continue
                    _kind, name, choice, confidence = result
                    genre = LLM_MAP.get(choice) if choice in LLM_MAP else None
                    entries[name] = {
                        "name": name,
                        "genre": genre,
                        "source": "llm",
                        "choice": choice,
                        "confidence": round(confidence, 4),
                    }
                    cached += 1
                    if entry_genre(entries[name]):
                        applied += 1
                if cached and cached % 50 < 40:
                    save_library(build_entries(remote_from(entries)))
                print(f"LLM cached {cached} applied {applied} left {len(pending)}", flush=True)
    except TypeSafeAuthenticationError:
        print("LLM skipped: authentication failed", flush=True)
        return "auth"
    save_library(build_entries(remote_from(entries)))
    print(f"LLM done cached {cached} indexable {applied} status {status}", flush=True)
    return status


def remote_from(entries: dict[str, dict]) -> dict[str, dict]:
    return {
        name: entry
        for name, entry in entries.items()
        if entry.get("source") in ("llm", "wikidata")
    }


def write_underground(conn: sqlite3.Connection) -> Counter[str]:
    from radio.genre_db import parent_by_subgenre

    parents = parent_by_subgenre()
    counts: Counter[str] = Counter()
    scanned = 0
    moved = 0
    started = time.time()
    for rows in iter_underground(conn):
        if free_bytes() < MIN_FREE:
            print("stopping: free disk fell below 3 GiB", flush=True)
            break
        pending: list[tuple[str, str | None, str]] = []
        for video_id, title, channel in rows:
            scanned += 1
            genre = classify(title, channel)
            if not genre or genre not in SPEC or genre == "Underground":
                continue
            pending.append((genre, parents.get(genre), video_id))
            counts[genre] += 1
            moved += 1
            if len(pending) >= BATCH:
                conn.executemany(
                    """
                    UPDATE beats
                    SET genre = ?, parent_genre = ?
                    WHERE video_id = ? AND genre = 'Underground'
                    """,
                    pending,
                )
                conn.commit()
                pending = []
                free = free_bytes()
                tight = free < MIN_FREE + 600 * 1024 * 1024
                _checkpoint(conn, truncate=tight or _wal_bytes() > 32 * 1024 * 1024)
                if free < MIN_FREE:
                    print("stopping: free disk fell below 3 GiB", flush=True)
                    _checkpoint(conn, truncate=True)
                    print(f"write scan stopped {scanned:,} moved {moved:,}", flush=True)
                    return counts
        if pending:
            conn.executemany(
                """
                UPDATE beats
                SET genre = ?, parent_genre = ?
                WHERE video_id = ? AND genre = 'Underground'
                """,
                pending,
            )
            conn.commit()
            _checkpoint(conn, truncate=_wal_bytes() > 64 * 1024 * 1024)
        if rows and scanned // 200000 != (scanned - len(rows)) // 200000:
            elapsed = max(time.time() - started, 0.001)
            print(
                f"write scan {scanned:,} moved {moved:,} ({scanned / elapsed:,.0f} rows/s) "
                f"free {free_bytes() / (1024**3):.2f} GiB",
                flush=True,
            )
    _checkpoint(conn, truncate=True)
    print(f"write scan done {scanned:,} moved {moved:,}", flush=True)
    return counts


def candidate_queue(counts: Counter[str], entries: dict[str, dict]) -> list[str]:
    queue = []
    for name, _count in counts.most_common():
        if name in entries and entries[name].get("source") in ("hand", "djcrates", "wikidata", "llm"):
            continue
        queue.append(name)
        if len(queue) >= LLM_CAP + WIKI_CAP:
            break
    return queue


def enrich(conn: sqlite3.Connection, entries: dict[str, dict], *, use_llm: bool) -> None:
    if not use_llm:
        print("LLM skipped by flag", flush=True)
        return
    counts = scan_unmatched(conn)
    queue = candidate_queue(counts, entries)
    preview = ", ".join(f"{name} ({counts[name]})" for name in queue[:12])
    print(f"unmatched queue {len(queue)} top: {preview}", flush=True)
    if not queue:
        return
    wiki_names = queue[:WIKI_CAP]
    try:
        wiki = wikidata_lookup(wiki_names)
    except Exception as exc:
        print(f"wikidata skipped: {type(exc).__name__}", flush=True)
        wiki = {}
    for name, genre in wiki.items():
        if name in entries and entries[name]["source"] in ("hand", "djcrates"):
            continue
        entries[name] = {"name": name, "genre": genre, "source": "wikidata"}
    save_library(build_entries(remote_from(entries)))
    llm_names = [name for name in queue if name not in entries][:LLM_CAP]
    if not llm_names:
        return
    asyncio.run(label_names(llm_names, entries))


def report(conn: sqlite3.Connection, counts: Counter[str]) -> None:
    remaining = conn.execute(
        "SELECT COUNT(*) FROM beats WHERE genre = 'Underground'"
    ).fetchone()[0]
    print("moved per genre:")
    for genre, count in counts.most_common():
        print(f"  {genre}: {count:,}")
    print(f"Underground remaining: {remaining:,}")
    print("new stations: UK Rap, Dancehall, Brazilian Funk, Brazilian Phonk")
    print(
        "Giggs → Grime (tighter than UK Rap). "
        "UK Rap is Dave (exact), Nines, Potter Payper, Marnz Malone, Clavish, "
        "D Block Europe, Bugzy Malone, Knucks, Nemzzz, Unknown T. "
        "Central Cee and Headie One stay Drill."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Retag Underground rows only")
    parser.add_argument("--check", action="store_true", help="self-check and write the library, no DB")
    parser.add_argument("--no-llm", action="store_true", help="skip Wikidata and TypeSafe")
    parser.add_argument("--no-write", action="store_true", help="build the library but do not update the DB")
    args = parser.parse_args()

    if not DJCRATES_PATH.is_file():
        raise SystemExit(f"missing {DJCRATES_PATH}")
    entries = build_entries()
    save_library(entries)
    rebuild_index(entries)
    _self_check()
    if args.check:
        hand = sum(1 for row in entries.values() if row["source"] == "hand")
        crates = sum(1 for row in entries.values() if row["source"] == "djcrates")
        print(f"library {LIB_PATH.name} hand {hand} djcrates {crates}", flush=True)
        return

    conn = connect()
    try:
        enrich(conn, entries, use_llm=not args.no_llm)
        entries = build_entries()
        rebuild_index(entries)
        _self_check()
        save_library(entries)
        if args.no_write:
            print("no-write: database not updated", flush=True)
            return
        assert_safe_to_write()
        counts = write_underground(conn)
        report(conn, counts)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
