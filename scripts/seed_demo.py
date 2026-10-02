"""SkyPulse Deterministic Seed Mechanism

Seeds:
1. Standard system users (Admin, Analyst, Citizen) with secure bcrypt password hashes
2. Standard data sources (IMD Official, WeatherAPI, OpenWeatherMap, Citizen Submissions, Synthetic Demo Stream)
3. Connector health tracking records
4. Initial demo weather events covering all 7 primary weather categories (Rainfall, Thunderstorm, Flooding, Heatwave, Fog, Dust Storm, Strong Winds) plus extensions
5. Initial weather reports with embeddings, spatial coordinates, and verification results.
All demo records have `is_demo=True` explicitly tagged.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import uuid
import sys
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.db.session import async_session_factory
from app.core.security import get_password_hash
from app.models import (
    User,
    UserRole,
    Source,
    SourceType,
    ConnectorHealth,
    ConnectorStatus,
    WeatherEvent,
    WeatherCategory,
    EventSeverity,
    VerificationStatus,
    WeatherReport,
    ReportStatus,
    EventEvidence,
    CorroborationType,
    VerificationResult,
    VerificationMethod,
    VerificationEvidence,
    EvidenceType,
    DuplicateCluster,
)
from scripts.seed_locations import seed_locations


async def seed_users(session: AsyncSession):
    print("Seeding standard development users...")
    demo_users = [
        {
            "email": "admin@skypulse.gov.in",
            "password": "AdminPassword123!",
            "display_name": "SkyPulse Chief Administrator",
            "role": UserRole.ADMIN.value,
        },
        {
            "email": "analyst@skypulse.gov.in",
            "password": "AnalystPassword123!",
            "display_name": "Senior Weather Analyst",
            "role": UserRole.ANALYST.value,
        },
        {
            "email": "citizen@skypulse.gov.in",
            "password": "CitizenPassword123!",
            "display_name": "Volunteer Citizen Observer",
            "role": UserRole.CITIZEN.value,
        },
        {
            "email": "gov@skypulse.gov.in",
            "password": "GovPassword123!",
            "display_name": "Disaster Response Liaison",
            "role": UserRole.GOVERNMENT.value,
        },
    ]

    user_map = {}
    for u in demo_users:
        stmt = select(User).where(User.email == u["email"])
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                id=uuid.uuid4(),
                email=u["email"],
                password_hash=get_password_hash(u["password"]),
                display_name=u["display_name"],
                role=u["role"],
                is_active=True,
                is_anonymous=False,
            )
            session.add(user)
            print(f"  [+] Created user: {u['email']} ({u['role']})")
        user_map[u["role"]] = user

    await session.commit()
    return user_map


async def seed_sources(session: AsyncSession):
    print("Seeding standard data sources...")
    demo_sources = [
        {
            "name": "India Meteorological Department (Official Alerts)",
            "source_type": SourceType.GOVERNMENT_API.value,
            "connector_class": "IMDAlertsConnector",
            "trust_score": 0.95,
            "is_demo": False,
        },
        {
            "name": "WeatherAPI.com Realtime Ingestion",
            "source_type": SourceType.WEATHER_API.value,
            "connector_class": "WeatherAPIConnector",
            "trust_score": 0.85,
            "is_demo": False,
        },
        {
            "name": "OpenWeatherMap Live Stations",
            "source_type": SourceType.WEATHER_API.value,
            "connector_class": "OpenWeatherMapConnector",
            "trust_score": 0.85,
            "is_demo": False,
        },
        {
            "name": "SkyPulse Citizen Weather Reports",
            "source_type": SourceType.CITIZEN.value,
            "connector_class": "CitizenReportConnector",
            "trust_score": 0.60,
            "is_demo": False,
        },
        {
            "name": "SkyPulse Synthetic Demo Stream",
            "source_type": SourceType.DEMO.value,
            "connector_class": "DemoConnector",
            "trust_score": 0.70,
            "is_demo": True,
        },
    ]

    source_map = {}
    for s in demo_sources:
        stmt = select(Source).where(Source.name == s["name"])
        res = await session.execute(stmt)
        source = res.scalar_one_or_none()
        if not source:
            source = Source(
                id=uuid.uuid4(),
                name=s["name"],
                description=f"Standard source integration for {s['name']}",
                source_type=s["source_type"],
                connector_class=s["connector_class"],
                config={"rate_limit": 60, "enabled": True},
                trust_score=s["trust_score"],
                is_active=True,
                is_demo=s["is_demo"],
            )
            session.add(source)
            await session.flush()

            # Add health tracking
            health = ConnectorHealth(
                id=uuid.uuid4(),
                source_id=source.id,
                status=ConnectorStatus.HEALTHY.value,
                records_ingested_last_hour=45 if s["is_demo"] else 12,
                last_success_at=datetime.now(timezone.utc),
            )
            session.add(health)
            print(f"  [+] Created source: {s['name']} (Trust: {s['trust_score']})")

        source_map[s["connector_class"]] = source

    await session.commit()
    return source_map


async def seed_demo_events_and_reports(session: AsyncSession, users, sources):
    print("Seeding demo weather events & corroborating reports...")
    now = datetime.now(timezone.utc)
    demo_source = sources.get("DemoConnector") or list(sources.values())[0]
    analyst_user = users.get(UserRole.ANALYST.value)

    # 7 primary problem statement categories + extensions
    events_to_seed = [
        {
            "category": WeatherCategory.RAINFALL.value,
            "sub_category": "Torrential Downpour",
            "severity": EventSeverity.SEVERE.value,
            "lat": 19.0760,
            "lon": 72.8777,
            "city": "Mumbai",
            "district": "Mumbai",
            "state": "Maharashtra",
            "status": VerificationStatus.VERIFIED.value,
            "confidence": 0.94,
            "content": "Heavy persistent rain exceeding 85mm/hr in Dadar and Kurla causing waterlogging on tracks.",
        },
        {
            "category": WeatherCategory.THUNDERSTORM.value,
            "sub_category": "Severe Lightning",
            "severity": EventSeverity.MODERATE.value,
            "lat": 12.9716,
            "lon": 77.5946,
            "city": "Bengaluru",
            "district": "Bengaluru Urban",
            "state": "Karnataka",
            "status": VerificationStatus.VERIFIED.value,
            "confidence": 0.88,
            "content": "Intense lightning flashes and squall winds across Whitefield and Indiranagar.",
        },
        {
            "category": WeatherCategory.FLOODING.value,
            "sub_category": "Urban Inundation",
            "severity": EventSeverity.CATASTROPHIC.value,
            "lat": 25.5941,
            "lon": 85.1376,
            "city": "Patna",
            "district": "Patna",
            "state": "Bihar",
            "status": VerificationStatus.LIKELY.value,
            "confidence": 0.79,
            "content": "Ganga river overflowing into low-lying northern suburbs; waist-deep water reported in Rajendra Nagar.",
        },
        {
            "category": WeatherCategory.HEATWAVE.value,
            "sub_category": "Severe Heatwave",
            "severity": EventSeverity.SEVERE.value,
            "lat": 26.9124,
            "lon": 75.7873,
            "city": "Jaipur",
            "district": "Jaipur",
            "state": "Rajasthan",
            "status": VerificationStatus.VERIFIED.value,
            "confidence": 0.92,
            "content": "Daytime maximum temperature recorded at 46.2C with scorching Loo winds.",
        },
        {
            "category": WeatherCategory.FOG.value,
            "sub_category": "Dense Winter Fog",
            "severity": EventSeverity.MODERATE.value,
            "lat": 28.6139,
            "lon": 77.2090,
            "city": "New Delhi",
            "district": "New Delhi",
            "state": "Delhi",
            "status": VerificationStatus.VERIFIED.value,
            "confidence": 0.91,
            "content": "Dense radiation fog dropping runway visual range below 50m at IGI Airport.",
        },
        {
            "category": WeatherCategory.DUST_STORM.value,
            "sub_category": "Andhi",
            "severity": EventSeverity.SEVERE.value,
            "lat": 23.0225,
            "lon": 72.5714,
            "city": "Ahmedabad",
            "district": "Ahmedabad",
            "state": "Gujarat",
            "status": VerificationStatus.LIKELY.value,
            "confidence": 0.82,
            "content": "Sudden dust squall with gusts reaching 65 km/h drastically reducing visibility across SG Highway.",
        },
        {
            "category": WeatherCategory.STRONG_WINDS.value,
            "sub_category": "Gale Force Winds",
            "severity": EventSeverity.MODERATE.value,
            "lat": 13.0827,
            "lon": 80.2707,
            "city": "Chennai",
            "district": "Chennai",
            "state": "Tamil Nadu",
            "status": VerificationStatus.VERIFIED.value,
            "confidence": 0.86,
            "content": "Coastal squall winds sustained at 55 km/h along Marina Beach with choppy surf.",
        },
        {
            "category": WeatherCategory.CYCLONE.value,
            "sub_category": "Tropical Cyclone Outer Bands",
            "severity": EventSeverity.CATASTROPHIC.value,
            "lat": 20.2961,
            "lon": 85.8245,
            "city": "Bhubaneswar",
            "district": "Khordha",
            "state": "Odisha",
            "status": VerificationStatus.VERIFIED.value,
            "confidence": 0.96,
            "content": "Outer spiraling rainbands from Bay of Bengal system bringing sustained winds and heavy squalls.",
        },
        {
            "category": WeatherCategory.SNOWFALL.value,
            "sub_category": "Heavy Blizzard",
            "severity": EventSeverity.SEVERE.value,
            "lat": 34.0837,
            "lon": 74.7973,
            "city": "Srinagar",
            "district": "Srinagar",
            "state": "Jammu and Kashmir",
            "status": VerificationStatus.VERIFIED.value,
            "confidence": 0.95,
            "content": "Continuous heavy snowfall of 25cm in 6 hours closing national highway passes.",
        },
    ]

    for item in events_to_seed:
        pt = Point(item["lon"], item["lat"])
        geom = from_shape(pt, srid=4326)

        event_id = uuid.uuid4()
        event = WeatherEvent(
            id=event_id,
            category=item["category"],
            sub_category=item["sub_category"],
            severity=item["severity"],
            confidence_score=item["confidence"],
            verification_status=item["status"],
            centroid_point=geom,
            centroid_lat=item["lat"],
            centroid_lon=item["lon"],
            primary_state=item["state"],
            primary_district=item["district"],
            primary_city=item["city"],
            first_reported_at=now - timedelta(hours=2),
            last_updated_at=now - timedelta(minutes=15),
            evidence_count=2,
            is_anomalous=item["severity"] >= EventSeverity.SEVERE.value,
            anomaly_z_score=2.85 if item["severity"] >= EventSeverity.SEVERE.value else 0.4,
            is_demo=True,
            is_active=True,
            dweg_node_id=f"we_{event_id}",
        )
        session.add(event)
        await session.flush()

        # Primary Report
        report_id = uuid.uuid4()
        # Mock embedding 384 dimensional for test
        mock_embedding = [0.05] * 384

        report = WeatherReport(
            id=report_id,
            ingested_at=now - timedelta(hours=2),
            source_id=demo_source.id,
            raw_content=item["content"],
            normalized_text=item["content"],
            primary_category=item["category"],
            sub_category=item["sub_category"],
            severity=item["severity"],
            classification_confidence=item["confidence"],
            classification_method="zero_shot_and_nlp",
            location_point=geom,
            location_raw=f"{item['city']}, {item['state']}",
            location_lat=item["lat"],
            location_lon=item["lon"],
            location_city=item["city"],
            location_district=item["district"],
            location_state=item["state"],
            location_confidence="HIGH",
            event_time=now - timedelta(hours=2, minutes=10),
            is_duplicate=False,
            canonical_event_id=event.id,
            status=ReportStatus.PROCESSED.value,
            is_demo=True,
            metadata_={"seeded_demo": True},
            text_embedding=mock_embedding,
        )
        session.add(report)

        # Corroborating Evidence link
        evidence = EventEvidence(
            id=uuid.uuid4(),
            canonical_event_id=event.id,
            weather_report_id=report_id,
            corroboration_score=0.95,
            corroboration_type=CorroborationType.PRIMARY.value,
            added_at=now - timedelta(hours=2),
        )
        session.add(evidence)

        # Verification result
        verif = VerificationResult(
            id=uuid.uuid4(),
            canonical_event_id=event.id,
            reviewed_by=analyst_user.id if analyst_user else None,
            status=item["status"],
            confidence_score=item["confidence"],
            explanation_text=f"Event corroboration established across satellite observations, automated weather station telemetry, and local ground reports for {item['city']}.",
            evidence_items=[
                {"type": "OFFICIAL_API", "weight": 0.35, "match": True},
                {"type": "SPATIAL_CLUSTER", "weight": 0.25, "reports": 2},
                {"type": "TEMPORAL_CONSISTENCY", "weight": 0.15, "season_plausible": True},
            ],
            signal_scores={"official_api": 0.95, "spatial": 0.88, "temporal": 1.0},
            method=VerificationMethod.AI_CONFIRMED.value,
            is_manual_override=False,
        )
        session.add(verif)

        # Duplicate cluster
        cluster = DuplicateCluster(
            id=uuid.uuid4(),
            canonical_event_id=event.id,
            member_count=1,
            similarity_threshold=0.75,
        )
        session.add(cluster)

        print(f"  [+] Seeded event: {item['category']} in {item['city']} ({item['status']})")

    await session.commit()
    print("Demo weather events and evidence chain seeded successfully.")


async def main():
    async with async_session_factory() as session:
        print("Starting SkyPulse Database Seeding Process...")
        await seed_locations(session)
        users = await seed_users(session)
        sources = await seed_sources(session)
        await seed_demo_events_and_reports(session, users, sources)
        print("Database seeding completed.")


if __name__ == "__main__":
    asyncio.run(main())
