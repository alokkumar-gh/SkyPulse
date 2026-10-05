"""
Location Provenance & Normalization Resolver (High-Performance Vectorized Matcher)
Enriches reports that have location evidence in text, metadata, or titles,
resolving state, district, city, coordinates, and provenance without inventing data.
"""

import sqlite3
import re
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectors.normalizer import INDIAN_CITIES_REFERENCE, INDIAN_STATES_REFERENCE
from connectors.weather_discovery.india_locations import INDIA_STATES

def resolve_all():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skypulse.db"))
    con = sqlite3.connect(db_path, timeout=30.0)
    cur = con.cursor()

    cur.execute("SELECT id, normalized_text, raw_content, location_city, metadata FROM weather_reports WHERE location_state IS NULL")
    rows = cur.fetchall()
    print(f"Total reports with location_state IS NULL: {len(rows)}", flush=True)

    # 1. Build precompiled regex patterns
    # Sort keys by length descending to match multi-word names first
    sorted_city_keys = sorted([k for k in INDIAN_CITIES_REFERENCE.keys() if len(k) >= 3], key=len, reverse=True)
    city_pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_city_keys) + r")\b", re.IGNORECASE)

    sorted_state_keys = sorted([k for k in INDIAN_STATES_REFERENCE.keys() if len(k) >= 3], key=len, reverse=True)
    state_pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_state_keys) + r")\b", re.IGNORECASE)

    state_obj_map = {s["name"].lower(): s for s in INDIA_STATES.values()}

    updated_rows = []
    resolved_count = 0

    for rid, norm_txt, raw_cnt, city, meta in rows:
        combined = f"{norm_txt or ''} {raw_cnt or ''} {city or ''} {meta or ''}"
        
        # 1. Check city / district match
        m_city = city_pattern.search(combined)
        if m_city:
            matched_key = m_city.group(1).lower()
            ref = INDIAN_CITIES_REFERENCE.get(matched_key)
            if ref:
                updated_rows.append((
                    ref["district"],
                    ref["state"],
                    ref["city"],
                    ref["lat"],
                    ref["lon"],
                    "MEDIUM",
                    rid
                ))
                resolved_count += 1
                continue

        # 2. Check state match
        m_state = state_pattern.search(combined)
        if m_state:
            matched_skey = m_state.group(1).lower()
            st_canonical = INDIAN_STATES_REFERENCE.get(matched_skey)
            if st_canonical:
                st_obj = state_obj_map.get(st_canonical.lower())
                updated_rows.append((
                    None,
                    st_canonical,
                    None,
                    st_obj["lat"] if st_obj else None,
                    st_obj["lon"] if st_obj else None,
                    "LOW",
                    rid
                ))
                resolved_count += 1

    print(f"Resolved location provenance for {resolved_count} reports from actual text/metadata evidence.", flush=True)

    if updated_rows:
        cur.executemany("""
            UPDATE weather_reports
            SET location_district = coalesce(location_district, ?),
                location_state = ?,
                location_city = coalesce(location_city, ?),
                location_lat = coalesce(location_lat, ?),
                location_lon = coalesce(location_lon, ?),
                location_confidence = ?
            WHERE id = ?
        """, updated_rows)
        con.commit()
        print(f"Committed updates to skypulse.db. Rows updated: {len(updated_rows)}", flush=True)

    # Check new state breakdown
    cur.execute("SELECT location_state, count(*) FROM weather_reports GROUP BY location_state ORDER BY count(*) DESC")
    print("\nUpdated Weather Reports State Breakdown:", flush=True)
    for row in cur.fetchall():
        print(f"  {row[0] or 'UNRESOLVED (National/General)'}: {row[1]}", flush=True)

if __name__ == "__main__":
    resolve_all()
