"""Distance checks for geofenced attendance."""

from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest
from app.models.company import Company
from app.models.employee import Employee
from app.models.organization import Location

EARTH_RADIUS_M = 6_371_000


def distance_metres(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in metres (haversine)."""
    p1, p2 = radians(lat1), radians(lat2)
    d_lat = p2 - p1
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(p1) * cos(p2) * sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def employee_location(db: Session, employee: Employee) -> Location | None:
    """The employee's assigned office, falling back to the company headquarters."""
    if employee.employment and employee.employment.location_id:
        location = db.get(Location, employee.employment.location_id)
        if location and location.company_id == employee.company_id:
            return location

    return db.query(Location).filter(
        Location.company_id == employee.company_id,
        Location.is_active.is_(True),
        Location.is_headquarters.is_(True),
    ).first()


def check_within_fence(
    db: Session, employee: Employee, latitude: float | None, longitude: float | None
) -> tuple[float | None, Location | None]:
    """Enforces the company's geofence.

    Returns (distance_in_metres, location) — distance is None when no fence applies.
    Raises BadRequest when the punch is outside the allowed radius, or when
    coordinates are required but missing.
    """
    company = db.get(Company, employee.company_id)
    if company is None or not company.geofence_enabled:
        return None, None

    location = employee_location(db, employee)
    # A location without coordinates is unfenced — don't lock people out.
    if location is None or not location.has_geofence:
        return None, location

    if latitude is None or longitude is None:
        raise BadRequest(
            "Location access is required to mark attendance. "
            "Allow location in your browser and try again."
        )

    distance = distance_metres(latitude, longitude, location.latitude, location.longitude)
    if distance > location.geofence_radius_m:
        raise BadRequest(
            f"You are {int(distance)} m from {location.name}. "
            f"You must be within {location.geofence_radius_m} m to mark attendance."
        )
    return distance, location
