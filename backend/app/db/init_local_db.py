"""
SkyPulse Local Database Initialization and Demo Seeding
======================================================
Creates schema tables in SQLite/PostgreSQL and seeds canonical weather events
with multi-source evidence reports, sources, and locations for interactive judging.
"""

import asyncio
import sys
import uuid
sys.path.insert(0, r"e:\SkyPulse\backend")
from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import Base
from app.models.audit_log import AuditLog
AuditLog.__table__.columns["id"].autoincrement = False
from app.db.session import engine, async_session_factory
from app.models.user import User
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.source import Source
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus, UserRole, CorroborationType
from app.core.security import get_password_hash


async def init_and_seed_db():
    print("Initializing SkyPulse database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Schema tables initialized successfully.")

    async with async_session_factory() as session:
        # Check if events already exist
        res = await session.execute(select(WeatherEvent))
        existing_events = res.scalars().all()
        if existing_events:
            print(f"Database already contains {len(existing_events)} weather events. Skipping seed.")
            return

        print("Seeding canonical weather events and multi-source DWEG evidence networks...")

        now = datetime.now(timezone.utc)

        # 0. Default Users
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@skypulse.in",
            password_hash=get_password_hash("admin123"),
            display_name="System Administrator",
            role=UserRole.ADMIN.value,
            is_active=True,
            created_at=now,
        )
        analyst_user = User(
            id=uuid.uuid4(),
            email="analyst@skypulse.in",
            password_hash=get_password_hash("analyst123"),
            display_name="Lead Meteorologist",
            role=UserRole.ANALYST.value,
            is_active=True,
            created_at=now,
        )
        session.add_all([admin_user, analyst_user])

        # 1. Sources
        imd_source = Source(
            id=uuid.uuid4(),
            name="IMD Doppler Radar & Synoptic Grid",
            source_type="GOVERNMENT_API",
            connector_class="IMDConnector",
            trust_score=0.96,
            is_active=True,
            config={"endpoint": "https://api.imd.gov.in/v1/synoptic"},
            created_at=now,
        )
        gdacs_source = Source(
            id=uuid.uuid4(),
            name="GDACS Tropical Alert Stream",
            source_type="RSS_FEED",
            connector_class="GDACSConnector",
            trust_score=0.92,
            is_active=True,
            config={"feed": "https://www.gdacs.org/xml/rss.xml"},
            created_at=now,
        )
        mastodon_source = Source(
            id=uuid.uuid4(),
            name="Mastodon Verified Weather Feeds",
            source_type="RSS_FEED",
            connector_class="SocialWebConnector",
            trust_score=0.81,
            is_active=True,
            config={"instance": "mastodon.social"},
            created_at=now,
        )
        citizen_source = Source(
            id=uuid.uuid4(),
            name="SkyPulse Citizen Ground Network",
            source_type="CITIZEN",
            connector_class="CitizenConnector",
            trust_score=0.84,
            is_active=True,
            config={"mobile_app": "v1.4.2"},
            created_at=now,
        )
        sensor_source = Source(
            id=uuid.uuid4(),
            name="CWC River Gauge Telemetry",
            source_type="WEATHER_API",
            connector_class="SensorConnector",
            trust_score=0.95,
            is_active=True,
            config={"protocol": "MQTT/LoRaWAN"},
            created_at=now,
        )
        session.add_all([imd_source, gdacs_source, mastodon_source, citizen_source, sensor_source])
        await session.flush()

        # ---------------------------------------------------------------------
        # EVENT 1: Cyclone Alert — Odisha Coast
        # ---------------------------------------------------------------------
        evt1 = WeatherEvent(
            id=uuid.uuid4(),
            category=WeatherCategory.CYCLONE.value,
            severity=EventSeverity.SEVERE.value,
            confidence_score=0.94,
            verification_status=VerificationStatus.VERIFIED.value,
            centroid_lat=19.8135,
            centroid_lon=85.8312,
            primary_state="Odisha",
            primary_district="Puri",
            primary_city="Puri",
            first_reported_at=now - timedelta(hours=6),
            last_updated_at=now - timedelta(minutes=10),
            evidence_count=4,
            is_active=True,
        )
        session.add(evt1)
        await session.flush()

        # Reports for Event 1
        r1_1 = WeatherReport(
            id=uuid.uuid4(),
            source_id=imd_source.id,
            primary_category=WeatherCategory.CYCLONE.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=19.8135,
            location_lon=85.8312,
            location_district="Puri",
            location_state="Odisha",
            normalized_text="Doppler radar Doppler-Echo detects high-reflectivity eyewall structure approaching Puri coast.",
            classification_confidence=0.96,
            status="PROCESSED",
            event_time=now - timedelta(hours=5),
            ingested_at=now - timedelta(hours=5),
        )
        r1_2 = WeatherReport(
            id=uuid.uuid4(),
            source_id=gdacs_source.id,
            primary_category=WeatherCategory.CYCLONE.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=19.9500,
            location_lon=86.1000,
            location_district="Jagatsinghpur",
            location_state="Odisha",
            normalized_text="GDACS Red Alert: Tropical Cyclone approaching North Bay of Bengal / Odisha coast with storm surge 1.8m.",
            classification_confidence=0.93,
            status="PROCESSED",
            event_time=now - timedelta(hours=4),
            ingested_at=now - timedelta(hours=4),
        )
        r1_3 = WeatherReport(
            id=uuid.uuid4(),
            source_id=citizen_source.id,
            primary_category=WeatherCategory.CYCLONE.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=19.8100,
            location_lon=85.8200,
            location_district="Puri",
            location_state="Odisha",
            normalized_text="Extreme wind gusts blowing tin roofs and large trees near Puri Swargadwar beach.",
            classification_confidence=0.88,
            status="PROCESSED",
            event_time=now - timedelta(hours=2),
            ingested_at=now - timedelta(hours=2),
        )
        r1_4 = WeatherReport(
            id=uuid.uuid4(),
            source_id=mastodon_source.id,
            primary_category=WeatherCategory.CYCLONE.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=20.2500,
            location_lon=86.4000,
            location_district="Kendrapara",
            location_state="Odisha",
            normalized_text="Heavy rain and gale force winds reaching coastal Kendrapara as storm propagates northeast.",
            classification_confidence=0.85,
            status="PROCESSED",
            event_time=now - timedelta(minutes=45),
            ingested_at=now - timedelta(minutes=45),
        )
        session.add_all([r1_1, r1_2, r1_3, r1_4])
        await session.flush()

        # Evidence links
        session.add_all([
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt1.id, weather_report_id=r1_1.id, corroboration_type=CorroborationType.PRIMARY.value, corroboration_score=0.96),
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt1.id, weather_report_id=r1_2.id, corroboration_type=CorroborationType.CORROBORATING.value, corroboration_score=0.93),
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt1.id, weather_report_id=r1_3.id, corroboration_type=CorroborationType.CORROBORATING.value, corroboration_score=0.88),
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt1.id, weather_report_id=r1_4.id, corroboration_type=CorroborationType.CORROBORATING.value, corroboration_score=0.85),
        ])

        # ---------------------------------------------------------------------
        # EVENT 2: Flash Flooding & Inundation — Wayanad & Kozhikode (Kerala)
        # ---------------------------------------------------------------------
        evt2 = WeatherEvent(
            id=uuid.uuid4(),
            category=WeatherCategory.FLOODING.value,
            severity=EventSeverity.SEVERE.value,
            confidence_score=0.91,
            verification_status=VerificationStatus.VERIFIED.value,
            centroid_lat=11.6854,
            centroid_lon=76.1320,
            primary_state="Kerala",
            primary_district="Wayanad",
            primary_city="Kalpetta",
            first_reported_at=now - timedelta(hours=4),
            last_updated_at=now - timedelta(minutes=25),
            evidence_count=3,
            is_active=True,
        )
        session.add(evt2)
        await session.flush()

        r2_1 = WeatherReport(
            id=uuid.uuid4(),
            source_id=sensor_source.id,
            primary_category=WeatherCategory.FLOODING.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=11.6854,
            location_lon=76.1320,
            location_district="Wayanad",
            location_state="Kerala",
            normalized_text="CWC Automatic River Gauge exceeds Danger Level (DL) by 1.4 meters at Meppadi station.",
            classification_confidence=0.97,
            status="PROCESSED",
            event_time=now - timedelta(hours=3),
            ingested_at=now - timedelta(hours=3),
        )
        r2_2 = WeatherReport(
            id=uuid.uuid4(),
            source_id=imd_source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=11.6000,
            location_lon=76.0800,
            location_district="Wayanad",
            location_state="Kerala",
            normalized_text="IMD AWS station records 184.5 mm torrential downpour over Nilgiri-Wayanad hills.",
            classification_confidence=0.94,
            status="PROCESSED",
            event_time=now - timedelta(hours=3, minutes=30),
            ingested_at=now - timedelta(hours=3, minutes=30),
        )
        r2_3 = WeatherReport(
            id=uuid.uuid4(),
            source_id=citizen_source.id,
            primary_category=WeatherCategory.FLOODING.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=11.7200,
            location_lon=76.1500,
            location_district="Wayanad",
            location_state="Kerala",
            normalized_text="Water logging and flash flood mudflow entering residential access roads in Chooralmala.",
            classification_confidence=0.86,
            status="PROCESSED",
            event_time=now - timedelta(hours=1),
            ingested_at=now - timedelta(hours=1),
        )
        session.add_all([r2_1, r2_2, r2_3])
        await session.flush()

        session.add_all([
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt2.id, weather_report_id=r2_1.id, corroboration_type=CorroborationType.PRIMARY.value, corroboration_score=0.97),
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt2.id, weather_report_id=r2_2.id, corroboration_type=CorroborationType.CORROBORATING.value, corroboration_score=0.94),
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt2.id, weather_report_id=r2_3.id, corroboration_type=CorroborationType.CORROBORATING.value, corroboration_score=0.86),
        ])

        # ---------------------------------------------------------------------
        # EVENT 3: Severe Heatwave — Rajasthan
        # ---------------------------------------------------------------------
        evt3 = WeatherEvent(
            id=uuid.uuid4(),
            category=WeatherCategory.HEATWAVE.value,
            severity=EventSeverity.SEVERE.value,
            confidence_score=0.92,
            verification_status=VerificationStatus.VERIFIED.value,
            centroid_lat=26.9124,
            centroid_lon=75.7873,
            primary_state="Rajasthan",
            primary_district="Jaipur",
            primary_city="Jaipur",
            first_reported_at=now - timedelta(hours=8),
            last_updated_at=now - timedelta(minutes=40),
            evidence_count=2,
            is_active=True,
        )
        session.add(evt3)
        await session.flush()

        r3_1 = WeatherReport(
            id=uuid.uuid4(),
            source_id=imd_source.id,
            primary_category=WeatherCategory.HEATWAVE.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=26.9124,
            location_lon=75.7873,
            location_district="Jaipur",
            location_state="Rajasthan",
            normalized_text="IMD Sanganer observatory reports maximum temp 46.8°C (departure +5.6°C above normal).",
            classification_confidence=0.98,
            status="PROCESSED",
            event_time=now - timedelta(hours=6),
            ingested_at=now - timedelta(hours=6),
        )
        r3_2 = WeatherReport(
            id=uuid.uuid4(),
            source_id=citizen_source.id,
            primary_category=WeatherCategory.HEATWAVE.value,
            severity=EventSeverity.SEVERE.value,
            location_lat=26.9200,
            location_lon=75.8000,
            location_district="Jaipur",
            location_state="Rajasthan",
            normalized_text="Intense dry heat and loo conditions; public health advisory issued.",
            classification_confidence=0.84,
            status="PROCESSED",
            event_time=now - timedelta(hours=2),
            ingested_at=now - timedelta(hours=2),
        )
        session.add_all([r3_1, r3_2])
        await session.flush()

        session.add_all([
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt3.id, weather_report_id=r3_1.id, corroboration_type=CorroborationType.PRIMARY.value, corroboration_score=0.98),
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt3.id, weather_report_id=r3_2.id, corroboration_type=CorroborationType.CORROBORATING.value, corroboration_score=0.84),
        ])

        # ---------------------------------------------------------------------
        # EVENT 4: Monsoon Downpour & Waterlogging — Mumbai
        # ---------------------------------------------------------------------
        evt4 = WeatherEvent(
            id=uuid.uuid4(),
            category=WeatherCategory.RAINFALL.value,
            severity=EventSeverity.MODERATE.value,
            confidence_score=0.85,
            verification_status=VerificationStatus.VERIFIED.value,
            centroid_lat=19.0760,
            centroid_lon=72.8777,
            primary_state="Maharashtra",
            primary_district="Mumbai City",
            primary_city="Mumbai",
            first_reported_at=now - timedelta(hours=2),
            last_updated_at=now - timedelta(minutes=5),
            evidence_count=2,
            is_active=True,
        )
        session.add(evt4)
        await session.flush()

        r4_1 = WeatherReport(
            id=uuid.uuid4(),
            source_id=imd_source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            severity=EventSeverity.MODERATE.value,
            location_lat=19.0760,
            location_lon=72.8777,
            location_district="Mumbai City",
            location_state="Maharashtra",
            normalized_text="Santacruz weather radar shows moderate convective rain bands over Mumbai MMR.",
            classification_confidence=0.92,
            status="PROCESSED",
            event_time=now - timedelta(hours=2),
            ingested_at=now - timedelta(hours=2),
        )
        r4_2 = WeatherReport(
            id=uuid.uuid4(),
            source_id=mastodon_source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            severity=EventSeverity.MODERATE.value,
            location_lat=19.1000,
            location_lon=72.8500,
            location_district="Mumbai City",
            location_state="Maharashtra",
            normalized_text="Heavy rain starting near Andheri and Bandra; traffic slow on Western Express Highway.",
            classification_confidence=0.80,
            status="PROCESSED",
            event_time=now - timedelta(minutes=30),
            ingested_at=now - timedelta(minutes=30),
        )
        session.add_all([r4_1, r4_2])
        await session.flush()

        session.add_all([
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt4.id, weather_report_id=r4_1.id, corroboration_type=CorroborationType.PRIMARY.value, corroboration_score=0.92),
            EventEvidence(id=uuid.uuid4(), canonical_event_id=evt4.id, weather_report_id=r4_2.id, corroboration_type=CorroborationType.CORROBORATING.value, corroboration_score=0.80),
        ])
        await session.commit()
        print("Database seeded with 4 canonical multi-source weather events and full DWEG evidence networks.")


if __name__ == "__main__":
    asyncio.run(init_and_seed_db())
