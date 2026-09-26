#!/usr/bin/env python3
"""Retag beats.genre = 'Underground' from title phrases and artist aliases.

Local rules only. Does not call TypeSafe, Jev, or any network API.
Idempotent: updates only rows that are still Underground.
"""

from __future__ import annotations

import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "typebeats.db"

BATCH = 4000
READ_BATCH = 8000

# Artist alias → genre. Keys are matched case-insensitively after quote-stripping.
# One destination per alias. If a title's known artists map to different genres,
# the row stays Underground.
ARTIST_GENRE: dict[str, str] = {
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
    "trey songz": "R&B",
    "ne-yo": "R&B",
    "neyo": "R&B",
    "aaliyah": "R&B",
    "miguel": "R&B",
    "usher": "R&B",
    # Melodic Trap. Future is exact-clause only (the word shows up in other styles).
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
    # Rage/Opium
    "sofaygo": "Rage/Opium",
    "so faygo": "Rage/Opium",
    "che": "Rage/Opium",
    "osamason": "Rage/Opium",
    "osama son": "Rage/Opium",
    "kai angel": "Rage/Opium",
    "destroy lonely": "Rage/Opium",
    "ken carson": "Rage/Opium",
    "homixide gang": "Rage/Opium",
    "yeat": "Rage/Opium",
    # Plugg/Pluggnb
    "summrs": "Plugg/Pluggnb",
    "autumn": "Plugg/Pluggnb",
    "autumn!": "Plugg/Pluggnb",
    "xavier sobased": "Plugg/Pluggnb",
    "xaviersobased": "Plugg/Pluggnb",
    "nettspend": "Plugg/Pluggnb",
    # Drill. Chief Keef is intentionally absent: only the word "drill" moves him.
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
    "pop smoke": "Drill",
    "central cee": "Drill",
    # Trap via artist only. The bare word "trap" is not an alias and not a phrase.
    "kodak black": "Trap",
    "kodak": "Trap",
    "dababy": "Trap",
    "da baby": "Trap",
    "key glock": "Trap",
    "g herbo": "Trap",
    "21 savage": "Trap",
    "nardo wick": "Trap",
    "moneybagg yo": "Trap",
    "moneybagg": "Trap",
    "young dolph": "Trap",
    "pooh shiesty": "Trap",
    "est gee": "Trap",
    "sauce walka": "Trap",
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
}

# These aliases match only when the whole artist clause is that name.
EXACT_ONLY = frozenset({
    "future",
    "che",
    "usher",
    "miguel",
    "autumn",
    "nav",
    "pnd",
    "kodak",
    "fivio",
    "peezy",
    "veeze",
})

# Specific before broad. Hip-Hop is last. Bare "trap" is not here.
# (regex, genre). First hit wins.
PHRASES: list[tuple[str, str]] = [
    (r"\btrap\s*soul\b", "R&B"),
    (r"\btrapsoul\b", "R&B"),
    (r"\brn\s*&\s*b\b", "R&B"),
    (r"\br\s*&\s*b\b", "R&B"),
    (r"\brnb\b", "R&B"),
    (r"\bemo\s+trap\b", "Melodic Trap"),
    (r"\bguitar\s+type\s+beats?\b", "Melodic Trap"),
    (r"\bpop\s+smoke\b", "Drill"),
    (r"\bcentral\s+cee\b", "Drill"),
    (r"\b(?:uk|ny)\s+drill\b", "Drill"),
    (r"\bdrill\s+uk\b", "Drill"),
    (r"\bdrill\b", "Drill"),
    (r"\bken\s+carson\b", "Rage/Opium"),
    (r"\bf1lthy\b", "Rage/Opium"),
    (r"\bhyperpop\b", "Rage/Opium"),
    (r"\bopium\b", "Rage/Opium"),
    (r"\brage\b", "Rage/Opium"),
    (r"\bcarti\b", "Rage/Opium"),
    (r"\byeat\b", "Rage/Opium"),
    (r"\bpluggnb\b", "Plugg/Pluggnb"),
    (r"\bplugg\b", "Plugg/Pluggnb"),
    (r"\bmexikodro\b", "Plugg/Pluggnb"),
    (r"\bstoopidxool\b", "Plugg/Pluggnb"),
    (r"\bneopop\b", "Plugg/Pluggnb"),
    (r"\bcashcache\b", "Plugg/Pluggnb"),
    (r"\bsigilkore\b", "Experimental/Glitch"),
    (r"\bhexxed\b", "Experimental/Glitch"),
    (r"\bglitchcore\b", "Experimental/Glitch"),
    (r"\bwebcore\b", "Experimental/Glitch"),
    (r"\bscenecore\b", "Experimental/Glitch"),
    (r"\bbladee\b", "Experimental/Glitch"),
    (r"\bexperimental\b", "Experimental/Glitch"),
    (r"\bdrain\b", "Experimental/Glitch"),
    (r"\bcloud\s+rap\b", "Ambient/Cloud"),
    (r"\bclams\s+casino\b", "Ambient/Cloud"),
    (r"\bethereal\b", "Ambient/Cloud"),
    (r"\bspacey\b", "Ambient/Cloud"),
    (r"\bambient\b", "Ambient/Cloud"),
    (r"\bjersey\b", "Jersey Club"),
    (r"\bgrime\b", "Grime"),
    (r"\buk\s+garage\b", "UK Garage"),
    (r"\bafro\s*swing\b", "Afroswing"),
    (r"\broad\s+rap\b", "Road Rap"),
    (r"\bboom\s*bap\b", "Boom Bap/Old School"),
    (r"\bold\s+school\b", "Boom Bap/Old School"),
    (r"\beast\s+coast\b", "Boom Bap/Old School"),
    (r"\blo[\s-]*fi\b", "Boom Bap/Old School"),
    (r"\b90s\b", "Boom Bap/Old School"),
    (r"\bevilgiane\b", "Dark/Aggressive"),
    (r"\bcity\s+morgue\b", "Dark/Aggressive"),
    (r"\bzillakami\b", "Dark/Aggressive"),
    (r"\bthraxx\b", "Dark/Aggressive"),
    (r"\bhardcore\b", "Dark/Aggressive"),
    (r"\bdark\b", "Dark/Aggressive"),
    (r"\bdetroit\b", "Detroit"),
    (r"\bmelodic\b", "Melodic Trap"),
    (r"\bjazzy\b", "Jazz"),
    (r"\bjazz\b", "Jazz"),
    (r"\bchillhop\b", "Chill"),
    (r"\bchill\b", "Chill"),
    (r"\bpop\s*/\s*hip[\s-]*hop\b", "Hip-Hop"),
    (r"\bpop\s+hip[\s-]*hop\b", "Hip-Hop"),
    (r"\bhip[\s-]*hop\b", "Hip-Hop"),
]

PHRASE_RES = [(re.compile(p), g) for p, g in PHRASES]

QUOTE_RES = (
    re.compile(r'"[^"]*"'),
    re.compile(r"“[^”]*”"),
    re.compile(r"«[^»]*»"),
    re.compile(r"''[^']*''"),
)

SKIP_RE = re.compile(r"\bhow to make\b|\btutorials?\b|\bcompilations?\b")
HER_RE = re.compile(r"\bh\.e\.r\.?\b")
SPLIT_RE = re.compile(
    r"\s+(?:x|feat\.?|ft\.?|vs\.?|and)\s+|[×+]|(?:\s*[&/]\s*)",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
TYPEBEAT_RE = re.compile(r"\btype\s*beats?\b")
PROD_TAIL_RE = re.compile(
    r"(?:\((?:prod|produced)[^)]*\)|\b(?:prod|produced)\.?\s*by\b.*$|\|\s*(?:prod|produced)\b.*$)",
    re.IGNORECASE,
)

FILLER = frozenset({
    "type", "beat", "beats", "free", "prod", "produced", "instrumental",
    "instrumentals", "for", "profit", "non", "not", "sold", "exclusive",
    "untagged", "tagged", "official", "full", "download", "link", "description",
    "bpm", "hook", "sample", "loop", "hard", "soft", "sad", "new", "old", "hot",
    "cold", "fast", "slow", "best", "real", "raw", "dirty", "clean", "night",
    "day",     "with", "w", "vol", "volume", "pt", "part", "remix", "inst", "by",
    "made", "fl", "studio", "of", "to", "my", "your", "our",
    "in", "on", "at", "from", "this", "that", "it", "its", "is", "am", "are",
    "and", "or", "but", "plus", "ft", "feat", "vs", "radio", "edit", "version",
    "available", "youtube", "copyright", "commercial", "use", "lease", "mp3",
    "wav", "stems", "untagged", "tagged", "loop", "kit", "preset", "midi",
    "freestyle", "rap", "trap", "upbeat", "slowed", "reverb", "sped", "up",
    "nightcore", "instrumental", "instru", "piste", "gratuit", "gratuite",
    "free", "profit", "nonprofit", "np", "ffp", "f4p", "lease", "exclusive",
    "club", "banger", "viral", "hard", "aggressive", "emotional", "smooth",
    "guitar", "piano", "808", "808s", "bpm", "amin", "cmin", "dmin",
    "emin", "fmin", "gmin", "bmin", "major", "minor", "prod", "producer",
    "beats", "beat", "typebeat", "type", "2020", "2021", "2022", "2023",
    "2024", "2025", "2026", "2027",
})

_ALIAS: dict[tuple[str, ...], str] = {}
_ALIAS_SQUEEZE: set[str] = set()
MAX_ALIAS_LEN = 1


def _alias_tokens(alias: str) -> tuple[str, ...]:
    text = alias.lower().replace("$", "s").replace("é", "e").replace("!", "")
    return tuple(TOKEN_RE.findall(text))


def _build_alias_index() -> None:
    global MAX_ALIAS_LEN
    for alias, genre in ARTIST_GENRE.items():
        parts = _alias_tokens(alias)
        if not parts:
            continue
        _ALIAS[parts] = genre
        if len(parts) > 1:
            _ALIAS[("".join(parts),)] = genre
        _ALIAS_SQUEEZE.add("".join(parts))
        MAX_ALIAS_LEN = max(MAX_ALIAS_LEN, len(parts))


_build_alias_index()


def strip_quotes(title: str) -> str:
    s = title
    prev = None
    while prev != s:
        prev = s
        for cre in QUOTE_RES:
            s = cre.sub(" ", s)
    return s


def phrase_genre(text: str) -> str | None:
    if SKIP_RE.search(text):
        return None
    for cre, genre in PHRASE_RES:
        if cre.search(text):
            return genre
    return None


def _clause_genres(clause: str) -> set[str]:
    found: set[str] = set()
    if HER_RE.search(clause):
        found.add("R&B")
    raw = YEAR_RE.sub(" ", clause)
    raw = TYPEBEAT_RE.sub(" ", raw)
    tokens = [t for t in TOKEN_RE.findall(raw) if t not in FILLER]
    if not tokens:
        return found
    i = 0
    while i < len(tokens):
        matched = False
        upper = min(MAX_ALIAS_LEN, len(tokens) - i)
        for length in range(upper, 0, -1):
            window = tuple(tokens[i : i + length])
            genre = _ALIAS.get(window)
            if genre is None:
                continue
            if length == 1 and window[0] in EXACT_ONLY and tuple(tokens) != window:
                continue
            found.add(genre)
            i += length
            matched = True
            break
        if not matched:
            i += 1
    return found


def artist_genre(text: str, channel: str | None) -> tuple[str | None, list[str]]:
    """Return (genre or None, unknown tokens)."""
    if SKIP_RE.search(text):
        return None, []
    work = text
    if channel:
        ch = channel.lower().strip()
        squeezed = "".join(TOKEN_RE.findall(ch.replace("$", "s")))
        if ch and squeezed not in _ALIAS_SQUEEZE and len(squeezed) >= 4:
            work = work.replace(ch, " ")
    work = PROD_TAIL_RE.sub(" ", work)
    work = TYPEBEAT_RE.sub(" ", work)
    work = re.sub(r"[\[\]\(\)\{\}*_]+", " ", work)
    found: set[str] = set()
    unknown: list[str] = []
    for clause in SPLIT_RE.split(work):
        clause = clause.strip(" -|~:.")
        if not clause:
            continue
        genres = _clause_genres(clause)
        found |= genres
        if genres:
            continue
        raw = YEAR_RE.sub(" ", clause.lower())
        raw = TYPEBEAT_RE.sub(" ", raw)
        for tok in TOKEN_RE.findall(raw):
            if tok in FILLER or tok.isdigit() or len(tok) < 3 or not tok.isalpha():
                continue
            if (tok,) in _ALIAS or tok in _ALIAS_SQUEEZE:
                continue
            unknown.append(tok)
    if len(found) == 1:
        return next(iter(found)), unknown
    return None, unknown


def classify(title: str | None, channel: str | None) -> tuple[str | None, list[str]]:
    if not title:
        return None, []
    text = strip_quotes(title).lower()
    if SKIP_RE.search(text):
        return None, []
    genre = phrase_genre(text)
    if genre:
        return genre, []
    return artist_genre(text, channel)


def _self_check() -> None:
    cases = [
        ('[FREE] Lil Baby Type Beat - "No Hope"', "", "Melodic Trap"),
        ('(FREE) R&B Type Beat - "Last Kiss"', "", "R&B"),
        ("Rnb Type Beat | R&B Type Beat", "", "R&B"),
        ('*CLUB BANGER* Detroit Type Beat "Caught A Charge"', "", "Detroit"),
        ('(FREE) Melodic Type Beat- "Friends"', "", "Melodic Trap"),
        ('Chill Type Beat "Rooms"', "", "Chill"),
        ('lo-fi type beat "rain"', "", "Boom Bap/Old School"),
        ("lofi boom bap type beat", "", "Boom Bap/Old School"),
        ("chill type beat", "", "Chill"),
        ('Jazz Type Beat "u"', "", "Jazz"),
        ('Upbeat Hip-hop Instrumental "Still Me"', "", "Hip-Hop"),
        ("Pop / Hip Hop Type Beat", "", "Hip-Hop"),
        ("Melodic Hip-Hop Type Beat", "", "Melodic Trap"),
        ("R&B Hip Hop Type Beat", "", "R&B"),
        ('Drill Type Beat "x"', "", "Drill"),
        ('trap type beat "hood"', "", None),
        ("How To Make A Skillibeng Type Beat | FL Studio Tutorial", "", None),
        ('[FREE] Kodak Black Type Beat "x"', "", "Trap"),
        ('Kodak Black Dark Type Beat "x"', "", "Dark/Aggressive"),
        ('[FREE] DaBaby Type Beat "x"', "", "Trap"),
        ("(FREE) Chief Keef Type beat", "", None),
        ('Chief Keef Drill Type Beat «Hood»', "", "Drill"),
        ("[FREE] Veeze Type Beat - “Trifling”", "", "Detroit"),
        ('[FREE] Gunna x Young Thug Type Beat "Turnstile"', "", "Melodic Trap"),
        ('[FREE] Future x 21Savage type beat - "Molotov"', "", None),
        ('Future Type Beat "Price Tags"', "", "Melodic Trap"),
        ("future bass type beat", "", None),
        ("free destroy lonely type beat", "", "Rage/Opium"),
        ("(FREE) Summer Walker Type Beat - \"Away\"", "", "R&B"),
        ('Che Type Beat "x"', "", "Rage/Opium"),
        ('Summrs x Autumn! Type Beat "x"', "", "Plugg/Pluggnb"),
        ('Che x Summrs Type Beat "x"', "", None),
        ('"R&B" Trap Type Beat', "", None),
        ('Lil Durk Type Beat "Seen It All"', "", "Drill"),
        ("Don Toliver Type Beat", "", "Melodic Trap"),
        ("Yeat Type Beat", "", "Rage/Opium"),
        ("guitar type beat", "", "Melodic Trap"),
        ("emo trap type beat", "", "Melodic Trap"),
        ("trap soul type beat", "", "R&B"),
        ("jersey club type beat", "", "Jersey Club"),
        ("uk garage type beat", "", "UK Garage"),
        ("grime type beat", "", "Grime"),
        ("afroswing type beat", "", "Afroswing"),
        ("road rap type beat", "", "Road Rap"),
        ("pluggnb type beat", "", "Plugg/Pluggnb"),
        ("rage type beat", "", "Rage/Opium"),
        ("ambient type beat", "", "Ambient/Cloud"),
        ("experimental type beat", "", "Experimental/Glitch"),
        ("dark type beat", "", "Dark/Aggressive"),
        ("Pop Smoke Type Beat", "", "Drill"),
        ("Babytron Type Beat", "", "Detroit"),
        ("21 Savage x Key Glock Type Beat", "", "Trap"),
        ("G Herbo x Veeze Type Beat", "", None),
        ("type beat compilation vol 3", "", None),
        ("H.E.R. Type Beat", "", "R&B"),
        ("The Weeknd Type Beat", "", "R&B"),
        ("chill lofi type beat", "", "Boom Bap/Old School"),
        ('Happy x Macklemore Type Beat "Still Me" | Upbeat Hip-hop', "", "Hip-Hop"),
    ]
    failed = 0
    for title, channel, expected in cases:
        got, _ = classify(title, channel)
        if got != expected:
            failed += 1
            print(f"FAIL {title!r} -> {got!r} expected {expected!r}")
    if failed:
        raise SystemExit(f"{failed} classifier checks failed")
    print(f"classifier checks ok ({len(cases)})")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    conn.execute("PRAGMA busy_timeout=120000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-262144")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def _flush(conn: sqlite3.Connection, pending: list[tuple[str, str]], counts: Counter) -> None:
    if not pending:
        return
    conn.executemany(
        "UPDATE beats SET genre = ? WHERE video_id = ? AND genre = 'Underground'",
        pending,
    )
    conn.commit()
    pending.clear()


def run() -> None:
    _self_check()
    read = _connect()
    write = _connect()
    plan = read.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT video_id, title, channel_name
        FROM beats INDEXED BY idx_beats_genre_views
        WHERE genre = 'Underground'
        """
    ).fetchall()
    print("query plan:", "; ".join(str(r[3]) for r in plan), flush=True)

    counts: Counter[str] = Counter()
    unknown_tokens: Counter[str] = Counter()
    pending: list[tuple[str, str]] = []
    scanned = 0
    moved = 0
    started = time.time()
    try:
        # One index scan. A separate write connection commits every few thousand
        # so the reader snapshot does not restart the scan.
        cur = read.execute(
            """
            SELECT video_id, title, channel_name
            FROM beats INDEXED BY idx_beats_genre_views
            WHERE genre = 'Underground'
            """
        )
        while True:
            rows = cur.fetchmany(READ_BATCH)
            if not rows:
                break
            for video_id, title, channel in rows:
                scanned += 1
                genre, unknown = classify(title, channel)
                if genre:
                    pending.append((genre, video_id))
                    counts[genre] += 1
                    moved += 1
                    if len(pending) >= BATCH:
                        _flush(write, pending, counts)
                elif unknown:
                    unknown_tokens.update(unknown)
            if scanned % 200000 < READ_BATCH:
                elapsed = time.time() - started
                rate = scanned / elapsed if elapsed else 0
                print(
                    f"scanned {scanned:,} moved {moved:,} "
                    f"({rate:,.0f} rows/s)",
                    flush=True,
                )
        _flush(write, pending, counts)
        remaining = write.execute(
            "SELECT COUNT(*) FROM beats WHERE genre = 'Underground'"
        ).fetchone()[0]
    finally:
        read.close()
        write.close()

    elapsed = time.time() - started
    print(f"done in {elapsed:,.0f}s  scanned {scanned:,}  moved {moved:,}")
    print("moved per genre:")
    for genre, n in counts.most_common():
        print(f"  {genre}: {n:,}")
    print(f"Underground remaining: {remaining:,}")
    top = [tok for tok, _n in unknown_tokens.most_common(12)]
    if top:
        shown = ", ".join(top)
        print(
            "A later Jev pass could classify frequent unknown artist tokens "
            f"such as {shown}, mapping each token to a genre instead of rescoring rows."
        )
    else:
        print(
            "A later Jev pass could classify frequent unknown artist tokens "
            "that never matched this lexicon, mapping each token to a genre instead of rescoring rows."
        )


if __name__ == "__main__":
    run()
