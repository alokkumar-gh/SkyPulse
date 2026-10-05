"""
SkyPulse National Coverage & Data Truth Audit Script
Calculates ground truth coverage metrics across all 28 States and 8 Union Territories.
"""

import sqlite3
import json
from collections import defaultdict
from datetime import datetime, timezone
import sys
import os

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectors.weather_discovery.india_locations import INDIA_STATES, INDIA_DISTRICTS

def run_audit():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skypulse.db"))
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # 1. Total counts
    cur.execute("SELECT count(*) FROM weather_reports WHERE is_deleted = 0")
    total_reports = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM weather_events WHERE is_deleted = 0")
    total_events = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM weather_observations")
    total_observations = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM alerts")
    total_alerts = cur.fetchone()[0]

    # Canonical list of 36 states/UTs
    canonical_states = {s["name"]: s for s in INDIA_STATES.values()}

    # Group known districts by state
    known_districts_by_state = defaultdict(dict)
    for d in INDIA_DISTRICTS:
        known_districts_by_state[d["state"]][d["district"]] = {
            "lat": d["lat"],
            "lon": d["lon"]
        }

    # Normalize state aliases
    STATE_ALIASES = {
        "Jammu and Kashmir": "Jammu & Kashmir",
        "Andaman & Nicobar": "Andaman & Nicobar Islands",
        "Dadra and Nagar Haveli and Daman and Diu": "Dadra & Nagar Haveli and Daman & Diu",
    }

    def norm_state(st):
        if not st:
            return None
        st = st.strip()
        return STATE_ALIASES.get(st, st)

    # 2. Gather observations per state & district
    cur.execute("SELECT state, district, count(*), max(observed_at), group_concat(distinct source_name) FROM weather_observations GROUP BY state, district")
    obs_by_state = defaultdict(lambda: {"count": 0, "districts": set(), "latest": None, "sources": set()})
    for st, dist, cnt, latest, srcs in cur.fetchall():
        nst = norm_state(st)
        if not nst: continue
        o = obs_by_state[nst]
        o["count"] += cnt
        if dist: o["districts"].add(dist)
        if not o["latest"] or (latest and latest > o["latest"]): o["latest"] = latest
        if srcs:
            for s in srcs.split(","): o["sources"].add(s.strip())

    # 3. Gather reports per state & district
    cur.execute("SELECT location_state, location_district, count(*), max(ingested_at), group_concat(distinct source_id) FROM weather_reports WHERE is_deleted = 0 GROUP BY location_state, location_district")
    rep_by_state = defaultdict(lambda: {"count": 0, "districts": set(), "latest": None, "sources": set()})
    for st, dist, cnt, latest, srcs in cur.fetchall():
        nst = norm_state(st)
        if not nst: continue
        r = rep_by_state[nst]
        r["count"] += cnt
        if dist: r["districts"].add(dist)
        if not r["latest"] or (latest and latest > r["latest"]): r["latest"] = latest
        if srcs:
            for s in srcs.split(","): r["sources"].add(s.strip())

    # 4. Gather events per state & district
    cur.execute("SELECT primary_state, primary_district, count(*), max(last_updated_at) FROM weather_events WHERE is_deleted = 0 GROUP BY primary_state, primary_district")
    ev_by_state = defaultdict(lambda: {"count": 0, "districts": set(), "latest": None})
    for st, dist, cnt, latest in cur.fetchall():
        nst = norm_state(st)
        if not nst: continue
        e = ev_by_state[nst]
        e["count"] += cnt
        if dist: e["districts"].add(dist)
        if not e["latest"] or (latest and latest > e["latest"]): e["latest"] = latest

    # 5. Gather alerts per state
    cur.execute("SELECT location_state, count(*) FROM alerts GROUP BY location_state")
    al_by_state = defaultdict(int)
    for st, cnt in cur.fetchall():
        nst = norm_state(st)
        if nst: al_by_state[nst] += cnt

    # 6. Build the National Matrix for all 36 States & UTs
    matrix = []
    states_with_telemetry = 0
    total_districts_known_all = 0
    total_districts_active_all = 0

    for st_name in sorted(canonical_states.keys()):
        obs = obs_by_state.get(st_name, {"count": 0, "districts": set(), "latest": None, "sources": set()})
        rep = rep_by_state.get(st_name, {"count": 0, "districts": set(), "latest": None, "sources": set()})
        ev = ev_by_state.get(st_name, {"count": 0, "districts": set(), "latest": None})
        al_cnt = al_by_state.get(st_name, 0)

        known_dists = known_districts_by_state.get(st_name, {})
        total_known = len(known_dists)
        total_districts_known_all += total_known

        # Active districts: union of districts with observations, reports, or events that match known list
        active_dists = set()
        for d in (obs["districts"] | rep["districts"] | ev["districts"]):
            if d in known_dists:
                active_dists.add(d)

        districts_with_data = len(active_dists)
        districts_without_data = max(0, total_known - districts_with_data)
        total_districts_active_all += districts_with_data

        has_data = (obs["count"] > 0 or rep["count"] > 0 or ev["count"] > 0)
        if has_data:
            states_with_telemetry += 1

        all_sources = sorted(list(obs["sources"] | rep["sources"]))

        # District detail listing for UI
        district_status_list = []
        for d_name in sorted(known_dists.keys()):
            is_active = d_name in active_dists
            district_status_list.append({
                "district": d_name,
                "status": "ACTIVE" if is_active else "NO CURRENT TELEMETRY",
                "has_data": is_active,
                "lat": known_dists[d_name]["lat"],
                "lon": known_dists[d_name]["lon"]
            })

        matrix.append({
            "state": st_name,
            "observations_count": obs["count"],
            "reports_count": rep["count"],
            "events_count": ev["count"],
            "alerts_count": al_cnt,
            "total_known_districts": total_known,
            "districts_with_data": districts_with_data,
            "districts_without_data": districts_without_data,
            "latest_observation": obs["latest"],
            "latest_report": rep["latest"],
            "latest_event": ev["latest"],
            "active_sources": all_sources,
            "active_sources_count": len(all_sources),
            "status": "ACTIVE TELEMETRY" if has_data else "NO CURRENT TELEMETRY",
            "districts": district_status_list
        })

    # Category breakdown for reports
    cur.execute("SELECT coalesce(primary_category, 'UNKNOWN'), count(*) FROM weather_reports WHERE is_deleted = 0 GROUP BY primary_category ORDER BY count(*) DESC")
    reports_by_category = dict(cur.fetchall())

    # Source breakdown for reports
    cur.execute("""
        SELECT coalesce(s.name, wr.source_id), count(*)
        FROM weather_reports wr
        LEFT JOIN sources s ON wr.source_id = s.id
        WHERE wr.is_deleted = 0
        GROUP BY wr.source_id
        ORDER BY count(*) DESC
    """)
    reports_by_source = dict(cur.fetchall())

    # Date breakdown for reports
    cur.execute("""
        SELECT substr(ingested_at, 1, 10) as dt, count(*)
        FROM weather_reports
        WHERE is_deleted = 0
        GROUP BY dt
        ORDER BY dt DESC
        LIMIT 10
    """)
    reports_by_date = dict(cur.fetchall())

    output = {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_states": 36,
            "states_with_telemetry": states_with_telemetry,
            "total_known_districts": total_districts_known_all,
            "districts_with_data": total_districts_active_all,
            "total_reports": total_reports,
            "total_events": total_events,
            "total_observations": total_observations,
            "total_alerts": total_alerts,
        },
        "reports_by_category": reports_by_category,
        "reports_by_source": reports_by_source,
        "reports_by_date": reports_by_date,
        "matrix": matrix
    }

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "coverage_audit_results.json"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Audit completed successfully. Summary: {output['summary']}")
    print(f"Results written to: {out_path}")
    return output

if __name__ == "__main__":
    run_audit()
