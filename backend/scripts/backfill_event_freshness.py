import sqlite3
import os
from datetime import datetime, timezone

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skypulse.db")
if os.path.exists(db_path):
    con = sqlite3.connect(db_path, timeout=30.0)
    cur = con.cursor()
    
    rows = cur.execute("""
        SELECT id, category, severity, first_reported_at, created_at, last_updated_at, resolved_at, is_active
        FROM weather_events
    """).fetchall()
    
    # Import freshness calculation
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from app.core.freshness_policy import calculate_event_expiry, determine_event_lifecycle_status
    
    now = datetime.now(timezone.utc)
    updated = 0
    for row in rows:
        eid, cat, sev, first_rep, created, last_upd, resolved, is_act = row
        
        # Parse timestamps safely
        def parse_dt(s):
            if not s: return None
            try:
                # Handle formats like '2026-10-04 12:00:00' or ISO
                s = s.replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                return None
                
        dt_obs = parse_dt(first_rep) or now
        dt_ing = parse_dt(created) or now
        dt_seen = parse_dt(last_upd) or dt_obs
        dt_res = parse_dt(resolved)
        
        expires_at = calculate_event_expiry(cat, dt_seen, sev or 1)
        lifecycle = determine_event_lifecycle_status(
            is_active=bool(is_act),
            is_deleted=False,
            resolved_at=dt_res,
            expires_at=expires_at,
            last_seen_at=dt_seen,
            category=cat,
            severity=sev or 1,
            now=now,
        )
        
        cur.execute("""
            UPDATE weather_events
            SET observed_at = ?,
                ingested_at = ?,
                last_seen_at = ?,
                expires_at = ?,
                lifecycle_status = ?
            WHERE id = ?
        """, (dt_obs.isoformat(), dt_ing.isoformat(), dt_seen.isoformat(), expires_at.isoformat(), lifecycle, eid))
        updated += 1
        
    con.commit()
    print(f"Successfully backfilled {updated} events with lifecycle and freshness timestamps!")
    
    # Summary of statuses
    stats = cur.execute("SELECT lifecycle_status, count(*) FROM weather_events GROUP BY lifecycle_status").fetchall()
    print("Lifecycle distribution:", stats)
    con.close()
