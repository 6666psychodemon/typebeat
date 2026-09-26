# Producer activity (publish window)

Generated: `2026-08-10 23:47:06`
Window: `published_time >= 2026-03-27` and `< 2026-08-11` (exclusive end).
DB: `typebeats.db`

## Thresholds

Computed from the distribution of `window_track_count` among producers
with ≥1 track in the window (nearest-rank percentiles):

| Stat | Value |
|------|------:|
| Producers in window | 81,365 |
| Tracks in window | 553,915 |
| Producer Harvest v2 inserts (all-time in DB) | 99,255 |
| p50 (median) | 2 |
| p75 (warm floor) | 5 |
| p90 | **22** ← prolific cutoff |
| p95 | 40 |
| mean | 6.81 |

### Tier definitions

- **Prolific**: `window_track_count ≥ 22` (at/above p90; high output)
- **Active**: `3 … 21` tracks in window (moderate)
- **Sparse**: `1–2` tracks in window (usually not worth harvest priority)
- Note: p75=5 is a warm floor inside Active — rising toward prolific.

## Counts per tier

| Tier | Producers | Share |
|------|----------:|------:|
| Prolific | 8,196 | 10.1% |
| Active | 23,119 | 28.4% |
| Sparse | 50,050 | 61.5% |

## Track-count histogram (window)

| window_track_count | producers |
|-------------------:|----------:|
| 1 | 39,216 |
| 2 | 10,834 |
| 3 | 5,499 |
| 4 | 3,530 |
| 5 | 2,546 |
| 6 | 2,037 |
| 7 | 1,579 |
| 8 | 1,214 |
| 9 | 1,098 |
| 10 | 851 |
| 11 | 679 |
| 12 | 597 |
| 13 | 507 |
| 14 | 447 |
| 15 | 413 |
| 16 | 411 |
| 17 | 370 |
| 18 | 367 |
| 19 | 322 |
| 20 | 339 |
| 22 | 296 |
| 25 | 242 |
| 40 | 216 |
| 50 | 224 |
| 75 | 6 |
| >20 (sum) | 8,509 |

## Top prolific examples

| channel_name | window | total | last_publish |
|--------------|-------:|------:|--------------|
| Fukk2Beatz | 249 | 1105 | 9 days ago |
| Release - Topic | 161 | 170 | Unknown |
| Bino The Beat Plug - Future | 133 | 181 | 2026-08-05 |
| Trunxks Beatz | 113 | 399 | 9 months ago |
| Prod. Galaxy | 112 | 189 | 2026-08-04 |
| Bino the Beat Plug - Drake | 105 | 168 | 2026-08-04 |
| RayOffkey | 102 | 176 | 7 months ago |
| prod. prymus | 101 | 232 | 8 days ago |
| EVARAN | 98 | 102 | 4 months ago |
| K.O Beats II | 98 | 129 | 3 years ago |
| uneweer | 98 | 101 | 2026-07-26 |
| fukkem800s | 95 | 108 | 43 minutes ago |
| Bino The Beat Plug - Kendrick Lamar | 94 | 184 | 3 months ago |
| Bobby Pebblestone Beats | 94 | 145 | 3 years ago |
| nìjam | 94 | 94 | 2026-07-23 |

## Sample active (highest in tier)

| channel_name | window | total | last_publish |
|--------------|-------:|------:|--------------|
|  (𝙏𝙃𝙀 𝘾𝙊𝙉𝙎𝘾𝙄𝙊𝙐𝙎𝙉𝙀𝙎𝙎 𝙕𝙊𝙉𝙀) ☯ | 21 | 23 | 2026-04-04 |
|  eulogy808 | 21 | 33 | 2026-04-03 |
|  Pisce_z | 21 | 25 | 2026-04-12 |
| 10K Sosa | 21 | 21 | 2026-04-12 |
| 1ayotee | 21 | 38 | 2026-04-10 |
| 1Heart Beats | 21 | 21 | 2026-04-09 |
| 1Ivy | 21 | 23 | 3 years ago |
| 33erbra | 21 | 22 | 2026-04-15 |
| 8 Gram Beats | 21 | 23 | 2026-04-05 |
| 808 Productions | 21 | 22 | 2026-04-12 |

## Artifacts

- `prolific_producers.txt` — names only (feed into priority harvest)
- `prolific_producers.csv` — channel_name, window_track_count, window_tracks, last_publish, …
- `active_producers.csv` / `sparse_producers.csv`
- Re-run: `python analyze_producer_activity.py` (add `--snapshot` while harvester is writing)

## How this helps attention / harvest priority

1. **Attention**: focus curation / radio / tagging on prolific + active; ignore sparse noise.
2. **Harvest order**: put `prolific_producers.txt` ahead of cold / sparse names when
   rebuilding priority lists (`build_producer_priority.py` or a manual prepend).
3. **Skip waste**: sparse (1–2) producers rarely justify another YouTube search pass.
4. **Note**: `producer_harvester_v2` default search window may still end at
   `before:2026-08-06`; extend `--before` if you want harvest to match “through today”.

