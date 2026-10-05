"""
SkyPulse District & City Weather Observation Service
====================================================
Maintains authoritative nationwide meteorological observation telemetry across:
- All 36 Indian States and Union Territories
- Authoritative Indian district centroids (~250+ districts across all states)
- Major Indian cities & automated stations

Separates Routine Weather Observations from Severe Weather Incidents:
- Routine Observations: continuous physical measurements (temperature, humidity,
  precipitation, wind, pressure, WMO code) from Open-Meteo & IMD stations.
- Incidents: only significant weather hazards (Rainfall warnings, Thunderstorms, Floods).

Uses Open-Meteo multi-coordinate batching to fetch real-time weather across
monitoring locations in grouped requests with caching and retry logic.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather_observation import WeatherObservation
from app.models.weather_event import WeatherEvent
from app.core.freshness_policy import (
    get_observation_freshness_category,
    format_freshness_label,
    OBSERVATION_FRESHNESS_TIERS,
)
from app.core.websocket_manager import ws_manager, build_event_envelope
from connectors.weather_discovery.india_locations import (
    INDIA_STATES,
    INDIA_DISTRICTS,
    HIGH_PRIORITY_LOCATIONS,
    lookup_location,
)

logger = logging.getLogger("skypulse.services.district_weather")

WMO_DESCRIPTION_MAP: Dict[int, Tuple[str, str]] = {
    0: ("Clear Sky", "☀️"),
    1: ("Mainly Clear", "🌤️"),
    2: ("Partly Cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Depositing Rime Fog", "🌫️"),
    51: ("Light Drizzle", "🌦️"),
    53: ("Moderate Drizzle", "🌧️"),
    55: ("Dense Drizzle", "🌧️"),
    61: ("Slight Rain", "🌧️"),
    63: ("Moderate Rain", "🌧️"),
    65: ("Heavy Rain", "🌧️"),
    71: ("Slight Snow", "🌨️"),
    73: ("Moderate Snow", "🌨️"),
    75: ("Heavy Snow", "❄️"),
    80: ("Slight Rain Showers", "🌦️"),
    81: ("Moderate Rain Showers", "🌧️"),
    82: ("Violent Rain Showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with Hail", "⛈️"),
    99: ("Severe Thunderstorm", "⛈️"),
}


class DistrictWeatherService:
    """
    Manages district and city weather observation telemetry.
    """

    BATCH_SIZE = 50
    CACHE_TTL_SECONDS = 600  # 10 minutes cache
    _cache: Dict[str, Any] = {}
    _last_fetch_time: Optional[float] = None

    @classmethod
    def get_wmo_info(cls, code: Optional[int]) -> Tuple[str, str]:
        if code is None:
            return ("Fair", "⛅")
        return WMO_DESCRIPTION_MAP.get(code, (f"WMO {code}", "⛅"))

    @classmethod
    async def fetch_batch_weather(
        cls, locations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Executes a multi-coordinate batch request to Open-Meteo forecast API.
        """
        if not locations:
            return []

        lats = ",".join(str(loc["lat"]) for loc in locations)
        lons = ",".join(str(loc["lon"]) for loc in locations)

        params = {
            "latitude": lats,
            "longitude": lons,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,rain,showers,weather_code,cloud_cover,"
                "surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
            ),
            "timezone": "auto",
        }

        url = "https://api.open-meteo.com/v1/forecast"
        headers = {
            "User-Agent": "SkyPulse-NationalWeatherAnalytics/1.0 (+https://skypulse.gov.in)",
            "Accept": "application/json",
        }

        results = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    # Open-Meteo returns a list of result objects if multiple coordinates requested
                    if isinstance(data, list):
                        for i, item in enumerate(data):
                            loc = locations[i]
                            curr = item.get("current", {})
                            results.append({
                                "loc": loc,
                                "current": curr,
                                "elevation": item.get("elevation"),
                            })
                    elif isinstance(data, dict) and "current" in data:
                        results.append({
                            "loc": locations[0],
                            "current": data.get("current", {}),
                            "elevation": data.get("elevation"),
                        })
                else:
                    logger.warning("Open-Meteo batch request returned HTTP %d", resp.status_code)
        except Exception as e:
            logger.error("Open-Meteo batch request failed: %s", e)

        return results

    @classmethod
    async def refresh_all_districts(cls, db: AsyncSession) -> Dict[str, Any]:
        """
        Fetches fresh real-time observations for all districts and key cities across India.
        Enforces Section 25 rule: Never overwrite newer data with an older observation.
        Broadcasts WEATHER_OBSERVATION_UPDATED via WebSocket upon completion.
        """
        now = time.time()
        # Compile unique locations (districts + state capitals + key cities)
        target_locations: List[Dict[str, Any]] = []
        seen_coords = set()

        # 1. All District Centroids
        for d in INDIA_DISTRICTS:
            coord_key = (round(d["lat"], 3), round(d["lon"], 3))
            if coord_key not in seen_coords:
                seen_coords.add(coord_key)
                target_locations.append({
                    "district": d["district"],
                    "city": d.get("city") or d["district"],
                    "state": d["state"],
                    "lat": d["lat"],
                    "lon": d["lon"],
                    "type": "DISTRICT_OBSERVATION",
                })

        # 2. State & UT Capitals
        for k, v in INDIA_STATES.items():
            coord_key = (round(v["lat"], 3), round(v["lon"], 3))
            if coord_key not in seen_coords:
                seen_coords.add(coord_key)
                target_locations.append({
                    "district": v.get("capital") or v["name"],
                    "city": v.get("capital"),
                    "state": v["name"],
                    "lat": v["lat"],
                    "lon": v["lon"],
                    "type": "CITY_OBSERVATION",
                })

        total_targets = len(target_locations)
        records_saved = 0
        batches_count = (total_targets + cls.BATCH_SIZE - 1) // cls.BATCH_SIZE
        failed_batches = 0

        obs_time = datetime.now(timezone.utc)
        broadcast_samples: List[Dict[str, Any]] = []

        # Pre-query latest observed_at timestamp per district to avoid older data overwriting newer data (Section 25)
        latest_times_q = select(
            WeatherObservation.state,
            WeatherObservation.district,
            func.max(WeatherObservation.observed_at).label("max_obs")
        ).group_by(WeatherObservation.state, WeatherObservation.district)
        latest_res = await db.execute(latest_times_q)
        latest_obs_map: Dict[Tuple[str, str], datetime] = {}
        for row in latest_res.all():
            m_obs = row.max_obs
            if m_obs:
                if m_obs.tzinfo is None:
                    m_obs = m_obs.replace(tzinfo=timezone.utc)
                latest_obs_map[(row.state, row.district or "")] = m_obs

        for b_idx in range(batches_count):
            batch_locs = target_locations[b_idx * cls.BATCH_SIZE : (b_idx + 1) * cls.BATCH_SIZE]
            batch_res = await cls.fetch_batch_weather(batch_locs)
            if not batch_res:
                failed_batches += 1
                continue

            for item in batch_res:
                loc = item["loc"]
                curr = item["current"]
                if not curr:
                    continue

                state_name = loc["state"]
                dist_name = loc["district"]
                prev_obs = latest_obs_map.get((state_name, dist_name or ""))

                # Section 25: Do not overwrite newer observation with an older one
                if prev_obs and obs_time < prev_obs:
                    logger.debug(
                        "Skipping older observation for %s, %s (incoming %s < existing %s)",
                        dist_name, state_name, obs_time, prev_obs
                    )
                    continue

                w_code = curr.get("weather_code")
                cond_text, cond_icon = cls.get_wmo_info(w_code)

                obs = WeatherObservation(
                    source_name="Open-Meteo",
                    source_model="ECMWF / GFS Real-Time Seamless",
                    observation_type=loc.get("type", "DISTRICT_OBSERVATION"),
                    state=state_name,
                    district=dist_name,
                    city=loc.get("city"),
                    latitude=loc["lat"],
                    longitude=loc["lon"],
                    observed_at=obs_time,
                    temperature_c=curr.get("temperature_2m"),
                    apparent_temperature_c=curr.get("apparent_temperature"),
                    humidity_percent=curr.get("relative_humidity_2m"),
                    precipitation_mm=curr.get("precipitation"),
                    rain_mm=curr.get("rain"),
                    showers_mm=curr.get("showers"),
                    wind_speed_kmh=curr.get("wind_speed_10m"),
                    wind_direction_deg=curr.get("wind_direction_10m"),
                    wind_gust_kmh=curr.get("wind_gusts_10m"),
                    pressure_hpa=curr.get("surface_pressure"),
                    cloud_cover_percent=curr.get("cloud_cover"),
                    weather_code=w_code,
                    weather_condition=f"{cond_icon} {cond_text}",
                )
                db.add(obs)
                records_saved += 1

                if len(broadcast_samples) < 30:
                    broadcast_samples.append({
                        "district": dist_name,
                        "state": state_name,
                        "city": loc.get("city"),
                        "temperature_c": obs.temperature_c,
                        "humidity_percent": obs.humidity_percent,
                        "rain_mm": obs.rain_mm or obs.precipitation_mm or 0.0,
                        "wind_speed_kmh": obs.wind_speed_kmh,
                        "pressure_hpa": obs.pressure_hpa,
                        "weather_condition": cond_text,
                        "weather_icon": cond_icon,
                        "observed_at": obs_time.isoformat(),
                        "freshness_category": "LIVE",
                        "freshness_label": "Observed just now",
                    })

            # Brief pause to respect API rate-limits
            await asyncio.sleep(0.10)

        if records_saved > 0:
            await db.commit()
            cls._last_fetch_time = now

            # Broadcast real-time WEATHER_OBSERVATION_UPDATED over WebSocket bus
            try:
                now_iso = obs_time.isoformat()
                ws_envelope = build_event_envelope(
                    event_type="WEATHER_OBSERVATION_UPDATED",
                    event_id=f"obs-batch-{int(now)}",
                    data={
                        "total_updated": records_saved,
                        "observed_at": now_iso,
                        "server_time": now_iso,
                        "sample_districts": broadcast_samples,
                        "provider": "Open-Meteo Seamless Telemetry",
                    },
                )
                ws_envelope["legacy_type"] = "weather_observation.updated"
                ws_envelope["server_time"] = now_iso
                ws_envelope["revision"] = int(datetime.now(timezone.utc).timestamp() * 1000)
                await ws_manager.broadcast(ws_envelope)
                logger.info("Broadcasted WEATHER_OBSERVATION_UPDATED for %d districts", records_saved)
            except Exception as ws_err:
                logger.warning("Failed to broadcast weather observation update: %s", ws_err)

        return {
            "total_locations": total_targets,
            "batches_executed": batches_count,
            "failed_batches": failed_batches,
            "records_persisted": records_saved,
            "observed_at": obs_time.isoformat(),
        }

    @classmethod
    async def get_district_weather_list(
        cls, db: AsyncSession, state: Optional[str] = None, district: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the latest weather observation for every district, along with active hazard status
        and server-authoritative freshness calculations.
        """
        # If table is empty, trigger initial refresh
        count_q = select(func.count(WeatherObservation.id))
        res = await db.execute(count_q)
        cnt = res.scalar() or 0
        if cnt == 0:
            await cls.refresh_all_districts(db)

        # Query observations directly ordered by state, district, observed_at desc
        q = select(WeatherObservation).order_by(
            WeatherObservation.state,
            WeatherObservation.district,
            WeatherObservation.observed_at.desc()
        ).limit(500)
        if state:
            q = q.where(WeatherObservation.state.ilike(f"%{state}%"))
        if district:
            q = q.where(WeatherObservation.district.ilike(f"%{district}%"))

        q_res = await db.execute(q)
        all_obs = q_res.scalars().all()

        # Deduplicate to latest observation per state + district
        seen_keys = set()
        obs_records = []
        for o in all_obs:
            key = ((o.state or "").upper(), (o.district or o.city or "").upper())
            if key not in seen_keys:
                seen_keys.add(key)
                obs_records.append(o)

        # Query active, unexpired incidents per district to link hazard state
        now_utc = datetime.now(timezone.utc)
        incident_by_district: Dict[str, List[Dict[str, Any]]] = {}
        try:
            inc_q = select(WeatherEvent).where(
                WeatherEvent.is_active == True,
                WeatherEvent.is_deleted == False
            )
            inc_res = await db.execute(inc_q)
            for inc in inc_res.scalars().all():
                if getattr(inc, "lifecycle_status", "ACTIVE") != "EXPIRED":
                    d_key = f"{inc.primary_state or ''}_{inc.primary_district or inc.primary_city or ''}".lower()
                    if d_key not in incident_by_district:
                        incident_by_district[d_key] = []
                    incident_by_district[d_key].append({
                        "id": str(inc.id),
                        "category": inc.category,
                        "severity": inc.severity,
                        "verification_status": inc.verification_status,
                        "confidence_score": inc.confidence_score,
                        "lifecycle_status": getattr(inc, "effective_lifecycle_status", "ACTIVE"),
                        "observed_at": inc.effective_observed_at.isoformat() if inc.effective_observed_at else None,
                        "expires_at": inc.effective_expires_at.isoformat() if inc.effective_expires_at else None,
                    })
        except Exception as inc_err:
            logger.warning("Active incidents linking warning: %s", inc_err)

        output = []
        for o in obs_records:
            d_key = f"{o.state}_{o.district or ''}".lower()
            matching_incidents = incident_by_district.get(d_key, [])
            cond_desc, cond_icon = cls.get_wmo_info(o.weather_code)

            obs_dt = o.observed_at
            if obs_dt and obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)

            freshness_cat, _ = get_observation_freshness_category(obs_dt, now_utc)
            freshness_lbl = format_freshness_label(obs_dt, now_utc)

            output.append({
                "district_id": str(o.id),
                "district_name": o.district or o.city or "Unknown",
                "city": o.city,
                "state": o.state,
                "latitude": o.latitude,
                "longitude": o.longitude,
                "observation_type": o.observation_type,
                "weather": {
                    "temperature_c": o.temperature_c,
                    "apparent_temperature_c": o.apparent_temperature_c,
                    "humidity_percent": o.humidity_percent,
                    "precipitation_mm": o.precipitation_mm,
                    "rain_mm": o.rain_mm,
                    "wind_speed_kmh": o.wind_speed_kmh,
                    "wind_direction_deg": o.wind_direction_deg,
                    "wind_gust_kmh": o.wind_gust_kmh,
                    "pressure_hpa": o.pressure_hpa,
                    "cloud_cover_percent": o.cloud_cover_percent,
                    "weather_code": o.weather_code,
                    "weather_condition": cond_desc,
                    "weather_icon": cond_icon,
                    "observed_at": obs_dt.isoformat() if obs_dt else None,
                    "freshness_category": freshness_cat,
                    "freshness_label": freshness_lbl,
                },
                "source": {
                    "provider": o.source_name,
                    "model": o.source_model,
                    "provenance": "Operational Model Telemetry (Open-Meteo)",
                },
                "warning_status": "ACTIVE_INCIDENT" if matching_incidents else "NORMAL",
                "active_incidents": matching_incidents,
            })

        return output

    @classmethod
    async def get_map_observations_layer(
        cls, db: AsyncSession, zoom: int = 5
    ) -> Dict[str, Any]:
        """
        Returns GeoJSON FeatureCollection of weather observations for map rendering.
        Visual style: subtle neutral weather chips (e.g. 29°C ⛅), visually separated from
        large colored severe weather incident pins.
        Includes authoritative server_time and freshness metrics.
        """
        districts = await cls.get_district_weather_list(db)
        features = []
        now_utc = datetime.now(timezone.utc)

        for d in districts:
            w = d["weather"]
            temp_str = f"{round(w['temperature_c'])}°C" if w["temperature_c"] is not None else "--"
            cond_icon = w.get("weather_icon", "⛅")

            features.append({
                "type": "Feature",
                "id": f"obs-{d['district_id']}",
                "geometry": {
                    "type": "Point",
                    "coordinates": [d["longitude"], d["latitude"]],
                },
                "properties": {
                    "id": d["district_id"],
                    "name": d["district_name"],
                    "city": d["city"],
                    "state": d["state"],
                    "temperature_c": w["temperature_c"],
                    "apparent_temperature_c": w.get("apparent_temperature_c"),
                    "temp_label": temp_str,
                    "weather_icon": cond_icon,
                    "condition": w["weather_condition"],
                    "humidity_percent": w["humidity_percent"],
                    "rain_mm": w["rain_mm"] or w["precipitation_mm"] or 0.0,
                    "precipitation_mm": w.get("precipitation_mm", 0.0),
                    "wind_speed_kmh": w["wind_speed_kmh"],
                    "wind_direction_deg": w.get("wind_direction_deg"),
                    "wind_gust_kmh": w.get("wind_gust_kmh"),
                    "pressure_hpa": w.get("pressure_hpa"),
                    "cloud_cover_percent": w.get("cloud_cover_percent"),
                    "source": d["source"]["provider"],
                    "model": d["source"]["model"],
                    "observed_at": w["observed_at"],
                    "freshness_category": w.get("freshness_category", "LIVE"),
                    "freshness_label": w.get("freshness_label", "LIVE"),
                    "server_time": now_utc.isoformat(),
                    "warning_status": d["warning_status"],
                    "incident_count": len(d["active_incidents"]),
                    "layer_type": "WEATHER_OBSERVATION",
                },
            })

        return {
            "type": "FeatureCollection",
            "layer": "DISTRICT_WEATHER_OBSERVATIONS",
            "total_observations": len(features),
            "server_time": now_utc.isoformat(),
            "zoom": zoom,
            "features": features,
        }

    @classmethod
    async def get_location_fallback_telemetry(
        cls,
        db: AsyncSession,
        state: Optional[str] = None,
        district: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Implements Requirements 20 & 22 (News -> Weather Fallback):
        PRIORITY 1: Fresh canonical severe weather event / news
        PRIORITY 2: Latest valid weather observation
        PRIORITY 3: Honest NO CURRENT TELEMETRY (no black panel, no fabricated event)
        """
        now_utc = datetime.now(timezone.utc)

        # 1. PRIORITY 1: Check for active, fresh weather event
        event_q = select(WeatherEvent).where(
            WeatherEvent.is_active == True,
            WeatherEvent.is_deleted == False
        )
        if state:
            event_q = event_q.where(WeatherEvent.primary_state.ilike(f"%{state}%"))
        if district:
            event_q = event_q.where(
                (WeatherEvent.primary_district.ilike(f"%{district}%")) |
                (WeatherEvent.primary_city.ilike(f"%{district}%"))
            )
        event_q = event_q.order_by(desc(WeatherEvent.severity), desc(WeatherEvent.observed_at)).limit(5)
        ev_res = await db.execute(event_q)
        events = ev_res.scalars().all()

        active_events = [e for e in events if e.effective_lifecycle_status != "EXPIRED"]
        if active_events:
            top_ev = active_events[0]
            obs_dt = top_ev.effective_observed_at
            return {
                "telemetry_type": "EVENT",
                "headline": f"{top_ev.category} Alert",
                "state": top_ev.primary_state,
                "district": top_ev.primary_district or top_ev.primary_city,
                "event": {
                    "id": str(top_ev.id),
                    "category": top_ev.category,
                    "severity": top_ev.severity,
                    "confidence_score": top_ev.confidence_score,
                    "verification_status": top_ev.verification_status,
                    "lifecycle_status": top_ev.effective_lifecycle_status,
                    "observed_at": obs_dt.isoformat() if obs_dt else None,
                    "expires_at": top_ev.effective_expires_at.isoformat() if top_ev.effective_expires_at else None,
                    "freshness_label": format_freshness_label(obs_dt, now_utc),
                },
                "observation": None,
                "has_telemetry": True,
                "server_time": now_utc.isoformat(),
            }

        # 2. PRIORITY 2: Fall back to latest valid meteorological observation
        obs_q = select(WeatherObservation)
        if state:
            obs_q = obs_q.where(WeatherObservation.state.ilike(f"%{state}%"))
        if district:
            obs_q = obs_q.where(
                (WeatherObservation.district.ilike(f"%{district}%")) |
                (WeatherObservation.city.ilike(f"%{district}%"))
            )
        obs_q = obs_q.order_by(desc(WeatherObservation.observed_at)).limit(1)
        obs_res = await db.execute(obs_q)
        latest_obs = obs_res.scalar_one_or_none()

        if latest_obs:
            cond_desc, cond_icon = cls.get_wmo_info(latest_obs.weather_code)
            obs_dt = latest_obs.observed_at
            if obs_dt and obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)
            freshness_cat, _ = get_observation_freshness_category(obs_dt, now_utc)
            freshness_lbl = format_freshness_label(obs_dt, now_utc)

            return {
                "telemetry_type": "OBSERVATION",
                "headline": "Current Weather Telemetry",
                "state": latest_obs.state,
                "district": latest_obs.district or latest_obs.city,
                "event": None,
                "observation": {
                    "id": str(latest_obs.id),
                    "district": latest_obs.district,
                    "city": latest_obs.city,
                    "state": latest_obs.state,
                    "latitude": latest_obs.latitude,
                    "longitude": latest_obs.longitude,
                    "temperature_c": latest_obs.temperature_c,
                    "apparent_temperature_c": latest_obs.apparent_temperature_c,
                    "humidity_percent": latest_obs.humidity_percent,
                    "rain_mm": latest_obs.rain_mm or latest_obs.precipitation_mm or 0.0,
                    "precipitation_mm": latest_obs.precipitation_mm or 0.0,
                    "wind_speed_kmh": latest_obs.wind_speed_kmh,
                    "wind_direction_deg": latest_obs.wind_direction_deg,
                    "wind_gust_kmh": latest_obs.wind_gust_kmh,
                    "pressure_hpa": latest_obs.pressure_hpa,
                    "cloud_cover_percent": latest_obs.cloud_cover_percent,
                    "weather_condition": cond_desc,
                    "weather_icon": cond_icon,
                    "source": latest_obs.source_name,
                    "model": latest_obs.source_model,
                    "observed_at": obs_dt.isoformat() if obs_dt else None,
                    "freshness_category": freshness_cat,
                    "freshness_label": freshness_lbl,
                },
                "has_telemetry": True,
                "server_time": now_utc.isoformat(),
            }

        # 3. PRIORITY 3: Honest NO CURRENT TELEMETRY state
        return {
            "telemetry_type": "NO_TELEMETRY",
            "headline": "No Current Telemetry",
            "state": state,
            "district": district or city,
            "event": None,
            "observation": None,
            "has_telemetry": False,
            "server_time": now_utc.isoformat(),
            "message": f"No active weather events or routine station observations available for {district or state or 'selected location'}.",
        }


district_weather_service = DistrictWeatherService()
