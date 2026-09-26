import requests
from bs4 import BeautifulSoup
import time

# YOUR SEEDS
seed_artists = ["skepta",
"wiley",
"Dizzee Rascal",
"D Double E",
"Ghetts",
"jme",
"Novelist",
"Casisdead",
"stormzy",
"mez",
"Duppy",
"Faultsz",
"Mic Ty",
"Knucks",
"Giggs",
"PinkPantheress",
"Central Cee",
"Loyle Carner",
"Little Simz",
"Princess Nokia"
]
TARGET_COUNT = 500

discovered_artists = set()
# We use a 'queue' to keep track of who to scout next
queue = list(seed_artists)
visited = set()

def get_similar_artists(artist_name):
    # Normalize name for Last.fm URL
    formatted_name = artist_name.replace(" ", "+")
    url = f"https://www.last.fm/music/{formatted_name}/+similar"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        artist_links = soup.find_all("a", class_="link-block-target")
        
        found_here = []
        for link in artist_links:
            name = link.text.strip()
            # CASE-SENSITIVE FIX: We check a lowercase version to prevent duplicates
            if name and name.lower() not in [a.lower() for a in discovered_artists]:
                found_here.append(name)
                discovered_artists.add(name)
        return found_here
    except:
        return []

if __name__ == "__main__":
    print(f"🚀 Deep Radar engaged. Target: {TARGET_COUNT} artists...")
    
    while len(discovered_artists) < TARGET_COUNT and queue:
        current_scout = queue.pop(0)
        
        if current_scout.lower() in visited:
            continue
            
        new_names = get_similar_artists(current_scout)
        visited.add(current_scout.lower())
        
        # Add new names to the back of the queue to keep digging deeper
        queue.extend(new_names)
        
        print(f"📊 Progress: {len(discovered_artists)}/{TARGET_COUNT} (Just scouted: {current_scout})")
        
        # Be polite to the servers
        time.sleep(0.5)

    print(f"\n✅ Mission accomplished. Found {len(discovered_artists)} artists.")
    
    # Save with quotes and commas
    with open("new_artists.txt", "w") as f:
        for artist in sorted(list(discovered_artists)):
            f.write(f'"{artist}",\n')
            
    print("📝 500+ artists saved to new_artists.txt!")