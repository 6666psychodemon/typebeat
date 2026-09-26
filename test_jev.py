"""Evaluate three TypeBeat listings with Jev.

Each track is one System One call. The three questions share that state and
run in parallel inside the call.
"""

from __future__ import annotations

import os
from pathlib import Path

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

# Jev Score levels are 0-indexed. Five descriptions map raw scores 0..4 onto
# a 1..5 metadata rating via `raw + 1`.
METADATA_QUALITY_LEVELS = [
    "1 — unusable: title, channel, or description is missing or contradicts the others",
    "2 — weak: a title exists, but the channel or description adds almost nothing",
    "3 — adequate: title and channel identify a type beat; the description is generic or very short",
    "4 — good: title, channel, and description agree and name the style or featured artists",
    "5 — excellent: a specific type-beat title, a real channel, and a description with usage terms or musical details",
]

QUESTIONS = {
    "subgenre": Choice(
        instructions=(
            "Which subgenre best fits this TypeBeat listing, using `title`, "
            "`channel`, and `description`?"
        ),
        criteria={
            "plugg_rage": (
                "Plugg, pluggnb, rage, or opium-style trap "
                "(Playboi Carti, Yeat, Ken Carson, Summrs, and similar)."
            ),
            "boom_bap": "Boom bap, 90s, old school, or lo-fi east-coast hip-hop.",
            "dark_trap": "Dark, aggressive, horror, or phonk-adjacent trap.",
            "other": "None of those subgenres is the best fit.",
        },
    ),
    "is_single_beat": Noul(
        instructions=(
            "Is this one standalone type beat, rather than a mix, compilation, "
            "playlist, beat tape, or multi-beat pack? Judge `title` and `description`."
        ),
        criteria={
            "true": "A single instrumental uploaded to be used on its own.",
            "false": "A mix, compilation, playlist, beat tape, or pack of more than one beat.",
        },
    ),
    "metadata_quality": Score(
        instructions=(
            "How complete and consistent is this listing for someone looking for a "
            "type beat? Judge `title`, `channel`, and `description` together. "
            "The levels run from 1 (worst) to 5 (best)."
        ),
        criteria=METADATA_QUALITY_LEVELS,
    ),
}

# Titles and channels are real rows from typebeats.db. Descriptions are sample
# listing text; the catalog does not store YouTube descriptions.
SAMPLE_TRACKS = [
    {
        "title": '[FREE FOR PROFIT] YEAT PLUGG x AGGRESSIVE TYPE BEAT "got" (PROD. Andrew Beatz X LUKE!)',
        "channel": "Andrew Beatz",
        "description": (
            "Yeat plugg / rage type beat. Free for profit if you credit Andrew Beatz "
            "in the title. One instrumental, 142 BPM, F# minor. "
            "Tags: yeat, plugg, rage, type beat."
        ),
    },
    {
        "title": '"Fall Back" - 90s OldSchool Type Beat | Underground Hip-Hop Boom Bap Type Beat | Anabolic Beatz',
        "channel": "Anabolic Beatz",
        "description": (
            "90s boom bap instrumental, Joey Bada$$ / Pro Era pocket. "
            "Single beat. Lease and exclusive links in the pinned comment."
        ),
    },
    {
        "title": 'DENZEL CURRY X $UICIDEBOY$ X POUYA TYPE BEAT "CRUEL COMPLEX" | WRONGSIDE BEAT TAPE',
        "channel": "wrongside",
        "description": "beat tape",
    },
]


def load_dotenv(path: Path) -> None:
    """Fill missing environment variables from a local KEY=value file."""
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


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    with TypeSafeClient() as client:
        for track in SAMPLE_TRACKS:
            response = client.system_one(state=track, questions=QUESTIONS)
            subgenre = response.choices["subgenre"]
            single = response.nouls["is_single_beat"]
            quality = response.scores["metadata_quality"]
            rating = quality.score + 1

            print(track["title"])
            print(f"  channel: {track['channel']}")
            print(
                f"  subgenre: {subgenre.choice} "
                f"(confidence {subgenre.confidence:.3f})"
            )
            probs = ", ".join(
                f"{label} {probability:.3f}"
                for label, probability in subgenre.probabilities.items()
            )
            print(f"    probabilities: {probs}")
            print(f"  is_single_beat: {single.noul:.3f}")
            print(
                f"  metadata_quality: {rating:.3f} / 5 "
                f"(raw {quality.score:.3f}, confidence {quality.confidence:.3f})"
            )
            print(
                f"    model {response.model} "
                f"tokens in {response.usage.input_tokens} "
                f"out {response.usage.output_tokens}"
            )
            print()


if __name__ == "__main__":
    main()
