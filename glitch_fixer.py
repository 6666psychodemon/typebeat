import sqlite3

print("🔌 Connecting to the matrix...")
conn = sqlite3.connect("typebeats.db")
cursor = conn.cursor()

# Find the glitched tracks
cursor.execute("SELECT COUNT(*) FROM beats WHERE published_time < '2014-01-01'")
glitch_count = cursor.fetchone()[0]

print(f"🗑️ Found {glitch_count} tracks corrupted by the Time Paradox.")

# Delete them so the harvester can grab them fresh
cursor.execute("DELETE FROM beats WHERE published_time < '2014-01-01'")
conn.commit()
conn.close()

print("✅ Glitches wiped! The next time your scraper runs, it will re-harvest them with the correct dates.")