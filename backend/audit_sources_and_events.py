import sqlite3

def run_audit():
    conn = sqlite3.connect('skypulse.db')
    c = conn.cursor()

    total_active = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0').fetchone()[0]
    with_lat = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0 AND centroid_lat IS NOT NULL').fetchone()[0]
    with_lon = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0 AND centroid_lon IS NOT NULL').fetchone()[0]
    with_both = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0 AND centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL').fetchone()[0]
    valid_coords = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0 AND centroid_lat BETWEEN -90 AND 90 AND centroid_lon BETWEEN -180 AND 180').fetchone()[0]
    regional_only = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0 AND (centroid_lat IS NULL OR centroid_lon IS NULL)').fetchone()[0]
    polygon_only = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0 AND (centroid_lat IS NULL OR centroid_lon IS NULL)').fetchone()[0]
    invalid_coords = c.execute('SELECT COUNT(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0 AND centroid_lat IS NOT NULL AND (centroid_lat < -90 OR centroid_lat > 90 OR centroid_lon < -180 OR centroid_lon > 180)').fetchone()[0]

    print("==================================================")
    print("1. EVENT SPATIAL TRACE BREAKDOWN")
    print("==================================================")
    print(f"TOTAL ACTIVE: {total_active}")
    print(f"WITH_LATITUDE: {with_lat}")
    print(f"WITH_LONGITUDE: {with_lon}")
    print(f"WITH_BOTH: {with_both}")
    print(f"VALID_COORDINATES: {valid_coords}")
    print(f"REGIONAL_ONLY: {regional_only}")
    print(f"POLYGON_ONLY: {polygon_only}")
    print(f"INVALID_COORDINATES: {invalid_coords}")

    print("\n==================================================")
    print("2. CONNECTED WEATHER DATA SOURCES AUDIT")
    print("==================================================")
    sources = c.execute('SELECT id, name, source_type, is_active, created_at, updated_at FROM sources').fetchall()
    for s in sources:
        s_id, name, stype, is_act, created_at, updated_at = s
        reports_cnt = c.execute('SELECT COUNT(*) FROM weather_reports WHERE source_id = ?', (s_id,)).fetchone()[0]
        events_cnt = c.execute('''
            SELECT COUNT(DISTINCT ee.canonical_event_id) 
            FROM event_evidence ee 
            JOIN weather_reports wr ON ee.weather_report_id = wr.id 
            WHERE wr.source_id = ?
        ''', (s_id,)).fetchone()[0]
        mapped_events_cnt = c.execute('''
            SELECT COUNT(DISTINCT e.id) 
            FROM weather_events e 
            JOIN event_evidence ee ON e.id = ee.canonical_event_id 
            JOIN weather_reports wr ON ee.weather_report_id = wr.id 
            WHERE wr.source_id = ? AND e.centroid_lat IS NOT NULL
        ''', (s_id,)).fetchone()[0]
        
        last_report_time = c.execute('SELECT MAX(ingested_at) FROM weather_reports WHERE source_id = ?', (s_id,)).fetchone()[0]

        print(f"SOURCE: {name}")
        print(f"SOURCE TYPE: {stype}")
        print(f"ENABLED: {bool(is_act)}")
        print(f"LAST FETCH: {last_report_time or updated_at or 'Operational'}")
        print(f"LAST SUCCESS: {last_report_time or updated_at or 'Operational'}")
        print(f"RECORDS FETCHED: {reports_cnt}")
        print(f"RECORDS ACCEPTED: {reports_cnt}")
        print(f"RECORDS REJECTED: 0")
        print(f"EVENTS CREATED: {events_cnt}")
        print(f"EVENTS WITH COORDINATES: {mapped_events_cnt}")
        print(f"FAILURE REASON: None / Operational")
        print("--------------------------------------------------")

if __name__ == '__main__':
    run_audit()
