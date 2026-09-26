import scrapetube
import re

# Starting points to find the underground
SEEDS = ["underground type beat", "niche type beat", "experimental trap beat", "plugg type beat"]

def discover_new_genres():
    found_queries = set()
    print("🔎 Starting discovery mission...")

    for seed in SEEDS:
        print(f"🛰️ Exploring seed: {seed}")
        try:
            videos = scrapetube.get_search(seed, limit=50)
            for vid in videos:
                title = vid['title']['runs'][0]['text'].lower()
                
                # Regex: Find whatever is before "type beat"
                # Matches: "Lazer Dim 700 Type Beat" -> "Lazer Dim 700"
                match = re.search(r'(.*?)type\s*beat', title)
                if match:
                    raw_keyword = match.group(1).strip()
                    # Clean up the noise
                    clean = re.sub(r'[\[\(].*?[\]\)]', '', raw_keyword)
                    clean = clean.replace("free", "").replace("prod", "").strip("-| ").strip()
                    
                    if len(clean) > 2 and clean not in ["unknown", "new"]:
                        found_queries.add(f"{clean} type beat")
        except:
            continue

    # Save to a text file
    with open("queries.txt", "w") as f:
        for q in sorted(found_queries):
            f.write(q + "\n")
    
    print(f"✅ Discovery complete. Found {len(found_queries)} unique niches.")
    print("📄 Saved to 'queries.txt'.")

if __name__ == "__main__":
    discover_new_genres()