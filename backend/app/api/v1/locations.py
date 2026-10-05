import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, ConfigDict

from app.db.session import get_db
from app.models.location import Location
from app.schemas.common import LocationSchema

router = APIRouter(prefix="/locations", tags=["Locations"])


class LocationResponse(BaseModel):
    id: str
    name: str
    level: str
    state: Optional[str] = None
    district: Optional[str] = None
    country: str = "IN"
    lat: Optional[float] = None
    lon: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[LocationResponse])
async def list_locations(
    level: Optional[str] = Query(None, description="One of: CITY, DISTRICT, STATE, COUNTRY"),
    state: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve Indian states, districts, and cities for spatial querying."""
    query = select(
        Location.id,
        Location.name,
        Location.level,
        Location.state,
        Location.district,
        Location.country,
        Location.lat,
        Location.lon,
    )
    if level:
        query = query.where(Location.level == level.upper())
    if state:
        query = query.where(Location.state.ilike(f"%{state}%"))
    if search:
        query = query.where(Location.name.ilike(f"%{search}%"))

    query = query.order_by(Location.name.asc()).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    return [
        LocationResponse(
            id=str(row[0]),
            name=row[1],
            level=row[2],
            state=row[3],
            district=row[4],
            country=row[5],
            lat=row[6],
            lon=row[7],
        )
        for row in rows
    ]


@router.get("/{location_id}", response_model=LocationResponse)
async def get_single_location(
    location_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve specific location metadata and centroid coordinates."""
    try:
        l_uuid = uuid.UUID(location_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": "Provided location ID is not a valid UUID",
                "details": {"location_id": location_id},
            },
        )

    res = await db.execute(
        select(
            Location.id,
            Location.name,
            Location.level,
            Location.state,
            Location.district,
            Location.country,
            Location.lat,
            Location.lon,
        ).where(Location.id == l_uuid)
    )
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "LOCATION_NOT_FOUND",
                "message": f"Location with ID {location_id} was not found",
                "details": {"location_id": location_id},
            },
        )

    return LocationResponse(
        id=str(row[0]),
        name=row[1],
        level=row[2],
        state=row[3],
        district=row[4],
        country=row[5],
        lat=row[6],
        lon=row[7],
    )
