import sqlite3

print("🔌 Connecting to the matrix...")
conn = sqlite3.connect("typebeats.db")
cursor = conn.cursor()

# 1. Add the column (We use a try/except so it doesn't crash if you run this twice)
try:
    cursor.execute("ALTER TABLE beats ADD COLUMN free_for_profit INTEGER DEFAULT 0")
    print("✅ Added 'free_for_profit' column to the database.")
except sqlite3.OperationalError:
    print("⚡ Column 'free_for_profit' already exists. Skipping creation.")

# 2. Run the massive SQL update command
print("🔍 Scanning nearly 500k tracks for Commercial Use tags...")
cursor.execute('''
    UPDATE beats 
    SET free_for_profit = 1 
    WHERE is_free = 1 
    AND (
        title LIKE '%for profit%' OR 
        title LIKE '%profit%' OR 
        title LIKE '%commercial%' OR 
        title LIKE '%ffp%'
    )
''')

# 3. Get the exact number of tracks that were updated
updated_rows = cursor.rowcount

conn.commit()
conn.close()

print(f"🎉 Success! You just permanently tagged {updated_rows} tracks as Free For Profit.")