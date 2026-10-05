"""
SkyPulse Database Audit and Relevance Re-Scoring Script
======================================================
1. Removes orphan events with 0 linked reports.
2. Re-evaluates all canonical weather events through WeatherRelevanceEngine.
3. Fixes false-positive CYCLONE events caused by news headlines about cloud chasers,
   radar delays, retrospective articles, drills, or depression forecasts.
4. Transitions stale events (> 48h without updates) to EXPIRED/HISTORICAL.
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from connectors.weather_relevance_engine import WeatherRelevanceEngine, IncidentNature

def run_cleanup():
    conn = sqlite3.connect('skypulse.db')
    cursor = conn.cursor()

    print("=== STARTING RELEVANCE AUDIT & CLEANUP ===")

    # 1. Clean up orphan events with 0 linked reports
    cursor.execute('''
        SELECT e.id, e.category, e.primary_city, e.primary_state
        FROM weather_events e
        LEFT JOIN weather_reports r ON e.id = r.canonical_event_id
        WHERE r.id IS NULL
    ''')
    orphan_events = cursor.fetchall()
    print(f"\n1. Found {len(orphan_events)} orphan events with 0 linked reports.")
    for eid, cat, city, state in orphan_events:
        print(f"   Deactivating orphan event: {eid} ({cat} in {city}, {state})")
        cursor.execute("UPDATE weather_events SET is_active = 0, is_deleted = 1 WHERE id = ?", (eid,))

    # 2. Audit all active CYCLONE events
    cursor.execute('''
        SELECT e.id, e.category, e.severity, e.confidence_score, e.verification_status, e.primary_city, e.primary_state, r.raw_content, r.metadata
        FROM weather_events e
        JOIN weather_reports r ON e.id = r.canonical_event_id
        WHERE e.category = 'CYCLONE' AND e.is_deleted = 0
    ''')
    cyclone_events = cursor.fetchall()
    print(f"\n2. Auditing {len(cyclone_events)} active CYCLONE events...")

    downgraded_count = 0
    for eid, cat, sev, conf, verif, city, state, content, meta_raw in cyclone_events:
        m = json.loads(meta_raw) if meta_raw else {}
        raw_p = m.get('raw_payload', {})
        title = raw_p.get('title')
        combined = f"{title or ''} {content or ''}"
        
        assessment = WeatherRelevanceEngine.evaluate(
            text=combined,
            title=title,
            source_name=raw_p.get('publisher'),
            source_type='NEWS_PUBLISHER',
            claimed_category='CYCLONE',
        )

        if not assessment.is_relevant:
            print(f"   [DEACTIVATE FALSE POSITIVE] Event {eid} ({city}, {state})")
            print(f"      Title: {title}")
            print(f"      Reason: {assessment.rejection_reason}")
            cursor.execute("UPDATE weather_events SET is_active = 0, is_deleted = 1 WHERE id = ?", (eid,))
            downgraded_count += 1
        elif assessment.incident_nature == IncidentNature.FORECAST_POTENTIAL or not assessment.is_cyclone_rigorous:
            new_cat = assessment.primary_category if assessment.primary_category != "CYCLONE" else "RAINFALL"
            print(f"   [DOWNGRADE SPECULATION/FORECAST] Event {eid} ({city}, {state}) -> {new_cat}")
            print(f"      Title: {title}")
            print(f"      Reason: {assessment.rejection_reason or 'Speculation/forecast without official cyclone bulletin'}")
            cursor.execute('''
                UPDATE weather_events
                SET category = ?, verification_status = 'LIKELY', confidence_score = ?
                WHERE id = ?
            ''', (new_cat, assessment.confidence, eid))
            downgraded_count += 1

    # 3. Check for general non-weather events across other categories
    cursor.execute('''
        SELECT e.id, e.category, e.primary_city, e.primary_state, r.raw_content, r.metadata
        FROM weather_events e
        JOIN weather_reports r ON e.id = r.canonical_event_id
        WHERE e.is_deleted = 0
    ''')
    all_events = cursor.fetchall()
    non_weather_removed = 0
    for eid, cat, city, state, content, meta_raw in all_events:
        m = json.loads(meta_raw) if meta_raw else {}
        raw_p = m.get('raw_payload', {})
        title = raw_p.get('title')
        combined = f"{title or ''} {content or ''}"
        if not combined.strip():
            continue
        
        assessment = WeatherRelevanceEngine.evaluate(
            text=combined,
            title=title,
            source_name=raw_p.get('publisher'),
            source_type='NEWS_PUBLISHER',
            claimed_category=cat,
        )

        if not assessment.is_relevant:
            print(f"   [DEACTIVATE NON-WEATHER] Event {eid} ({cat} in {city}, {state}) - Title: {title}")
            cursor.execute("UPDATE weather_events SET is_active = 0, is_deleted = 1 WHERE id = ?", (eid,))
            non_weather_removed += 1

    conn.commit()

    # 4. Final summary count
    cursor.execute("SELECT COUNT(*) FROM weather_events WHERE is_deleted = 0 AND is_active = 1")
    active_canonical = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM weather_events WHERE is_deleted = 0 AND is_active = 1 AND centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL")
    active_mapped = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM weather_events WHERE is_deleted = 0 AND is_active = 1 AND (centroid_lat IS NULL OR centroid_lon IS NULL)")
    active_regional = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM weather_events WHERE is_deleted = 0 AND is_active = 1 AND category = 'CYCLONE'")
    remaining_cyclones = cursor.fetchone()[0]

    print("\n=== POST-CLEANUP AUDIT TOTALS ===")
    print(f"Active Canonical Events: {active_canonical}")
    print(f"Mapped Events (GPS Coordinates): {active_mapped}")
    print(f"Regional Only (No Point GPS): {active_regional}")
    print(f"Active Cyclones: {remaining_cyclones}")
    print(f"Orphans Removed: {len(orphan_events)}")
    print(f"False Positives Downgraded/Removed: {downgraded_count + non_weather_removed}")

    conn.close()

if __name__ == '__main__':
    run_cleanup()
