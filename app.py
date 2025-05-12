import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import requests
from io import StringIO

NCAA_STATS_URL = 'https://stats.ncaa.org'

def get_player_statistics(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    html = requests.get(url, headers=headers).text
    player_soup = BeautifulSoup(html, 'html.parser')

    select_element = player_soup.select_one('select#player_id option[selected="selected"]')
    raw_name = select_element.get_text().strip()
    if ',' in raw_name:
        last, rest = raw_name.split(',', 1)
        first = rest.strip().split(' ')[0]
        player_name = f"{first} {last}"
    else:
        player_name = raw_name

    tables = player_soup.find_all('table', class_='dataTable')
    final_table = pd.DataFrame()

    for table in tables:
        headings = [th.get_text().strip() for th in table.select('th')]
        if 'Year' in headings and 'Team' in headings:
            try:
                team_index = headings.index('Team')
                year_index = headings.index('Year')
                rows = [row for row in table.find_all('tr') if row.find_all('td')]

                for row in rows:
                    team = row.select('td')[team_index].select_one('a')
                    year = row.select('td')[year_index].get_text().strip()
                    if not team:
                        continue

                    team_url = NCAA_STATS_URL + team['href']
                    team_soup = BeautifulSoup(requests.get(team_url, headers=headers).text, 'html.parser')
                    stats_link = next((a['href'] for a in team_soup.select('a') if a.get_text() == 'Team Statistics'), None)
                    if not stats_link:
                        continue

                    stats_soup = BeautifulSoup(requests.get(NCAA_STATS_URL + stats_link, headers=headers).text, 'html.parser')

                    def extract_table(stat_type):
                        link = next((a['href'] for a in stats_soup.select('a') if a.get_text() == stat_type), None)
                        if not link:
                            return None
                        table = pd.read_html(StringIO(requests.get(NCAA_STATS_URL + link).text))[0]
                        if 'Player' not in table.columns:
                            return None
                        table = table[table['Player'] == player_name]
                        table.columns = table.columns.str.replace(" ", "_")
                        return table

                    dfs = [extract_table(stat) for stat in [
                        "Rushing", "Passing", "Receiving", "Sacks", "Tackles",
                        "Passes Defended", "Fumbles", "Defense"
                    ]]

                    if dfs[0] is None or dfs[1] is None:
                        continue

                    dfs = [df.reset_index(drop=True) if df is not None else pd.DataFrame() for df in dfs]

                    dfs[0] = dfs[0].assign(Season=year)
                    merged = pd.concat(dfs, axis=1)
                    final_table = pd.concat([final_table, merged], ignore_index=True)
            except Exception as e:
                st.warning(f"Error: {e}")
                continue

    return final_table.fillna(0)

# Streamlit UI
st.title("🏈 NCAA Player Stats Scraper")

url = st.text_input("Paste NCAA player stats URL (from stats.ncaa.org):")
if st.button("Scrape Stats"):
    if url:
        df = get_player_statistics(url)
        if not df.empty:
            st.success("✅ Stats successfully retrieved!")
            st.dataframe(df)
            st.download_button("📥 Download as Excel", df.to_excel(index=False), "player_statistics.xlsx")
        else:
            st.warning("No stats found. Please check the URL.")
    else:
        st.warning("Please enter a valid URL.")
