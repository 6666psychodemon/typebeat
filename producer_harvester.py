import scrapetube
import sqlite3
import re
import random
import os
from datetime import datetime, timedelta

def get_absolute_date(relative_text, scrape_date_str):
    """Upgraded Date Engine: Immune to View Count Hijacking"""
    if re.match(r"\d{4}-\d{2}-\d{2}", str(relative_text)):
        return relative_text

    try:
        scrape_date = datetime.strptime(scrape_date_str, "%Y-%m-%d")
    except:
        scrape_date = datetime.now()

    ts = str(relative_text).lower()
    
    # NEW REGEX: Forces the number to be immediately followed by a unit of time
    match = re.search(r"(\d+)\s*(year|yr|month|mo|week|wk|day|hour|min|sec)", ts)
    
    if not match: 
        return scrape_date.strftime("%Y-%m-%d")
    
    n = int(match.group(1))
    unit = match.group(2)
    
    days = 0
    if unit in ['year', 'yr']: days = n * 365
    elif unit in ['month', 'mo']: days = n * 30
    elif unit in ['week', 'wk']: days = n * 7
    elif unit == 'day': days = n
    # hours/mins/secs default to 0 days (today)
        
    actual_date = scrape_date - timedelta(days=days)
    return actual_date.strftime("%Y-%m-%d")
    
def extract_views(vid):
    v_text = vid.get('viewCountText', {}).get('simpleText') or "0"
    raw_text = v_text.lower().replace(',', '').replace(' ', '').replace('\xa0', '')
    multipliers = {'k': 1000, 'm': 1000000}
    multiplier = 1
    for key, val in multipliers.items():
        if key in raw_text:
            multiplier = val
            break
    nums = re.findall(r"(\d+\.?\d*)", raw_text)
    try: return int(float(nums[0]) * multiplier) if nums else 0
    except: return 0

def run_producer_harvest():
    conn = sqlite3.connect("typebeats.db")
    cursor = conn.cursor()

    # 1. Load the "Done List"
    done_file = "harvested_producers.txt"
    already_harvested = set()
    if os.path.exists(done_file):
        with open(done_file, "r", encoding="utf-8") as f:
            already_harvested = set(line.strip() for line in f)

    # 2. Get all known producers
    print("🗄️ Fetching known producers from the database...")
    cursor.execute("SELECT DISTINCT channel_name FROM beats WHERE channel_name IS NOT NULL")
    all_producers = [row[0] for row in cursor.fetchall()]
    
    # 3. Filter out the ones we already harvested
    pending_producers = [p for p in all_producers if p not in already_harvested]
    
    # 4. RANDOMIZE the list
    random.shuffle(pending_producers)

    print(f"🎯 Found {len(all_producers)} total producers.")
    print(f"⏭️ Skipping {len(already_harvested)} already harvested.")
    print(f"🚀 Ready to harvest {len(pending_producers)} pending producers (Randomized Order).")

    for producer in pending_producers:
        print(f"\n🚜 Harvesting catalog for: {producer}")
        consecutive_knowns = 0
        
        try:
            # Change limit here if you want to go deeper
            videos = scrapetube.get_search(f'"{producer}" type beat', limit=50)
            
            for vid in videos:
                video_id = vid['videoId']
                
                # --- THE CIRCUIT BREAKER ---
                cursor.execute("SELECT views FROM beats WHERE video_id=?", (video_id,))
                existing = cursor.fetchone()
                
                if existing:
                    consecutive_knowns += 1
                    new_views = extract_views(vid)
                    
                    cursor.execute("UPDATE beats SET views=?, scraped_at=? WHERE video_id=?", 
                                   (new_views, datetime.now().strftime("%Y-%m-%d"), video_id))
                    
                    if consecutive_knowns >= 3:
                        print(f"   ⏭️ Reached known territory for {producer}. Moving on.")
                        break 
                    continue 
                
                consecutive_knowns = 0
                title = vid['title']['runs'][0]['text']
                
                if "type beat" not in title.lower():
                    continue
                
                is_free = 1 if "free" in title.lower() else 0
                views = extract_views(vid)
                
                if 0 < views <= 100000:
                    pub_time_raw = vid.get('publishedTimeText', {}).get('simpleText') or "Unknown"
                    scrape_date_str = datetime.now().strftime("%Y-%m-%d")
                    
                    actual_pub_date = get_absolute_date(pub_time_raw, scrape_date_str)
                    clean_style = "Producer Harvest"
                    
                    cursor.execute('''INSERT OR REPLACE INTO beats 
                        (video_id, title, artist_style, channel_name, url, views, published_time, scraped_at, is_free) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (video_id, title, clean_style, 
                         vid['longBylineText']['runs'][0]['text'], f"https://youtube.com/watch?v={video_id}", 
                         views, actual_pub_date, scrape_date_str, is_free))
            
            conn.commit()
            
            # 5. Mark as DONE after finishing their catalog
            with open(done_file, "a", encoding="utf-8") as f:
                f.write(f"{producer}\n")
            print(f"✅ Marked '{producer}' as completely harvested.")

        except KeyboardInterrupt: 
            print("\n🛑 Manual stop received.")
            break
        except Exception as e: 
            print(f"⚠️ Error harvesting {producer}: {e}")
            continue
    
    conn.close()
    print("✅ Producer harvest complete.")

if __name__ == "__main__": 
    run_producer_harvest()