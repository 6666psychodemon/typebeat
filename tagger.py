import sqlite3

# THE HIERARCHY MAP
# High Level -> Keywords to look for in the Title/Style
GENRE_MAP = {
    "Plugg/Pluggnb": ["plugg", "pluggnb", "mexikodro", "stoopidxool", "neopop", "cashcache"],
    "Rage/Opium": ["rage", "opium", "f1lthy", "ken carson", "carti", "yeat", "hyperpop"],
    "Experimental/Glitch": ["sigilkore", "hexxed", "glitchcore", "webcore", "drain", "bladee", "scenecore"],
    "Drill": ["drill", "ny drill", "uk drill", "central cee", "pop smoke"],
    "Ambient/Cloud": ["ambient", "cloud rap", "clams casino", "ethereal", "spacey"],
    "Dark/Aggressive": ["dark", "evilgiane", "thraxx", "city morgue", "zillakami", "hardcore"],
    "Boom Bap/Old School": ["boom bap", "lofi", "90s", "east coast", "old school"]
}

def tag_database():
    conn = sqlite3.connect("typebeats.db")
    cursor = conn.cursor()

    # 1. Add the genre column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE beats ADD COLUMN genre TEXT")
        print("✅ Added 'genre' column to database.")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    print("🏷️ Starting auto-tagging process...")
    cursor.execute("SELECT video_id, title, artist_style FROM beats")
    rows = cursor.fetchall()

    for vid_id, title, style in rows:
        found_genre = "Underground" # Default bucket
        full_text = f"{title} {style}".lower()

        # Check against our hierarchy
        for genre, keywords in GENRE_MAP.items():
            if any(key in full_text for key in keywords):
                found_genre = genre
                break
        
        cursor.execute("UPDATE beats SET genre = ? WHERE video_id = ?", (found_genre, vid_id))

    conn.commit()
    conn.close()
    print(f"✅ Tagged {len(rows)} videos into structured genres.")

if __name__ == "__main__":
    tag_database()