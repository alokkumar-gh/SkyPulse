import asyncio
from app.db.session import async_session_factory
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.services.weather_intelligence_service import weather_intelligence_service
from sqlalchemy import select, func

async def get_metrics():
    async with async_session_factory() as session:
        raw_count = (await session.execute(select(func.count(WeatherReport.id)))).scalar()
        events_total = (await session.execute(select(func.count(WeatherEvent.id)))).scalar()
        active_events = (await session.execute(select(func.count(WeatherEvent.id)).where(WeatherEvent.is_active == True, WeatherEvent.is_deleted == False))).scalar()
        gps_events = (await session.execute(select(func.count(WeatherEvent.id)).where(
            WeatherEvent.is_active == True, 
            WeatherEvent.is_deleted == False,
            WeatherEvent.centroid_lat.isnot(None), 
            WeatherEvent.centroid_lon.isnot(None)
        ))).scalar()
        no_gps_events = (await session.execute(select(func.count(WeatherEvent.id)).where(
            WeatherEvent.is_active == True, 
            WeatherEvent.is_deleted == False,
            WeatherEvent.centroid_lat.is_(None)
        ))).scalar()
        
        evidence_count = (await session.execute(select(func.count(EventEvidence.id)))).scalar()
        
        # Breakdown of district vs city/station vs regional
        district_events = (await session.execute(select(func.count(WeatherEvent.id)).where(
            WeatherEvent.is_active == True, 
            WeatherEvent.is_deleted == False,
            WeatherEvent.primary_district.isnot(None)
        ))).scalar()
        city_events = (await session.execute(select(func.count(WeatherEvent.id)).where(
            WeatherEvent.is_active == True, 
            WeatherEvent.is_deleted == False,
            WeatherEvent.primary_city.isnot(None)
        ))).scalar()
        
        map_data = await weather_intelligence_service.get_map_data(session)
        cov = await weather_intelligence_service.get_coverage_data(session)
        
        print("=== EXACT DATABASE AUDIT METRICS ===")
        print(f"1. Raw Reports / Signals: {raw_count}")
        print(f"2. Total Weather Events in DB: {events_total}")
        print(f"3. Active Canonical Events: {active_events}")
        print(f"4. Plottable Mapped Incidents (Point GPS): {gps_events}")
        print(f"5. Regional / No-GPS Active Events: {no_gps_events}")
        print(f"6. Active Events with District info: {district_events}")
        print(f"7. Active Events with City info: {city_events}")
        print(f"8. Event Evidence links: {evidence_count}")
        print(f"9. Map API Features: {len(map_data.get('features', []))}")
        print(f"10. National Coverage: States={cov.get('states_covered')}/{cov.get('states_total')}, Districts={cov.get('districts_covered')}/{cov.get('districts_total')}, Stations={cov.get('stations_reporting')}")

if __name__ == '__main__':
    asyncio.run(get_metrics())
