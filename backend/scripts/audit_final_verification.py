import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, or_
from app.db.session import async_session_factory
from app.models.weather_observation import WeatherObservation
from app.models.weather_event import WeatherEvent
from app.models.source import Source
from connectors.weather_discovery.india_locations import INDIA_DISTRICTS, INDIA_STATES
from connectors.openmeteo_connector import DEFAULT_INDIAN_LOCATIONS

async def main():
    async with async_session_factory() as db:
        # 1. Open-Meteo coordinate count
        openmeteo_coord_count = len(DEFAULT_INDIAN_LOCATIONS)
        
        # 2. Location catalog counts
        district_catalog_count = len(INDIA_DISTRICTS)
        city_catalog_count = 80
        
        # 3. Database observation records
        stmt_obs_count = select(func.count(WeatherObservation.id))
        total_obs = (await db.execute(stmt_obs_count)).scalar() or 0
        
        stmt_district_obs = select(func.count(WeatherObservation.id)).where(WeatherObservation.observation_type == "DISTRICT_OBSERVATION")
        district_obs_count = (await db.execute(stmt_district_obs)).scalar() or 0
        
        stmt_city_obs = select(func.count(WeatherObservation.id)).where(WeatherObservation.observation_type == "CITY_OBSERVATION")
        city_obs_count = (await db.execute(stmt_city_obs)).scalar() or 0
        
        stmt_station_obs = select(func.count(WeatherObservation.id)).where(WeatherObservation.observation_type == "STATION_OBSERVATION")
        station_obs_count = (await db.execute(stmt_station_obs)).scalar() or 0
        
        # 4. Reporting stations / active sources
        stmt_stations = select(func.count(Source.id)).where(Source.is_active == True)
        stations_reporting = (await db.execute(stmt_stations)).scalar() or 0
        
        # 5. Events counts
        stmt_active_events = select(func.count(WeatherEvent.id)).where(WeatherEvent.is_active == True)
        active_events = (await db.execute(stmt_active_events)).scalar() or 0
        
        stmt_mapped = select(func.count(WeatherEvent.id)).where(
            WeatherEvent.is_active == True,
            WeatherEvent.centroid_lat.isnot(None),
            WeatherEvent.centroid_lon.isnot(None)
        )
        mapped_events = (await db.execute(stmt_mapped)).scalar() or 0
        
        stmt_regional = select(func.count(WeatherEvent.id)).where(
            WeatherEvent.is_active == True,
            (WeatherEvent.centroid_lat.is_(None) | WeatherEvent.centroid_lon.is_(None))
        )
        regional_events = (await db.execute(stmt_regional)).scalar() or 0
        
        # 6. Specific requested locations check
        target_locations = [
            ("Khordha", ["Khordha", "Khurda"]),
            ("Bhubaneswar", ["Bhubaneswar"]),
            ("Puri", ["Puri"]),
            ("Cuttack", ["Cuttack"]),
            ("Mumbai", ["Mumbai"]),
            ("Pune", ["Pune"]),
            ("Delhi", ["Delhi"]),
            ("Bengaluru", ["Bengaluru", "Bangalore"]),
            ("Chennai", ["Chennai"]),
            ("Kolkata", ["Kolkata"]),
            ("Guwahati", ["Guwahati", "Kamrup", "Dispur"]),
        ]
        
        location_data = {}
        for label, search_terms in target_locations:
            conditions = []
            for t in search_terms:
                conditions.append(WeatherObservation.district.ilike(f"%{t}%"))
                conditions.append(WeatherObservation.city.ilike(f"%{t}%"))
            stmt = select(WeatherObservation).where(or_(*conditions)).limit(1)
            res = (await db.execute(stmt)).scalars().first()
            if res:
                location_data[label] = {
                    "id": str(res.id),
                    "type": res.observation_type,
                    "district": res.district,
                    "city": res.city,
                    "state": res.state,
                    "lat": res.latitude,
                    "lon": res.longitude,
                    "temp_c": res.temperature_c,
                    "humidity": res.humidity_percent,
                    "rain_mm": res.rain_mm,
                    "wind_speed_kmh": res.wind_speed_kmh,
                    "weather_code": res.weather_code,
                    "source": res.source_name,
                    "observed_at": res.observed_at.isoformat() if res.observed_at else None
                }
            else:
                location_data[label] = "NOT_FOUND"

        print(json.dumps({
            "openmeteo_coord_count": openmeteo_coord_count,
            "district_catalog_count": district_catalog_count,
            "city_catalog_count": city_catalog_count,
            "total_observations": total_obs,
            "district_observations": district_obs_count,
            "city_observations": city_obs_count,
            "station_observations": station_obs_count,
            "stations_reporting": stations_reporting,
            "active_events": active_events,
            "mapped_events": mapped_events,
            "regional_events": regional_events,
            "target_locations": location_data
        }, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
