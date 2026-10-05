import sqlite3

conn = sqlite3.connect('skypulse.db')
cursor = conn.cursor()

# Remove integer/bad IDs from sources
cursor.execute("DELETE FROM sources WHERE id IN ('8', 8, '3', 3, '00000000000000000000000000000008', '00000000000000000000000000000003')")

# Insert valid hyphenated UUIDs
cursor.execute("""
INSERT OR REPLACE INTO sources (id, name, description, source_type, connector_class, config, trust_score, is_active, is_demo, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000008', 'Regional News RSS Feeds', 'National and regional multi-lingual news feeds', 'RSS_FEED', 'RegionalRSSConnector', '{}', 0.75, 1, 0, datetime('now'), datetime('now'))
""")

cursor.execute("""
INSERT OR REPLACE INTO sources (id, name, description, source_type, connector_class, config, trust_score, is_active, is_demo, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000003', 'Google News RSS Discovery', 'Google News RSS automated hazard discovery stream', 'RSS_FEED', 'GNewsDiscoveryConnector', '{}', 0.70, 1, 0, datetime('now'), datetime('now'))
""")

# Fix source_id in weather_reports
cursor.execute("""
UPDATE weather_reports
SET source_id = '00000000-0000-0000-0000-000000000008'
WHERE source_id IN ('8', 8, '00000000000000000000000000000008')
""")

cursor.execute("""
UPDATE weather_reports
SET source_id = '00000000-0000-0000-0000-000000000003'
WHERE source_id IN ('3', 3, '00000000000000000000000000000003')
""")

conn.commit()
print("Fixed UUID formats in sources and weather_reports.")

cursor.execute("SELECT id, name FROM sources")
for row in cursor.fetchall():
    print(f"Source: {row[0]} -> {row[1]}")

conn.close()
