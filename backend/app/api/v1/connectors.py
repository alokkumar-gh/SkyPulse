"""
API endpoints for Data Ingestion Connectors, specifically Social & Web Weather Intelligence.
Provides status, source inspection, and live testing endpoints with role-based access.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.social_web import (
    SocialWebConnectorOverviewResponse,
    SocialWebConnectorStatusResponse,
    SocialWebSourceDetail,
    SocialWebSourcesListResponse,
    SocialWebTestSourceRequest,
    SocialWebTestSourceResponse,
)
from connectors.social_web_connector import (
    CONNECTOR_NAME,
    CONNECTOR_VERSION,
    DEFAULT_WEATHER_HASHTAGS,
    DEFAULT_WEATHER_KEYWORDS,
    PublicJSONAdapter,
    PublicWebAdapter,
    RSSAtomAdapter,
    SocialAPIAdapter,
    social_web_connector,
)

router = APIRouter(prefix="/connectors/social-web", tags=["Connectors - Social & Web"])
connectors_router = router


@router.get("", response_model=SocialWebConnectorOverviewResponse)
async def get_social_web_overview(
    current_user: User = Depends(get_current_user),
):
    """
    Overview of the Social & Web Weather Intelligence Connector,
    including supported source types, filter configuration, and registered providers.
    """
    sources_meta = social_web_connector.get_sources_status()
    sources_list = [
        SocialWebSourceDetail(
            provider_id=s["provider_id"],
            name=s["name"],
            source_type=s["source_type"],
            status=s["status"],
            config=s["config"],
            metrics=s["metrics"],
        )
        for s in sources_meta
    ]

    return SocialWebConnectorOverviewResponse(
        connector_name=CONNECTOR_NAME,
        connector_version=CONNECTOR_VERSION,
        status=social_web_connector.status.value,
        supported_source_types=["SOCIAL_API", "SOCIAL_FEED", "PUBLIC_WEB", "RSS_FEED", "PUBLIC_JSON"],
        default_weather_hashtags=DEFAULT_WEATHER_HASHTAGS,
        default_weather_keywords=DEFAULT_WEATHER_KEYWORDS,
        active_sources_count=len(sources_list),
        sources=sources_list,
    )


@router.get("/status", response_model=SocialWebConnectorStatusResponse)
async def get_social_web_status(
    current_user: User = Depends(get_current_user),
):
    """
    Real-time operational status and metrics telemetry for Social & Web ingestion.
    """
    sources_meta = social_web_connector.get_sources_status()
    sources_list = [
        SocialWebSourceDetail(
            provider_id=s["provider_id"],
            name=s["name"],
            source_type=s["source_type"],
            status=s["status"],
            config=s["config"],
            metrics=s["metrics"],
        )
        for s in sources_meta
    ]

    m = social_web_connector.metrics
    return SocialWebConnectorStatusResponse(
        connector_name=CONNECTOR_NAME,
        status=social_web_connector.status.value,
        is_running=social_web_connector.is_running,
        is_demo=social_web_connector.is_demo,
        records_fetched=m.records_fetched,
        records_accepted=m.records_accepted,
        records_rejected=m.records_rejected,
        weather_relevant=m.weather_relevant,
        accepted_for_pipeline=m.accepted_for_pipeline,
        accepted_india=m.accepted_india,
        rejected_non_weather=m.rejected_non_weather,
        quarantined_foreign=m.quarantined_foreign,
        quarantined_unknown_location=m.quarantined_unknown_location,
        duplicates=m.duplicates,
        reposts=m.reposts,
        rate_limits=m.rate_limits,
        errors=m.errors,
        last_poll_at=m.last_poll_at,
        last_successful_fetch=m.last_successful_fetch,
        last_error=m.last_error,
        last_error_at=m.last_error_at,
        processing_latency_ms=m.processing_latency_ms,
        sources_count=len(sources_list),
        configured_hashtags=social_web_connector.get_configured_hashtags(),
        sources_status=sources_list,
    )


@router.get("/hashtags")
async def get_configured_hashtags(
    current_user: User = Depends(get_current_user),
):
    """Get the active list of weather hashtags configured for social media ingestion."""
    return {
        "configured_hashtags": social_web_connector.get_configured_hashtags(),
        "total": len(social_web_connector.get_configured_hashtags()),
    }


@router.put("/hashtags")
async def update_configured_hashtags(
    payload: Dict[str, Any],
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
):
    """Update the active list of weather hashtags for dynamic ingestion filtering."""
    raw_tags = payload.get("hashtags", [])
    updated = social_web_connector.set_configured_hashtags(raw_tags)
    return {
        "status": "SUCCESS",
        "message": f"Configured hashtags updated ({len(updated)} active).",
        "configured_hashtags": updated,
    }


@router.get("/sources", response_model=SocialWebSourcesListResponse)
async def list_social_web_sources(
    current_user: User = Depends(get_current_user),
):
    """
    List all configured Social & Web source providers with metrics and health.
    """
    sources_meta = social_web_connector.get_sources_status()
    sources_list = [
        SocialWebSourceDetail(
            provider_id=s["provider_id"],
            name=s["name"],
            source_type=s["source_type"],
            status=s["status"],
            config=s["config"],
            metrics=s["metrics"],
        )
        for s in sources_meta
    ]

    return SocialWebSourcesListResponse(
        total=len(sources_list),
        sources=sources_list,
    )


@router.post("/test", response_model=SocialWebTestSourceResponse)
async def test_social_web_source(
    payload: SocialWebTestSourceRequest,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
):
    """
    Smoke test and validate a permitted Social, RSS, Web, or JSON weather source.
    Returns normalized preview records without persisting or leaking secrets,
    along with precise telemetry semantics.
    """
    st = payload.source_type.upper()
    t0 = time.time()

    adapter = None
    if st in ("SOCIAL_API", "SOCIAL_FEED"):
        if not payload.url:
            return SocialWebTestSourceResponse(
                status="NOT_CONFIGURED",
                source_type=st,
                tested_url=payload.url,
                success=False,
                records_found=0,
                records_fetched=0,
                error_message="Missing base_url for social API endpoint",
            )
        adapter = SocialAPIAdapter(
            provider_id="test-social-api",
            base_url=payload.url,
            api_key=payload.api_key,
            api_token=payload.api_token,
            queries=payload.queries or DEFAULT_WEATHER_HASHTAGS,
        )

    elif st == "RSS_FEED":
        if not payload.url:
            return SocialWebTestSourceResponse(
                status="NOT_CONFIGURED",
                source_type=st,
                tested_url=None,
                success=False,
                records_found=0,
                records_fetched=0,
                error_message="Missing RSS/Atom feed_url",
            )
        adapter = RSSAtomAdapter(
            provider_id="test-rss-feed",
            feed_url=payload.url,
        )

    elif st == "PUBLIC_WEB":
        if not payload.url:
            return SocialWebTestSourceResponse(
                status="NOT_CONFIGURED",
                source_type=st,
                tested_url=None,
                success=False,
                records_found=0,
                records_fetched=0,
                error_message="Missing public webpage URL",
            )
        adapter = PublicWebAdapter(
            provider_id="test-public-web",
            urls=[payload.url],
        )

    elif st == "PUBLIC_JSON":
        if not payload.url:
            return SocialWebTestSourceResponse(
                status="NOT_CONFIGURED",
                source_type=st,
                tested_url=None,
                success=False,
                records_found=0,
                records_fetched=0,
                error_message="Missing public JSON endpoint URL",
            )
        adapter = PublicJSONAdapter(
            provider_id="test-public-json",
            endpoint_url=payload.url,
            http_method=payload.http_method or "GET",
            record_path=payload.record_path or ".",
            field_mapping=payload.field_mapping,
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "UNSUPPORTED_SOURCE_TYPE",
                "message": f"Source type '{st}' is not supported. Must be one of SOCIAL_API, RSS_FEED, PUBLIC_WEB, PUBLIC_JSON.",
            },
        )

    health = await adapter.health_check()
    raw_items = await adapter.fetch()
    latency = (time.time() - t0) * 1000

    # Process all raw records through pipeline validation & telemetry calculation
    records_fetched = len(raw_items)
    weather_relevant = 0
    accepted_for_pipeline = 0
    accepted_india = 0
    rejected_non_weather = 0
    quarantined_foreign = 0
    quarantined_unknown_location = 0
    duplicates = 0
    reposts = 0
    errors = adapter.metrics.errors
    rate_limits = adapter.metrics.rate_limits
    sample_events = []

    seen_hashes = set()

    for item in raw_items:
        try:
            raw_event = adapter.parse(item)
            if raw_event is None:
                rejected_non_weather += 1
                continue

            weather_relevant += 1
            norm_event = adapter.normalize(raw_event)

            # Check repost and duplicate
            rel_val = raw_event.raw_payload.get("content_relationship")
            if rel_val == "REPOST":
                reposts += 1
            elif rel_val in ("DUPLICATE", "LIKELY_COPY"):
                duplicates += 1

            h = norm_event.idempotency_key
            if (h in seen_hashes or norm_event.is_duplicate) and rel_val not in ("DUPLICATE", "LIKELY_COPY"):
                duplicates += 1
            seen_hashes.add(h)

            if norm_event.is_india_valid and not norm_event.is_quarantined:
                accepted_india += 1
                accepted_for_pipeline += 1
            elif norm_event.is_quarantined:
                if norm_event.quarantine_reason == "FOREIGN_COORDINATES":
                    quarantined_foreign += 1
                else:
                    quarantined_unknown_location += 1

            if len(sample_events) < 10:
                sample_events.append(norm_event.model_dump())
        except Exception as e:
            errors += 1

    return SocialWebTestSourceResponse(
        status=health.value,
        source_type=st,
        tested_url=payload.url,
        success=health.value == "HEALTHY",
        records_found=records_fetched,
        records_fetched=records_fetched,
        weather_relevant=weather_relevant,
        accepted_for_pipeline=accepted_for_pipeline,
        accepted_india=accepted_india,
        rejected_non_weather=rejected_non_weather,
        quarantined_foreign=quarantined_foreign,
        quarantined_unknown_location=quarantined_unknown_location,
        duplicates=duplicates,
        reposts=reposts,
        rate_limits=rate_limits,
        errors=errors,
        sample_records=sample_events,
        latency_ms=round(latency, 2),
        error_message=adapter.metrics.last_error,
    )


# ==============================================================================
# Search Discovery Endpoints (Phase 1)
# ==============================================================================

from app.schemas.search_discovery import (
    SearchDiscoveryStatusResponse,
    SearchDiscoveryQueriesResponse,
    SearchDiscoveryTestSourceRequest,
    SearchDiscoveryTestSourceResponse,
)
from connectors.search_discovery_connector import (
    search_discovery_connector,
    DuckDuckGoSearchProvider,
    SearXNGSearchProvider,
    GoogleCSESearchProvider,
    CustomSearchProvider,
)

search_discovery_router = APIRouter(prefix="/connectors/search-discovery", tags=["Connectors - Search Discovery"])


@search_discovery_router.get("/status", response_model=SearchDiscoveryStatusResponse)
async def get_search_discovery_status(
    current_user: User = Depends(get_current_user),
):
    """Real-time operational status and metrics telemetry for Search Discovery ingestion."""
    m = search_discovery_connector.metrics
    all_queries = search_discovery_connector.query_registry.get_all_queries()

    return SearchDiscoveryStatusResponse(
        connector_name=search_discovery_connector.name,
        status=search_discovery_connector.status.value,
        is_running=search_discovery_connector.is_running,
        is_demo=search_discovery_connector.is_demo,
        provider_name=search_discovery_connector.provider.name if search_discovery_connector.provider else "None",
        records_fetched=m.records_fetched,
        records_accepted=m.records_accepted,
        records_rejected=m.records_rejected,
        weather_relevant=m.weather_relevant,
        accepted_for_pipeline=m.accepted_for_pipeline,
        accepted_india=m.accepted_india,
        rejected_non_weather=m.rejected_non_weather,
        quarantined_foreign=m.quarantined_foreign,
        quarantined_unknown_location=m.quarantined_unknown_location,
        duplicates=m.duplicates,
        errors=m.errors,
        last_poll_at=m.last_poll_at,
        last_successful_fetch=m.last_successful_fetch,
        last_error=m.last_error,
        last_error_at=m.last_error_at,
        processing_latency_ms=m.processing_latency_ms,
        active_queries_count=len(all_queries),
    )


@search_discovery_router.get("/queries", response_model=SearchDiscoveryQueriesResponse)
async def get_search_discovery_queries(
    current_user: User = Depends(get_current_user),
):
    """Inspect all configured hashtags, categories, target locations, and generated sample queries."""
    reg = search_discovery_connector.query_registry
    all_q = reg.get_all_queries()
    return SearchDiscoveryQueriesResponse(
        total_queries=len(all_q),
        hashtags=reg.hashtags,
        locations=reg.locations,
        categories=reg.categories,
        custom_queries=reg.custom_queries,
        generated_sample_queries=all_q[:20],
    )


@search_discovery_router.put("/queries")
async def update_search_discovery_queries(
    payload: Dict[str, Any],
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
):
    """Update custom search queries dynamically."""
    custom_q = payload.get("custom_queries", [])
    search_discovery_connector.set_custom_queries(custom_q)
    return {
        "status": "SUCCESS",
        "message": f"Custom search discovery queries updated ({len(custom_q)} configured).",
        "total_active_queries": len(search_discovery_connector.query_registry.get_all_queries()),
    }


@search_discovery_router.post("/test", response_model=SearchDiscoveryTestSourceResponse)
async def test_search_discovery_source(
    payload: SearchDiscoveryTestSourceRequest,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
):
    """Smoke test search discovery for a specific query without storing in production DB."""
    t0 = time.time()
    query = payload.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "EMPTY_QUERY", "message": "Search query cannot be empty."},
        )

    provider = search_discovery_connector.provider
    if payload.provider_type:
        pt = payload.provider_type.lower()
        if pt == "duckduckgo":
            provider = DuckDuckGoSearchProvider()
        elif pt == "searxng":
            provider = SearXNGSearchProvider()
        elif pt == "google_cse":
            provider = GoogleCSESearchProvider()

    if not provider:
        return SearchDiscoveryTestSourceResponse(
            status="NOT_CONFIGURED",
            query=query,
            provider="None",
            success=False,
            error_message="No search provider configured.",
        )

    health = await provider.health_check()
    raw_results = await provider.search(query, max_results=payload.max_results)
    latency = (time.time() - t0) * 1000

    weather_rel = 0
    acc_india = 0
    quar = 0
    sample_records = []

    for r in raw_results:
        raw_event = search_discovery_connector.parse((r, query))
        if raw_event is None:
            continue
        weather_rel += 1
        if raw_event.is_india_valid and not raw_event.is_quarantined:
            acc_india += 1
        else:
            quar += 1
        if len(sample_records) < 5:
            sample_records.append(raw_event.model_dump())

    return SearchDiscoveryTestSourceResponse(
        status=health.value,
        query=query,
        provider=provider.name,
        success=health.value == "HEALTHY",
        records_found=len(raw_results),
        weather_relevant=weather_rel,
        accepted_india=acc_india,
        quarantined=quar,
        sample_records=sample_records,
        latency_ms=round(latency, 2),
    )


# ==============================================================================
# News Website Ingestion Endpoints
# ==============================================================================

from app.schemas.news_website import (
    NewsWebsiteStatusResponse,
    NewsWebsiteSourcesListResponse,
    NewsSourceDetailResponse,
    NewsWebsiteTestSourceRequest,
    NewsWebsiteTestSourceResponse,
)
from connectors.news_website_connector import (
    news_website_connector,
    NewsSourceDefinition,
    NewsArticleItem,
)

news_website_router = APIRouter(prefix="/connectors/news-website", tags=["Connectors - News Website"])


@news_website_router.get("/status", response_model=NewsWebsiteStatusResponse)
async def get_news_website_status(
    current_user: User = Depends(get_current_user),
):
    """Real-time operational status and metrics telemetry for News Website ingestion."""
    m = news_website_connector.metrics
    reg = news_website_connector.registry

    return NewsWebsiteStatusResponse(
        connector_name=news_website_connector.name,
        status=news_website_connector.status.value,
        is_running=news_website_connector.is_running,
        is_demo=news_website_connector.is_demo,
        sources_configured=len(reg.get_all_sources()),
        sources_healthy=news_website_connector.sources_healthy_count,
        sources_failed=news_website_connector.sources_failed_count,
        feeds_polled=news_website_connector.feeds_polled_count,
        articles_discovered=m.records_fetched,
        weather_relevant=m.weather_relevant,
        accepted_for_pipeline=m.accepted_for_pipeline,
        accepted_india=m.accepted_india,
        rejected_non_weather=m.rejected_non_weather,
        quarantined_foreign=m.quarantined_foreign,
        quarantined_unknown_location=m.quarantined_unknown_location,
        duplicates=m.duplicates,
        parsing_errors=news_website_connector.parsing_errors_count,
        rate_limit_responses=news_website_connector.rate_limit_responses_count,
        last_successful_fetch=m.last_successful_fetch,
        last_poll_at=m.last_poll_at,
        processing_latency_ms=m.processing_latency_ms,
    )


@news_website_router.get("/sources", response_model=NewsWebsiteSourcesListResponse)
async def list_news_website_sources(
    current_user: User = Depends(get_current_user),
):
    """List all registered Indian news and weather publisher sources."""
    sources = news_website_connector.registry.get_all_sources()
    details = [
        NewsSourceDetailResponse(
            source_id=s.source_id,
            publisher_name=s.publisher_name,
            domains=s.domains,
            feed_urls=s.feed_urls,
            article_category_urls=s.article_category_urls,
            source_type=s.source_type,
            enabled=s.enabled,
            polling_interval_seconds=s.polling_interval_seconds,
            status=s.status.value,
        )
        for s in sources
    ]
    return NewsWebsiteSourcesListResponse(total=len(details), sources=details)


@news_website_router.post("/sources/{source_id}/toggle")
async def toggle_news_source(
    source_id: str,
    enabled: bool,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
):
    """Enable or disable a specific news source by ID."""
    reg = news_website_connector.registry
    source = reg.get_source(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SOURCE_NOT_FOUND", "message": f"News source '{source_id}' not found."},
        )
    source.enabled = enabled
    return {
        "status": "SUCCESS",
        "source_id": source_id,
        "enabled": source.enabled,
        "message": f"Source '{source.publisher_name}' is now {'enabled' if enabled else 'disabled'}.",
    }


@news_website_router.post("/test", response_model=NewsWebsiteTestSourceResponse)
async def test_news_feed_source(
    payload: NewsWebsiteTestSourceRequest,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
):
    """Smoke test a news RSS/Atom feed URL without persisting to the database."""
    t0 = time.time()
    feed_url = payload.feed_url.strip()
    if not feed_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "EMPTY_FEED_URL", "message": "Feed URL cannot be empty."},
        )

    headers = {"User-Agent": news_website_connector.user_agent}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(feed_url)
            latency = (time.time() - t0) * 1000

            if resp.status_code != 200:
                return NewsWebsiteTestSourceResponse(
                    status="ERROR",
                    feed_url=feed_url,
                    publisher_name=payload.publisher_name or "Unknown",
                    success=False,
                    error_message=f"HTTP status {resp.status_code}",
                    latency_ms=round(latency, 2),
                )

            dummy_source = NewsSourceDefinition(
                source_id="test-source",
                publisher_name=payload.publisher_name or "Test Publisher",
                domains=[urlparse(feed_url).netloc],
                feed_urls=[feed_url],
            )
            items = news_website_connector._parse_feed_xml(resp.text, dummy_source, feed_url)

            weather_rel = 0
            acc_india = 0
            quar = 0
            sample_articles = []

            for item in items:
                raw_event = news_website_connector.parse(item)
                if raw_event is None:
                    continue
                weather_rel += 1
                if raw_event.is_india_valid and not raw_event.is_quarantined:
                    acc_india += 1
                else:
                    quar += 1
                if len(sample_articles) < 5:
                    sample_articles.append(raw_event.model_dump())

            return NewsWebsiteTestSourceResponse(
                status="HEALTHY" if len(items) > 0 else "NO_ITEMS",
                feed_url=feed_url,
                publisher_name=dummy_source.publisher_name,
                success=True,
                articles_found=len(items),
                weather_relevant=weather_rel,
                accepted_india=acc_india,
                quarantined=quar,
                sample_articles=sample_articles,
                latency_ms=round(latency, 2),
            )
    except Exception as e:
        latency = (time.time() - t0) * 1000
        return NewsWebsiteTestSourceResponse(
            status="ERROR",
            feed_url=feed_url,
            publisher_name=payload.publisher_name or "Unknown",
            success=False,
            error_message=str(e),
            latency_ms=round(latency, 2),
        )


# ==============================================================================
# Unified Source Orchestration & Ingestion Telemetry Endpoints
# ==============================================================================

from app.schemas.orchestration import (
    UnifiedNationalOverviewResponse,
    UnifiedSourceStatusResponse,
    IngestionRunsListResponse,
    IngestionRunResponse,
    TriggerRunResponse,
    HistoricalTelemetryResponse,
    HistoricalSourceComparisonResponse,
    HistoricalPerformanceSummaryResponse,
    PruneHistoryResponse,
)
from connectors.orchestrator import source_orchestrator

unified_connectors_router = APIRouter(prefix="/connectors", tags=["Connectors - Unified Orchestration"])


@unified_connectors_router.get("/overview", response_model=UnifiedNationalOverviewResponse)
async def get_unified_national_overview(
    current_user: User = Depends(get_current_user),
):
    """
    National-level operational overview aggregating pipeline stages,
    source family summaries, and health metrics across all ingestion connectors.
    """
    return source_orchestrator.get_unified_overview()


@unified_connectors_router.get("/health", response_model=List[UnifiedSourceStatusResponse])
async def get_unified_sources_health(
    current_user: User = Depends(get_current_user),
):
    """Health matrix and operational status across all registered data ingestion sources."""
    return source_orchestrator.get_source_health_matrix()


@unified_connectors_router.get("/telemetry")
async def get_unified_pipeline_telemetry(
    current_user: User = Depends(get_current_user),
):
    """
    Detailed pipeline stage telemetry breakdown from fetch to DWEG integration
    including calculated operational rates.
    """
    overview = source_orchestrator.get_unified_overview()
    return {
        "timestamp": overview.timestamp,
        "global_pipeline_telemetry": overview.global_pipeline_telemetry.model_dump(),
        "global_performance": overview.global_performance.model_dump(),
        "source_family_summaries": [s.model_dump() for s in overview.source_family_summaries],
    }


@unified_connectors_router.get("/runs", response_model=IngestionRunsListResponse)
async def get_recent_ingestion_runs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Recent live ingestion run history across all connectors."""
    runs = source_orchestrator.get_recent_runs(limit=limit)
    return IngestionRunsListResponse(total=len(runs), runs=runs)


# ==============================================================================
# Persistent PostgreSQL Historical Endpoints
# ==============================================================================

@unified_connectors_router.get("/runs/history", response_model=IngestionRunsListResponse)
async def get_historical_ingestion_runs(
    connector_id: Optional[str] = None,
    source_family: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Query persistent completed ingestion runs from PostgreSQL with filtering,
    time range filtering, and pagination.
    """
    runs, total = await source_orchestrator.get_historical_runs(
        connector_id=connector_id,
        source_family=source_family,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        session=db,
    )
    return IngestionRunsListResponse(total=total, runs=runs)


@unified_connectors_router.get("/telemetry/history", response_model=HistoricalTelemetryResponse)
async def get_historical_telemetry_aggregation(
    interval: str = "daily",
    connector_id: Optional[str] = None,
    source_family: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Time-bucketed aggregation (hourly, daily, weekly) of historical telemetry stages
    and operational rates computed directly from persistent database records.
    """
    if interval not in ("hourly", "daily", "weekly"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_INTERVAL", "message": "Interval must be 'hourly', 'daily', or 'weekly'."},
        )
    return await source_orchestrator.get_historical_telemetry_aggregation(
        interval=interval,
        connector_id=connector_id,
        source_family=source_family,
        start_date=start_date,
        end_date=end_date,
        session=db,
    )


@unified_connectors_router.get("/history/comparison", response_model=HistoricalSourceComparisonResponse)
async def get_historical_source_comparison(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Historical cross-source comparison matrix computed from persisted database records.
    """
    return await source_orchestrator.get_historical_source_comparison(
        start_date=start_date,
        end_date=end_date,
        session=db,
    )


@unified_connectors_router.get("/history/performance", response_model=HistoricalPerformanceSummaryResponse)
async def get_historical_performance_summary(
    connector_id: Optional[str] = None,
    source_family: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Comprehensive historical performance rates and stage totals from PostgreSQL.
    """
    return await source_orchestrator.get_historical_performance_summary(
        connector_id=connector_id,
        source_family=source_family,
        start_date=start_date,
        end_date=end_date,
        session=db,
    )


@unified_connectors_router.post("/history/prune", response_model=PruneHistoryResponse)
async def prune_historical_ingestion_data(
    retention_days: int = 90,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Safely prunes historical ingestion runs older than the configured retention cutoff.
    Restricted to ADMIN role.
    """
    if retention_days < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_RETENTION_DAYS", "message": "Retention days must be at least 1."},
        )
    return await source_orchestrator.prune_historical_records(
        retention_days=retention_days,
        session=db,
    )


# ==============================================================================
# Parameterized Connector Endpoints
# ==============================================================================

@unified_connectors_router.get("/{connector_id}", response_model=UnifiedSourceStatusResponse)
async def get_connector_detail(
    connector_id: str,
    current_user: User = Depends(get_current_user),
):
    """Detailed operational status, stage telemetry, and recent runs for a specific connector."""
    status_res = source_orchestrator.get_source_status(connector_id)
    if not status_res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CONNECTOR_NOT_FOUND", "message": f"Connector with ID '{connector_id}' not found."},
        )
    return status_res


@unified_connectors_router.get("/{connector_id}/runs", response_model=IngestionRunsListResponse)
async def get_connector_runs(
    connector_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Recent ingestion runs for a specific connector."""
    runs = source_orchestrator.get_recent_runs(connector_id=connector_id, limit=limit)
    return IngestionRunsListResponse(total=len(runs), runs=runs)


@unified_connectors_router.post("/{connector_id}/poll", response_model=TriggerRunResponse)
async def trigger_connector_poll(
    connector_id: str,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an on-demand isolated ingestion run for a specific connector."""
    reg_info = source_orchestrator.get_connector_info(connector_id)
    if not reg_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CONNECTOR_NOT_FOUND", "message": f"Connector '{connector_id}' is not registered."},
        )

    run_res = await source_orchestrator.execute_connector_run(connector_id, session=db)
    return TriggerRunResponse(
        connector_id=connector_id,
        display_name=reg_info.display_name,
        run=run_res,
        message=f"Ingestion run completed with status '{run_res.status.value}'.",
    )
