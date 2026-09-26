# typebeat — Product Requirements (v2 draft)

> **Status:** Discussion draft — not locked for implementation.  
> **Sources:** Existing `PRD.md` (tech prototype), current codebase (catalog + radio prototypes), founder backlog (direction).  
> **Goal of this doc:** Align on *what* typebeat is and *who* it’s for before more build. Reply with decisions on the open questions at the end.

---

## What's changed vs old PRD

| Old PRD | This draft |
| --- | --- |
| Product = “Underground Type Beat **Directory**” (search table) | Product = **Radio + Catalog** discovery platform; directory is one surface, not the whole product |
| Success = filter low-view YouTube instrumentals | Success = **connector role** in UG hip-hop / type-beat culture (listeners, rappers, producers, labels) |
| Personas implicit (producers/artists searching) | Explicit personas + JTBD; **adversarial actors called out as threats, not customers** |
| Monetization / ethics / OSS absent | Framed as **open decisions** with pros/cons and an ethics stance |
| Tech-heavy (schema, scraper regex, Cursor workflow) | Product-first; tech only as a sketch. Schema/columns become open questions |
| Deployment = Streamlit Community Cloud + DB in git | Acknowledges Streamlit prototypes + emerging Next `web/`; hosting/protection TBD |
| No retention thesis | Explicit: why people come back (catalog depth, radio ease vs manual YT, free personal use, optional commercial tier) |
| No GTM / risks | Promote sketch + legal/security/cold-start/YouTube/culture risks |

**Already true in the repo (ahead of old PRD):** `radio.py` (filterable continuous radio), free / free-for-profit tagging, genres, large scraped DB, producer harvest lists, early Next app under `web/`. This draft treats those as **working prototypes**, not the finished product.

---

## 1. Product vision & north star

**typebeat** is an underground discovery layer for type beats: a place to **listen**, **filter**, and **connect** without drowning in YouTube’s algorithm, ads, and overplayed catalog filler.

**North star:** Be a **connector** in online hip-hop culture — between rappers and UG producers, between listeners and fresh beats, between “I just want radio” and “I want to dive the free beats ocean.” Stay credible to underground culture; don’t become another extractive beat marketplace wearing a hoodie.

**Founder intent (keep honest):** play connector, connect with people, get a bag, stay **anonifamous**. Product decisions should serve culture *and* a sustainable bag — not culture as cover for a data play.

**One-line pitch (debate this):**  
*Type beat radio + a deep UG catalog — find latest / lowest-view gems, skip the harsh YouTube grind, support producers without selling out the culture.*

---

## 2. Problem / opportunity

### What’s broken today

- **YouTube type beat discovery is painful.** Search → scroll → ads → same mega-channels → “FREE” spam → volume jumps → lose the thread. Manual playlist building is work.
- **Lofi radio nostalgia is real.** People want “put it on and vibe” (work / relax / freestyle) with a twist that still feels like supporting UG culture — not another sterile ambient stream.
- **True underground is hard to prove.** Low views can mean “fresh” or “trash.” Rappers and A&Rs need filters (genre, year, free/FFP, view bands, keywords) plus a way to stumble into gems.
- **Producers need rotation, not just upload-and-pray.** Latest beats should have a path into radio / catalog highlight without paying for playlist spam (long-term; MVP can start with scrape + filters).

### Opportunity

Own the **“type beat radio + searchable free beats ocean”** niche:

1. Continuous radio with genre / free / view filters (ease).
2. Deep catalog for freediving (depth + “true UG” via low-stats filters).
3. Later: producer cred, sample packs, connection layer — without becoming BandLab-with-worse-UX.

---

## 3. Personas & jobs-to-be-done

Prioritize by how much MVP should serve them. **Founder** is a stakeholder, not an end-user persona for features.

### Primary — Listener

**Who:** Anyone putting type beats on for focus, chill, background, or inspiration.

| Priority | Job |
| --- | --- |
| Must | Find latest beats; change genres; continuous listen without babysitting YT |
| Must | Avoid harsh volume jumps (compression / leveling intent) |
| Should | Save favorites; add to own playlist; loop a beat |
| Should | “More like this”; see more from this producer |
| Could | Hate / skip signals that train rotation; explore full catalog with rich filters |

**Emotional job:** Lofi-radio ease + feeling like a supporter of UG culture, with customization.

### Primary — Rapper

**Who:** Freestyles, writes, hunts instrumentals, wants contact with real UG producers.

| Priority | Job |
| --- | --- |
| Must | Freedive free beats ocean; radio randomly surfaces gems |
| Must | Filter by genre / free / low views (“proven underground” as a *signal*, not gospel) |
| Should | Get inspired by latest from lesser-known producers; path to connect |
| Could | Commercial / royalty clarity when using for releases (tiered later) |

### Primary — Producer

**Who:** Uploads type beats, wants plays, cred, maybe pack sales.

| Priority | Job |
| --- | --- |
| Must (later) | Latest beats play / rotate on radio; appear in catalog |
| Should | Build cred on platform; get highlighted / promoted |
| Should | Sell sample packs; buy other producers’ packs |
| Could | Tiers, partnerships, contact paths from rappers/labels |

**MVP honesty:** Today’s scrape-based catalog already *surfaces* producers without onboarding. True producer accounts, claims, and pack commerce are **post-MVP**.

### Secondary — Label boss / A&R

**Who:** Scouts producers and beats for artists.

| Priority | Job |
| --- | --- |
| Must | Pick latest from UG producers; freedive free ocean; radio gem hunting |
| Should | Discover producers worth signing/collabing; buy packs when inspired |
| Could | Saved scouting lists, export, “label” workspace |

### Stakeholder — Founder (“me”)

| Job | Product implication |
| --- | --- |
| Connector in online hip-hop | Features that create *paths between people*, not only playlists |
| Connect with people | Community / identity light at first; don’t fake Discord-scale social |
| Get a bag | Monetization that can be justified (see §6–7) |
| Anonifamous | Brand/voice can stay low-ego; product doesn’t need founder face |

---

### Threat models — NOT customers

These appear in the backlog as “WANT TO.” Treat them as **adversaries / ethics red lines**, never as paid segments.

| Actor | Intent | Product stance |
| --- | --- | --- |
| Industry shark / MusicAI CXO / data buyer | Buy user DB and/or beat DB | **Do not sell.** No bulk user or catalog dumps as a business line |
| Hacker | Steal beat DB, capture tech, extort | Security, least-privilege, no naive “DB in public git forever” for prod |

If someone wants API access later: **controlled, rate-limited, producer-permissioned**, never “here’s the whole UG graph.”

---

## 4. Core product surfaces

```text
                    ┌─────────────────────┐
                    │     typebeat        │
                    │  (connector layer)  │
                    └─────────┬───────────┘
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         RADIO (MVP)    CATALOG (MVP)    FUTURE SURFACES
         continuous     search/filter    producer pages
         genre/free     freedive ocean   listener pages
         rotation       low-view UG      sample packs
                                         tiers / partnerships
                                         tinder / duel
```

### Radio — MVP spine

**Promise:** Put on station → filter (genre, free, FFP, view cap) → long buffer → vibe / freestyle / work.

**Listener wants (backlog → product language):**

- Latest + rotation (not only random forever — **open: mix “new” vs “random UG”**)
- Change genres; favs (maybe per-genre); more from producer; more like this
- Own playlists; hate-this; loop; compression against harsh jumps
- Path to producer inspiration → packs (later)

**Producer wants:** latest in play + rotation; packs; cred.

### Catalog — MVP co-spine

**Promise:** Freedive the ocean. Filters that YouTube search doesn’t give you cleanly.

**Must filters (listener):** genres, keywords, view ranges (fixed bands), free / free-for-profit, year.

**Sort/discovery thesis:** low views as *underground signal* + recency — not “lowest views always wins.”

### Future surfaces (explicitly later)

| Surface | Intent | Why later |
| --- | --- | --- |
| Producer page | Cred, discography, contact, packs | Needs identity / claim model |
| Listener page | Favs, playlists, history | Needs accounts |
| Producer / listener tiers | Monetization + status | Needs ethics + pricing decisions |
| Individual partnerships | Curated deals | Ops-heavy |
| Sample pack marketplace | Producer ↔ everyone commerce | Trust, payments, rights |
| Tinder for typebeat | Swipe discover | Fun retention; after core loop works |
| Duel for typebeat | Compare two beats (also stream content) | GTM + engagement; after radio solid |
| Audio FX / vocals layer | Creative tools | Scope creep for v1 |
| Beat metadata: drop, key, length | Pro search | Enrichment pipeline; valuable but not day-one radio |

### MVP vs later (cut line)

| MVP (shippable product thesis) | Later |
| --- | --- |
| Radio with genre / free / FFP / view filters | Accounts, favs sync, playlists cloud |
| Catalog with same filters + search | Producer/listener pages, tiers |
| Decent listening UX (loop, skip, basic “station”) | Own “more like this” algo |
| Compression / leveling **intent** (even crude) | Full audio FX chain |
| Honest UG positioning; no user-data sales | Packs, partnerships, tinder/duel |
| Domain + basic protection plan | Split DB / search scale architecture |

---

## 5. Retention thesis

What keeps people coming back? Debate which mix is *true* for typebeat:

1. **Huge catalog** — depth of the free beats ocean; “I always find something.”
2. **Manual pain → easy radio** — what they did on YouTube (tabs, playlists, skips) becomes one station.
3. **Free radio for personal use** — low friction habit; daily driver.
4. **Royalty-free / commercial clarity (optional paid)** — when they need to *use* beats for profit without fear theater.
5. **Identity as UG supporter** — not Spotify chillhop clone; cultural belonging.
6. **Later hooks** — favs, playlists, producer follows, packs, tinder/duel, stream compare.

**Working bet for discussion:** Retention = **(3) habit radio + (1) catalog depth + (2) ease**, with **(4)** as monetization wedge for rappers/labels — not for casual chillers.

If retention only works via “sell the DB,” we’ve failed the ethics north star.

---

## 6. Monetization options (open decisions)

No recommendation locked. Pick with ethics (§7) in mind.

### A. Fully free (ads optional later)

| Pros | Cons |
| --- | --- |
| Cultural goodwill; growth; connector vibe | Bag unclear; infra costs; scrape/hosting bill |
| Matches “free beats ocean” energy | Hard to fund compression/search quality long-term |

### B. Freemium

- Free: personal radio + catalog browse (maybe rate limits / fewer filters).
- Paid: commercial/FFP clarity tools, higher limits, better compression, no ads, scouting exports, early “more like this.”

| Pros | Cons |
| --- | --- |
| Aligns personal free vs commercial paid | Easy to feel like paywalling culture if free tier is crippled |
| Justifiable if paid = *tools*, not “access to Black culture” | Needs crisp free forever promise |

### C. Paid radio (subscription)

| Pros | Cons |
| --- | --- |
| Clear bag; can fund no-ads + DSP-ish UX | Must justify beyond “glorified playlist” |
| | Cold start harder; cultural side-eye |

**If paid radio:** justify with **filters quality, compression, no ads, discovery that finds real UG, supporting producers** — not vibes alone.

### D. Open source

| Pros | Cons |
| --- | --- |
| Trust; contrib; anonifamous-friendly | Competitors clone; scrape arms race; support burden |
| Ethics signal | Monetization moves to hosted/pro tier or donations |

**Hybrid option:** OSS client/player + closed curated index, or OSS everything except hosted radio infra.

### E. Data sales (user DB / beat DB)

| Pros | Cons |
| --- | --- |
| Fast bag (Suno, Udio, BandLab, Pandora, etc. would buy) | **Extractive.** Contradicts UG platform story |
| | Legal/reputation nuke; becomes the product people hate |

**Stance for this draft:** Data sales of user or full beat DB = **Won’t (for now) / ethics red line.** Revisit only with producer consent frameworks and never raw user PII dumps.

### F. Take-rate on packs / partnerships (later)

Aligns connector role: make money when producers make money. Depends on marketplace maturity.

---

## 7. Ethics & positioning

### The hard question

Monetizing a space rooted in **predominantly Black / hip-hop culture** without becoming another platform that extracts and sells the culture back as SaaS.

### Positioning principles (debate / edit)

1. **Producers and culture are the product’s reason — not the feedstock.** Catalog exists to surface UG makers, not to strip-mine them for AI training deals.
2. **Free personal listening stays sacred** if anything is paid. Don’t charge chillers to hear free type beats.
3. **Paid must buy capability**, not belonging: compression, filters, commercial clarity, no ads, scouting tools, reliability.
4. **No selling people.** User DB is not inventory. Beat DB wholesale is not a go-to-market.
5. **Be honest about YouTube dependency.** We’re a discovery layer on others’ uploads until/unless licensing changes — don’t fake “we own the music.”
6. **Anonifamous ≠ shady.** Low profile brand is fine; opaque data practices are not.

### Justifying paid (if chosen)

Not “because playlist.” Because:

- Better station controls than YT (genre, free/FFP, view bands, year, hate/fav feedback).
- Listening comfort (leveling / compression, no ad roulette).
- Discovery quality (UG bias, recency rotation, later taste algo).
- Path that **supports** producers (cred, packs, connections) rather than only skimming attention.

If we can’t say those out loud without lying, don’t charge yet.

---

## 8. Feature backlog (MoSCoW)

Mapped from FUTURE DEV + radio/catalog wants. Adjust after open questions.

### Must (MVP)

- [ ] **Radio:** continuous play; genre change; free / FFP / view filters; skip
- [ ] **Catalog:** search + filters (genre, keywords, view ranges, free/FFP, year)
- [ ] **Latest + UG angle:** recency and/or low-view discovery modes
- [ ] **Listen comfort:** audio leveling / compression approach (even v1 crude)
- [ ] **Loop** current beat
- [ ] **Producer deep-link:** “more from this producer” (channel-level is enough for MVP)
- [ ] Stable deploy path + own domain intent
- [ ] Basic protection plan (no public writable DB; don’t treat threats as customers)

### Should (near-term after MVP)

- [ ] Favorites (per-genre?)
- [ ] Add to own playlist
- [ ] Hate this / downrank
- [ ] Hear more like this (v1: same genre + similar view band / tags — not full ML)
- [ ] Faster search (indexing; decide split DB or not)
- [ ] Metadata enrichment: **length**, **key**, **beat drop** (where is the drop?)
- [ ] Highlight / promote lanes for producers (editorial or algo)
- [ ] Visual theme inspired by YT “beats to work/relax” — atmospheric, not dashboard clutter
- [ ] Stream-friendly features: compare two beats; comment-on-stream hooks

### Could (later)

- [ ] Producer pages + listener pages
- [ ] Producer tiers / listener tiers
- [ ] Individual partnerships
- [ ] Sample pack buy/sell
- [ ] Tinder for typebeat
- [ ] Duel for typebeat
- [ ] Audio FX beyond leveling
- [ ] Vocals layer
- [ ] Accounts / sync across devices
- [ ] Commercial license clarity productized

### Won’t (for now)

- [ ] Selling user DB or full beat DB to Suno/Udio/BandLab/etc.
- [ ] Building for hackers/data buyers as a segment
- [ ] Full social network / fake community theater
- [ ] Claiming we replace YouTube hosting or own masters
- [ ] Maximal feature pack (FX + tinder + tiers) before radio+catalog loop is sticky

---

## 9. Open questions (founder decisions needed)

Reply in-line if useful (`Q1: freemium`, etc.).

### Business / ethics

| ID | Question | Options / notes |
| --- | --- | --- |
| Q1 | Paid or not? | Free / freemium / paid radio / packs-later |
| Q2 | Open source or not? | Closed / OSS / hybrid |
| Q3 | What is the free forever promise? | e.g. personal radio + catalog browse always free |
| Q4 | Any data licensing ever? | Draft stance = no wholesale DB sales |

### Retention / product

| ID | Question | Notes |
| --- | --- | --- |
| Q5 | What keeps people coming back — pick primary 1–2? | Catalog / radio ease / free personal / commercial tier / belonging |
| Q6 | Radio mix: latest vs random UG vs “station formats”? | Needs a clear default |
| Q7 | Is “low views = UG” the brand, or just one filter? | Avoid romanticizing zero-play trash |

### UX / brand

| ID | Question | Options |
| --- | --- | --- |
| Q8 | UI direction? | Glass (current radio experiment) / minimal / maximal dark+bold / “rap” energy |
| Q9 | Catalog columns to keep? | title, producer, views, date, free?, FFP?, genre, url… drop/add? |
| Q10 | Vocals layer? | In / out / later |

### Data / ops

| ID | Question | Notes |
| --- | --- | --- |
| Q11 | How is DB organized long-term? | Single SQLite vs split (search vs playback metadata) |
| Q12 | How often do we update / rescrape? | Daily? Weekly? On-demand per genre? |
| Q13 | Search architecture: split DB or not? | Performance vs ops complexity |
| Q14 | Enrichment priority: length / key / drop? | Order them |

### GTM / identity

| ID | Question | Notes |
| --- | --- | --- |
| Q15 | How visible is the founder? | Anonifamous brand voice vs personal |
| Q16 | First audience wedge? | Rappers freestyling vs chill listeners vs A&R |

---

## 10. Tech sketch (PRD-level only)

**Not an implementation plan.** Snapshot for product debate.

### Today

- **Ingest:** Python scrapers (`scrapetube` etc.), query generation, producer harvest, tagging (`is_free`, `free_for_profit`, genre).
- **Store:** SQLite `typebeats.db` (large; local). Schema evolved beyond old PRD (`published_time`, `genre`, `is_free`, `free_for_profit`).
- **UI prototypes:** Streamlit catalog (`app.py`), Streamlit radio (`radio.py`, glass-style player), early Next app (`web/`).
- **Pattern:** Scrape offline → DB → read-only frontends (good for rate limits / bans).

### Near-term product constraints

- Playback still leans on **YouTube** — rights, embeds, ToS, and breakage risk are product risks, not just eng tickets.
- Streamlit is fine for **validation**; a real consumer radio/catalog likely outgrows it (the `web/` experiment already hints at that).
- DB-in-git / Community Cloud is a prototype deployment story, not a security or scale story.

### Decisions to make later (not now)

- Hosted DB location; CDN; auth if accounts land.
- Search index (SQLite FTS vs external) if catalog lag hurts.
- Audio compression: client-side leveling vs preprocessed loudness metadata.
- Protection: secrets, scrape identity, abuse, scraping of *us*, backups — treat hacker/extort backlog item as threat model.

**Own domain:** yes when public; brand needs a real home before serious GTM.

---

## 11. Go-to-market / promote sketch

### Channels (from backlog)

Twitch, Kick, TikTok, Reddit, Threads, X, YouTube, Instagram.

### Angles that fit the product

| Angle | Why it works |
| --- | --- |
| “Type beat radio for work / freestyle” | Instant demo; lofi nostalgia with UG twist |
| Freedive clips: filters → weirdly good low-view gem | Shows catalog power in 15s |
| Compare two beats / duel on stream | Chat engagement; Kick/Twitch native |
| Producer spotlights | Connector role; builds trust with makers |
| “No harsh volume / less YT pain” | Concrete painkillers, not hype |

### Wedge suggestion (debate)

Launch narrative: **radio-first** for listeners/rappers → catalog for when they want to hunt → producers come because their beats get rotation and later packs/cred.

Avoid launching as “directory spreadsheet” publicly even if catalog exists — radio is the vibe; catalog is the depth.

---

## 12. Risks

| Risk | Why it matters | Mitigation direction |
| --- | --- | --- |
| **Legal / rights** | YT embeds, “free/FFP” claims may be wrong; commercial use is messy | Label license claims as *scraped signals*, not legal advice; paid commercial tier needs real clarity later |
| **YouTube dependency** | API/ToS/scrape breakage kills inventory | Diversify sources long-term; cache metadata; don’t pretend permanence |
| **Security** | Huge attractive DB; extortion fantasy is real enough | Lock down prod; no public raw DB; rate limits; monitoring |
| **Cold start** | Empty radio feels dead; empty social features worse | Lead with catalog size + radio buffer; delay social until density |
| **Cultural legitimacy** | Look like culture-vulture SaaS | Free personal tier; no data sales; producer-forward storytelling; don’t over-corporate the brand |
| **Quality signal failure** | Low views ≠ good | Combine recency, free tags, genre, later feedback (hate/fav) |
| **Scope explosion** | Tinder + duel + FX + tiers before sticky loop | MoSCoW discipline |
| **Ethics backlash** | Paid without justification | Only charge for tools/comfort/commercial clarity |

---

## Appendix A — Persona want-lists (raw mapping)

Quick traceability from founder backlog → surfaces.

**Radio / listener:** latest, genres, favs, more from producer, more like this, playlists, hate, catalog dive, loop, compression, packs inspiration → Radio Must/Should + Catalog Must + Packs Could.

**Radio / producer:** rotation, packs, cred → Radio Should (rotation rules) + Packs/Pages Could.

**Rapper / label:** inspire, free ocean, radio gems, connect, packs, no harsh sound → same MVP spine; connect/packs later.

**Catalog / industry shark & hacker & data buyer:** → Threat model only.

**Founder:** connector, bag, anonifamous → ethics + monetization + GTM voice.

---

## Appendix B — Suggested decision reply format

```text
Q1 Monetization:
Q2 OSS:
Q3 Free forever means:
Q5 Retention primary:
Q6 Radio default mix:
Q8 UI direction:
Q11–Q13 DB / refresh / search:
Q16 First wedge audience:
Anything in Must that should be Won’t:
```

---

*End of v2 discussion draft. Old `PRD.md` left untouched; this file is `PRD-v2-draft.md` for debate.*
