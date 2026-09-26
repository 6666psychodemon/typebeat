# TypeBeat — Product Requirements Document (v2)

**Version:** 2.0  
**Date:** August 2026  
**Status:** Living product doc  
**Supersedes:** PRD.md (v1) as the product vision; v1 remains the technical seed / current prototype baseline

---

## 1. Overview / Vision

TypeBeat is evolving from a local YouTube type-beat scraper and Streamlit catalog into an underground type-beat **radio + catalog + producer economy + cultural connector** platform.

The product is for people who dig for gems — freestyle-ready instrumentals with low views, clear licensing signals (free / free-for-profit), and a listening experience that feels like radio, not a spreadsheet of links. Over time it should also give producers rotation and platform cred, and position TypeBeat as a connector between rappers, producers, and labels — with a founder narrative of being “anonifamous”: known for the network and culture, not the face.

**One-liner:** Continuous underground type-beat radio backed by a filterable gem catalog, with a path toward producer economy and industry connection.

---

## 2. Problem

YouTube’s algorithm and search bury underground type beats. Artists and listeners who want freestyle fuel or commercial-ready instrumentals face:

- **Discovery friction** — Manual digging across channels is slow; “type beat” search surfaces the same high-view tracks.
- **No continuous listen mode** — Catalog browsing is stop-start; there is no radio-like flow with genre control, favorites, or “more like this.”
- **Weak underground signal** — Low views are often the gem marker, but platforms optimize for popularity, not obscurity.
- **Producer invisibility** — Newer or smaller producers lack rotation, credibility, and a fair path to sell packs or get heard.
- **Fragmented culture** — Rappers, producers, and labels lack a shared underground hub that is positive for UG culture rather than extractive.

TypeBeat exists to make underground discovery easier, listening continuous, and producers part of an economy — not just scraped rows in a DB.

---

## 3. Goals

### Product goals

1. **Radio-first listening** — Continuous play with genre control, favorites, producer deep-dives, similarity (“hear more like this”), playlists, dislike, loop, and volume leveling via audio compression.
2. **Catalog as discovery engine** — Filterable beat DB (genre, keywords, view ranges, free / free-for-profit, year); treat low views as an underground signal.
3. **Producer economy (near-term seed → growth)** — Latest-beat rotation on radio, platform cred, and a path to sample-pack buy/sell and producer pages/tiers.
4. **Connector role** — Link rappers, producers, and labels; reinforce positive UG culture; founder as cultural connector.

### Non-goals (for MVP clarity)

- Replacing YouTube as the audio host (MVP may still stream via YouTube / existing sources).
- Full music-industry suite (A&R CRM, contracts, label ops) at launch.
- Serving threat actors (scrapers-for-sale, model trainers, predatory middlemen) as customers — see Security & ethics.

---

## 4. Personas & Jobs-to-Be-Done

Threat actors (hacker, data buyer, MusicAI CXO, industry shark) are **not** served personas. They appear under Security & ethics as risks.

### Listener

- **Wants:** Endless freestyle radio; dig for gems without YouTube spam; control genre and vibes; save favorites; skip what they dislike; consistent volume.
- **JTBD:** When I’m freestyling or working, I want continuous underground type beats so I stay in flow without hunting links.

### Producer

- **Wants:** Rotation for latest beats; platform cred; discovery without paying for ads; later — tiers, pages, sample pack sales.
- **JTBD:** When I drop a type beat, I want it heard by rappers who dig underground so I build reputation and opportunity without chasing algorithms alone.

### Rapper

- **Wants:** Free / free-for-profit gems; filters that match their lane; “more from this producer”; playlists for sessions; commercial clarity when needed.
- **JTBD:** When I need a beat for a freestyle or release, I want underground instrumentals I can actually use so I don’t waste sessions on overplayed or unclear-license tracks.

### Label boss

- **Wants:** Talent and beat signal; connector intro path; cultural authenticity without looking like a tourist.
- **JTBD:** When I’m scouting UG talent and sounds, I want a credible underground surface so I can connect without cold-DMing random YouTube channels.

### Founder (operator / connector)

- **Wants:** Platform that shapes positive UG culture; “anonifamous” connector status; sustainable model without selling out the culture.
- **JTBD:** When I’m building TypeBeat, I want radio + catalog + economy + connection so the product is culturally useful and defensible, not just a glorified playlist.

---

## 5. Product Pillars / Features

### 5.1 Radio experience

Continuous listening layer on top of the catalog.

| Capability | Intent |
| --- | --- |
| Continuous radio | Uninterrupted play for freestyle / work sessions |
| Genre control | Steer the station without breaking flow |
| Favorites | Save gems for later sessions |
| More from producer | Dive into a channel after a hit |
| Hear more like this | Similarity / vibe adjacency |
| Playlists | Curated or user-built session sets |
| Dislike | Negative signal to shape rotation |
| Loop | Repeat a beat for freestyle / writing |
| Audio compression | Level loudness across tracks so volume stays usable |

**MVP emphasis:** continuous play, genre control, favorites, more from producer, dislike, loop, compression. Similarity and rich playlists can deepen in Growth.

### 5.2 Catalog / discovery

Filterable beat database; low views as underground signal.

| Filter / signal | Intent |
| --- | --- |
| Genre | Lane / style browsing |
| Keywords | Title / style / producer text search |
| View ranges | Explicit underground bias (e.g. max views) |
| Free / free-for-profit | Licensing clarity for personal vs commercial |
| Year | Freshness vs archive |

Catalog is the source of truth for radio queues and discovery. UX should feel diggable, not spreadsheet-only (v1 is table-first; v2 targets radio + richer browse).

### 5.3 Producer economy

| Capability | Horizon |
| --- | --- |
| Radio rotation for latest beats | MVP / early |
| Platform cred (visibility, trust signals) | MVP seed → Growth |
| Producer pages & tiers | Growth |
| Sample pack buy/sell marketplace | Growth |

Producers should feel the platform works *for* them: rotation, attribution, and a path to monetize packs without the product becoming extractive middleman theater.

### 5.4 Connector role

- Surface paths between rappers, producers, and labels.
- Influence UG culture positively (respect for creators, clear licensing, anti-scam norms).
- Founder narrative: connector / “anonifamous” — reputation through the network and gems, not personal celebrity.

Exact product surfaces (intros, profiles, trust badges, events) remain partly open; the pillar is directional for roadmap and positioning.

---

## 6. Current Prototype (v1 Seed)

The following is the **current / seed implementation** from PRD v1. v2 builds on it; it is not the end state.

### Stack

| Layer | Choice |
| --- | --- |
| Frontend / UI | Streamlit (`app.py`) |
| Database | SQLite (`typebeats.db`) |
| Scraping | Python + `scrapetube` (`scraper.py`) |
| Processing | `pandas`, `re` (title parsing) |
| Environment | Python `venv` |

**Architecture pattern:** Decoupled. Scraper updates the local DB independently. Frontend is **read-only** against the DB (fast loads; avoids live-scrape bans).

### Scraper workflow (`scraper.py`)

- Iterates search queries (e.g. `"yeat type beat"`, `"lucki type beat"`).
- Date filtering via YouTube operators (e.g. `after:YYYY-MM-DD`).
- Sort by `upload_date` for chronological scraping.
- Stealth: `time.sleep(random.uniform(0.3, 0.8))`; limits per keyword.

### Title parsing

- Anchor on `"type beat"` (case-insensitive); reject titles without it.
- Artist style = left side, cleaned (strip `[]`/`()`, marketing fluff like FREE / PROD BY / HARD / DARK / GUITAR, dashes/pipes).
- Result stored in `artist_style`.

### `beats` table shape

| Column | Type | Notes |
| --- | --- | --- |
| `video_id` | TEXT PK | Dedup via `INSERT OR IGNORE` |
| `title` | TEXT | Raw title |
| `artist_style` | TEXT | Parsed style |
| `channel_name` | TEXT | Producer / channel |
| `url` | TEXT | YouTube watch URL |
| `views` | INTEGER | Filterable |
| `upload_time_raw` | TEXT | e.g. “3 days ago” |
| `scraped_at` | TIMESTAMP | Ingest time |

Initialized via `db_setup.py`.

### Streamlit UI (read-only)

- `@st.cache_data` for SQLite queries.
- Default sort: views ascending (underground-first).
- Filters: global text search (`title`, `artist_style`, `channel_name`); max-views slider.
- `st.dataframe` + clickable Listen links via `LinkColumn`.

### Deploy notes (current)

- Target: Streamlit Community Cloud via GitHub.
- SQLite `.db` shipped in the repo with the code.

### Workflow

1. `python3 scraper.py` — ingest  
2. `streamlit run app.py` — browse  

v2 technical direction (Section 11) may outgrow Streamlit, in-repo SQLite, and table-only UX while keeping this pipeline as the seed data path where useful.

---

## 7. Out of Scope / Deferred

Deferred to Growth (or later) unless explicitly pulled into MVP:

- Algorithmic recommendations beyond simple filters / “more from producer”
- Full producer pages and subscription tiers
- Sample pack marketplace (buy/sell)
- Tinder / duel-style beat comparison UX
- Stream compare / comment social layer
- Rich metadata enrichment (key, BPM, drop timing, length — see Open questions)
- Advanced audio FX beyond compression / leveling
- Own branded audio hosting (if still on YouTube embeds / links)
- Full label CRM / deal flow tooling
- Multi-platform official apps beyond web MVP

Unresolved product bets (paid vs free, open source, etc.) are listed in Open questions — they are not decided by omission here.

---

## 8. Open Questions

Documented as **unresolved**. Do not treat as decided until explicitly closed.

### Product

- **Paid vs free** — Freemium? Radio free / catalog paid? Commercial radio tier?
- **Open source** — Fully open, open core, or closed?
- **Retention bet** — Which hypothesis we double down on (see Section 12).
- **How to justify paid radio** beyond a glorified playlist — candidates: better filters, compression / leveling, no ads, curation quality, commercial licensing clarity.

### Ethics & culture

- **Ethics of monetizing predominantly Black culture** — What model is respectful and non-extractive? Who captures value?

### UX

- **UI style** — Glass / minimal / maximal dark + accents / rap-visual language — undecided.
- **Catalog columns** — What to show vs hide in browse vs detail.

### Data

- **DB organization** — Schema evolution beyond v1 `beats`; producers, favorites, playlists, licensing flags.
- **Update cadence** — How often scrape / refresh rotation.
- **Vocals layer** — Acapellas / vocal tags / “with hooks” vs pure instrumentals.
- **Beat metadata** — Drop timing, key, length, BPM — scrape, user-tag, or infer?
- **DB location** — Remain in-repo SQLite vs hosted DB / object storage for audio metadata.

### Tech & distribution

- **Own domain** — When and under what brand.
- **Protection strategy** — Against scrapers, bulk data buyers, model trainers, clone apps (see Security & ethics).

---

## 9. Security & Ethics

### Risks (threat actors — not customers)

| Actor | Risk |
| --- | --- |
| Hacker | Account takeover, DB dump, abuse of scrape pipeline |
| Data buyer | Bulk export of catalog for resale or closed competing products |
| MusicAI CXO / model trainers | Training on UG catalog without creator consent or compensation |
| Industry shark | Predatory deals, culture washing, extractive “partnerships” |

### Principles (directional)

- Do not optimize product for bulk data extraction.
- Prefer creator-respecting licensing signals (free vs free-for-profit) over gray-area usage.
- Monetization models must be examined against cultural ethics (Open questions) before lock-in.
- Connector positioning should favor fair intros and positive UG norms, not gatekeeping theater.
- Protection strategy (rate limits, ToS, API posture, watermarking metadata, legal) remains an open tech decision but is a first-class concern before scale.

---

## 10. Technical Direction

**Evolve from the Streamlit seed; end-state stack is not fully decided.**

### Near term (build on v1)

- Keep scraper → SQLite → read-oriented app loop until radio MVP needs dictate otherwise.
- Extend schema carefully for licensing flags, favorites, dislike, playlists, producer rotation queues.
- Audio compression / leveling may require a player stack beyond Streamlit’s native widgets — evaluate embed + client DSP vs re-encoding pipeline.
- Preserve duplicate handling via `video_id` + `INSERT OR IGNORE`.

### Likely pressure points (unknowns)

- Streamlit limits for true continuous radio UX, auth, and marketplace.
- In-repo SQLite + Streamlit Cloud for multi-user writes, favorites, and economy features.
- Scrape ToS / IP risk as cadence and scale increase.
- Domain, hosting, and CDN if moving off Community Cloud.
- Recommendation / similarity features need embeddings or rules — not in v1.

Decisions here should close Open questions (DB location, protection, domain) rather than silently rewriting the seed.

---

## 11. Success / Retention Hypotheses

These are **open hypotheses**, not proven KPIs yet.

| Hypothesis | Mechanism |
| --- | --- |
| Huge catalog | More gems → higher chance of “this is the one” → return visits |
| Easier manual discovery | Filters + underground view bias reduce hunt time vs raw YouTube |
| Free radio for personal use | Habit loop for freestyle / daily listen without paywall friction |
| Royalty-free radio for commercial use | Clear commercial path → retention for rappers / releases |

Secondary signals to watch later: session length (radio), favorites saved, producer repeat listens, return rate after first gem, % of plays from low-view band.

Exact north-star metric TBD once paid/free and retention bet are chosen.

---

## 12. Roadmap

Lightly prioritized buckets. Order within buckets is indicative, not a sprint plan.

### P0 — Product decisions

Close or time-box:

- Paid vs free (and justification for paid radio)
- Retention bet
- Open source posture
- Ethics / monetization stance
- UI direction
- Domain + DB location + protection strategy (high-level)

### MVP — Radio + catalog core

- Continuous radio with genre control
- Favorites, more from producer, dislike, loop
- Audio compression / volume leveling
- Catalog filters: genre, keywords, view ranges, free / free-for-profit, year
- Producer rotation for latest beats (cred seed)
- Build on v1 scraper + SQLite seed; evolve UI beyond table-only as needed

### Growth

- Algo / “hear more like this” recommendations
- Producer pages and tiers
- Sample pack marketplace
- Tinder / duel comparison UX
- Stream compare / comment
- Metadata enrichment (key, length, drop, etc.)
- Audio FX beyond compression
- Stronger connector surfaces (rapper ↔ producer ↔ label)

### Tech & security

- Stack evolution off Streamlit seed when blocked
- Auth, user data, write path for favorites / playlists
- Anti-abuse, anti-bulk-scrape, data protection
- Scrape reliability, cadence, and compliance posture
- Hosting / domain / DB migration as decided in P0

### Marketing

Channels to develop presence (timing TBD post-MVP usefulness):

- Twitch, Kick  
- TikTok, YouTube, Instagram  
- Reddit, Threads, X  

Positioning: underground gems, freestyle radio, producer rotation, cultural connector — not “another beat search clone.”

---

## Document control

| Field | Value |
| --- | --- |
| Living doc | Yes — update when decisions close or MVP scope shifts |
| v1 reference | `PRD.md` — technical prototype baseline |
| This file | `PRD_v2.md` — product vision and roadmap |
