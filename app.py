import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="Underground Type Beat Directory", layout="wide")

def load_data():
    conn = sqlite3.connect("typebeats.db")
    df = pd.read_sql_query("SELECT * FROM beats", conn)
    conn.close()
    
    # Let Pandas natively read the perfect YYYY-MM-DD strings from your database
    if 'published_time' in df.columns:
        df['published_time'] = pd.to_datetime(df['published_time'], errors='coerce')
    return df

try:
    df = load_data()

    st.sidebar.header("Navigation")
    search_query = st.sidebar.text_input("Search Title or Producer (e.g. 'lil')", "").lower()
    max_views = st.sidebar.slider("Max Views", 0, 100000, 100000)
    show_free_only = st.sidebar.checkbox("Show Free Beats Only ✅")
    
    genres = sorted(df['genre'].unique().astype(str).tolist()) if 'genre' in df.columns else []
    selected_genre = st.sidebar.multiselect("Filter by Genre", genres)

    filtered = df[df['views'] <= max_views].copy()
    
    if search_query:
        filtered = filtered[
            filtered['title'].str.lower().str.contains(search_query) | 
            filtered['channel_name'].str.lower().str.contains(search_query)
        ]
    
    if selected_genre:
        filtered = filtered[filtered['genre'].isin(selected_genre)]
    
    if show_free_only:
        filtered = filtered[filtered['is_free'] == 1]

    st.title("🎧 Underground Type Beat Directory")
    st.subheader(f"Found {len(filtered)} items in the database")

    cols_to_show = ["title", "channel_name", "views", "published_time", "url"]
    
    if "is_free" in filtered.columns:
        filtered['Free?'] = filtered['is_free'].apply(lambda x: "✅" if x == 1 else "❌")
        cols_to_show.insert(3, "Free?")

    # Initial sort: Newest first
    display_df = filtered[cols_to_show].sort_values(by="published_time", ascending=False)

    st.dataframe(
        display_df,
        column_config={
            "url": st.column_config.LinkColumn("YouTube Link"),
            "views": st.column_config.NumberColumn("Views", format="%d"),
            "title": st.column_config.TextColumn("Track Name", width="large"),
            "published_time": st.column_config.DatetimeColumn(
                "Date", 
                format="MMM YYYY", 
                width="small"
            )
        },
        hide_index=True,
        width="stretch"
    )

except Exception as e:
    st.error(f"Waiting for data... ({e})")