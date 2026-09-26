import sqlite3
import re
from datetime import datetime, timedelta

def get_absolute_date(relative_text, scrape_date_str):
    # If it's already a real date format (YYYY-MM-DD), skip it
    if re.match(r"\d{4}-\d{2}-\d{2}", str(relative_text)):
        return relative_text

    try:
        # Default to the day we scraped it if we can't read the text
        scrape_date = datetime.strptime(scrape_date_str, "%Y-%m-%d")
    except:
        scrape_date = datetime.now()

    ts = str(relative_text).lower()
    match = re.search(r"(\d+)", ts)
    if not match: 
        return scrape_date.strftime("%Y-%m-%d")
    
    n = int(match.group(1))
    days = 0
    
    if 'year' in ts or ('y' in ts and 'day' not in ts): days = n * 365
    elif 'month' in ts: days = n * 30
    elif 'week' in ts: days = n * 7
    elif 'day' in ts: days = n
    elif 'hour' in ts or 'min' in ts or 'sec' in ts: days = 0
        
    actual_date = scrape_date - timedelta(days=days)
    return actual_date.strftime("%Y-%m-%d")

print("🕰️ Starting the Time Machine... fixing 75k+ dates.")

conn = sqlite3.connect("typebeats.db")
cursor = conn.cursor()

# Get all records
cursor.execute("SELECT video_id, published_time, scraped_at FROM beats")
rows = cursor.fetchall()

updates = 0
for row in rows:
    vid, pub_time, scraped_at = row
    
    # Calculate the hard, absolute date
    real_date = get_absolute_date(pub_time, scraped_at)
    
    if real_date != pub_time:
        cursor.execute("UPDATE beats SET published_time=? WHERE video_id=?", (real_date, vid))
        updates += 1

conn.commit()
conn.close()

print(f"✅ Time machine complete! Converted {updates} relative dates into absolute YYYY-MM-DD formats.")