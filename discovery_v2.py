import scrapetube
import re

# 1. THE SEED LIST: This covers all major underground "mother-genres"
SEEDS = [
    "plugg", "pluggnb", "rage", "opium", "supertrap", "jerk", "sigilkore", 
    "scenecore", "glitchcore", "drain gang", "sadboy", "cloud rap", "drill", 
    "ny drill", "jersey club", "ambient trap", "experimental trap", "dark trap", 
    "hardcore punk", "underground rap", "lofi trap", "phonk", "dirt", "slump",
    "vamp", "ethereal", "virtual", "cyber", "webcore", "hexxed", "dark plugg"
]

def clean_query(text):
    """Surgically removes marketing junk to find the core artist/genre."""
    # Remove everything in brackets or parens
    text = re.sub(r'[\[\(].*?[\]\)]', '', text)
    # Common words to delete
    junk = ["free", "prod", "by", "new", "type", "beat", "2024", "2025", "2026", "hard", "dark", "buy", "lease"]
    for word in junk:
        text = text.replace(word, "")
    # Remove separators and extra spaces
    text = re.sub(r'[|&\-+]', ' ', text)
    return text.strip()

def discover_wide(limit_per_seed=100):
    found_queries = set()
    print(f"🚀 Launching Mega Discovery across {len(SEEDS)} seeds...")

    for seed in SEEDS:
        print(f"🛰️ Deep-scanning seed: {seed}")
        try:
            # We search for "[seed] type beat"
            videos = scrapetube.get_search(f"{seed} type beat", limit=limit_per_seed)
            for vid in videos:
                title = vid['title']['runs'][0]['text'].lower()
                
                # Split title by 'x' because producers list multiple artists
                # Example: "Yeat x Carti x Ken Carson Type Beat"
                if "type beat" in title:
                    pre_type = title.split("type beat")[0]
                    # Split by 'x' to get individual artist names
                    potential_artists = pre_type.split("x")
                    
                    for artist in potential_artists:
                        clean = clean_query(artist)
                        # We only want names that are 3-20 characters long to avoid 'a' or 'the'
                        if 3 <= len(clean) <= 20:
                            found_queries.add(f"{clean} type beat")
        except:
            continue

    # Save to queries.txt
    with open("queries.txt", "w") as f:
        for q in sorted(list(found_queries)):
            f.write(q + "\n")
    
    print(f"✅ Mission Success. Found {len(found_queries)} niches.")
    print("📂 Your 'queries.txt' is now a gold mine.")

if __name__ == "__main__":
    discover_wide()