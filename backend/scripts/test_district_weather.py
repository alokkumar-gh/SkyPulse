import asyncio
from app.db.session import async_session_factory
from app.services.district_weather_service import district_weather_service

async def test_fetch():
    async with async_session_factory() as session:
        res = await district_weather_service.refresh_all_districts(session)
        print("=== DISTRICT REFRESH RESULT ===")
        print(res)
        
        dist_list = await district_weather_service.get_district_weather_list(session)
        print(f"Total district observation records retrieved: {len(dist_list)}")
        
        # Test specific cities
        test_cities = ["Khordha", "Bhubaneswar", "Puri", "Cuttack", "Mumbai", "Pune", "New Delhi", "Bengaluru", "Chennai", "Kolkata", "Guwahati"]
        for tc in test_cities:
            match = [d for d in dist_list if (d.get("district_name") and tc.lower() in d["district_name"].lower()) or (d.get("city") and tc.lower() in d["city"].lower())]
            if match:
                m = match[0]
                w = m["weather"]
                s = m["source"]
                print(f"- {tc}: Temp={w['temperature_c']}°C, Condition={w['weather_condition']}, Rain={w['rain_mm']}mm, Wind={w['wind_speed_kmh']}km/h, Source={s['provider']} ({s['model']})")
            else:
                print(f"- {tc}: Not found in district list")

if __name__ == "__main__":
    asyncio.run(test_fetch())
