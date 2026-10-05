import asyncio
import sys
sys.path.insert(0, '.')
from app.db.session import async_session_factory
from app.services.weather_intelligence_service import weather_intelligence_service

async def test():
    async with async_session_factory() as session:
        print("=== TESTING GET_MAP_DATA MULTI-LAYER & TIME FILTERS ===")
        for w in ['live', '1h', '6h', '24h', '7d', 'all']:
            res = await weather_intelligence_service.get_map_data(session, window=w)
            cov = res['coverage']
            sigs = res['signals_by_type']
            print(f"Window: {w:5s} | Total Mapped: {res['total_mapped']:3d} | Features: {res['total_features']:3d} | States: {cov['states_represented']:2d}/36 | Obs: {sigs.get('OBSERVATION', 0):3d} | Events: {sigs.get('EVENT', 0):3d} | Warnings: {sigs.get('WARNING', 0):2d} | News: {sigs.get('NEWS', 0):2d}")
        
        print("\n=== TESTING LAYER FILTERING ===")
        for layer in ['OBSERVATIONS', 'EVENTS', 'NEWS', 'WARNINGS', 'EVENTS,OBSERVATIONS']:
            res = await weather_intelligence_service.get_map_data(session, layers=layer, window='live')
            sigs = res['signals_by_type']
            print(f"Layer: {layer:20s} | Total Mapped: {res['total_mapped']:3d} | Obs: {sigs.get('OBSERVATION', 0)} | Events: {sigs.get('EVENT', 0)} | Warnings: {sigs.get('WARNING', 0)} | News: {sigs.get('NEWS', 0)}")

if __name__ == '__main__':
    asyncio.run(test())
