import sqlite3

def setup_database(db_name="typebeats.db"):
    print("🛠️ Creating fresh database...")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # We are using a clean structure: No genres, just raw names and parsed styles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS beats (
            video_id TEXT PRIMARY KEY,
            title TEXT,
            artist_style TEXT,
            channel_name TEXT,
            url TEXT,
            views INTEGER,
            upload_time_raw TEXT,
            scraped_at TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database is ready with 'artist_style' column.")

if __name__ == "__main__":
    setup_database()