# 🎧 Product Requirements Document: Underground Type Beat Directory

## 1. Project Overview

**Objective:** Build an automated directory and discovery engine for YouTube "type beats." The platform allows producers and artists to bypass YouTube's algorithm to find high-quality, low-view instrumentals by searching specific producer styles and filtering out overplayed tracks.

**Current State:** A fully functional local prototype consisting of a backend SQLite database, an automated scraping pipeline using `scrapetube`, and a Streamlit frontend.

## 2. Tech Stack & Architecture

* **Frontend / UI:** Streamlit (`app.py`)
* **Database:** SQLite (`typebeats.db`)
* **Scraping / Data Ingestion:** Python with `scrapetube` (`scraper.py`)
* **Data Processing:** `pandas`, `re` (Regular Expressions for string parsing)
* **Architecture Pattern:** Decoupled. The scraper runs independently to update the local `.db` file. The frontend strictly reads from the `.db` file (read-only) to ensure fast load times and avoid live-scraping bans.

---

## 3. Database Schema (`beats` table)

The database is initialized via `db_setup.py`.

| Column Name | Data Type | Description |
| --- | --- | --- |
| `video_id` | `TEXT (Primary Key)` | Unique YouTube ID. Prevents duplicate entries. |
| `title` | `TEXT` | Full raw video title. |
| `artist_style` | `TEXT` | Parsed style (e.g., "Yeat", "Bones"). Extracted from the title. |
| `channel_name` | `TEXT` | Name of the YouTube channel/producer. |
| `url` | `TEXT` | Direct YouTube link (`[https://youtube.com/watch?v=](https://youtube.com/watch?v=){video_id}`). |
| `views` | `INTEGER` | Cleaned view count for filtering. |
| `upload_time_raw` | `TEXT` | YouTube's raw time string (e.g., "3 days ago"). |
| `scraped_at` | `TIMESTAMP` | When the script added the record. |

---

## 4. Core Components & Logic

### A. The Scraper (`scraper.py`)

* **Targeting:** Iterates through a defined list of search queries (e.g., `"yeat type beat"`, `"lucki type beat"`).
* **Date Filtering:** Uses YouTube's native boolean operators (e.g., appending `after:2026-03-27` to queries) to fetch specific date ranges.
* **Sorting:** Forces `scrapetube` to sort by `upload_date` to ensure chronological scraping.
* **Stealth Mechanics:** Uses `time.sleep(random.uniform(0.3, 0.8))` between requests to prevent IP bans. Limits requests per keyword to avoid infinite scrolling.

### B. The Parsing Engine (RegEx inside Scraper)

* **The Slicer:** Uses the phrase `"type beat"` (case-insensitive) as the anchor to split the video title into two parts.
* **Artist Extraction:** Takes the string to the *left* of "type beat" and applies a cleanup function.
* **Cleanup Rules:**
* Removes text enclosed in `[]` or `()`.
* Strips out marketing fluff: "FREE", "PROD BY", "PROD.", "HARD", "DARK", "GUITAR".
* Removes dashes (`-`) and pipes (`|`).
* The resulting clean string is saved to the `artist_style` column.


* **The Guardrail:** If a video title does not contain the phrase `"type beat"`, the parser rejects it entirely to maintain database purity.

### C. The Frontend (`app.py`)

* **Data Caching:** Uses `@st.cache_data` to store the SQLite query in memory, keeping the UI snappy.
* **Discovery First:** Automatically sorts the dataframe by `Views` (ascending) so the lowest-view beats appear at the top.
* **Filters:**
* Global Text Search (queries `title`, `artist_style`, and `channel_name`).
* Max Views Slider (dynamically adjusts to the maximum view count in the DB).


* **UI Features:** Renders a clean Pandas dataframe using Streamlit's `st.dataframe`. Transforms raw URLs into clickable "Listen" buttons using `st.column_config.LinkColumn`.

---

## 5. Development Workflow & Rules for Cursor

* **Environment:** Code runs inside a Python virtual environment (`venv`).
* **Execution:**
1. Run `python3 scraper.py` to ingest data.
2. Run `streamlit run app.py` to view the UI.


* **Duplicate Handling:** Handled exclusively by SQLite's `INSERT OR IGNORE` command using the `video_id`. Do not write complex Python logic to check for duplicates; let the database engine handle it.
* **Deployment Goal:** The final app will be hosted on Streamlit Community Cloud via a GitHub repository. The SQLite `.db` file will be pushed to the repo alongside the code.