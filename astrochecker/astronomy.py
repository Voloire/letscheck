"""Small, deterministic astronomical coordinate transformations."""

from datetime import datetime, timezone
import math


def _vector(ra_degrees, dec_degrees):
    ra = math.radians(ra_degrees)
    dec = math.radians(dec_degrees)
    return math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)


def interpolate_equatorial(first, second, fraction):
    """Interpolate RA/Dec on the unit sphere, including the 0/360 boundary."""
    if not 0 <= fraction <= 1:
        raise ValueError("La frazione di interpolazione deve essere tra zero e uno")
    left = _vector(*first)
    right = _vector(*second)
    vector = tuple(a + (b - a) * fraction for a, b in zip(left, right))
    length = math.sqrt(sum(component * component for component in vector))
    if length == 0:
        raise ValueError("Le coordinate non possono essere interpolate")
    x, y, z = (component / length for component in vector)
    return math.degrees(math.atan2(y, x)) % 360.0, math.degrees(math.asin(z))


def greenwich_mean_sidereal_degrees(instant):
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise ValueError("L'istante astronomico deve includere il fuso orario")
    utc = instant.astimezone(timezone.utc)
    julian_date = utc.timestamp() / 86400.0 + 2440587.5
    days = julian_date - 2451545.0
    centuries = days / 36525.0
    return (
        280.46061837
        + 360.98564736629 * days
        + 0.000387933 * centuries * centuries
        - centuries * centuries * centuries / 38710000.0
    ) % 360.0


def greenwich_apparent_sidereal_degrees(instant):
    """Approximate GAST with the leading IAU 1980 nutation terms."""
    utc = instant.astimezone(timezone.utc)
    julian_date = utc.timestamp() / 86400.0 + 2440587.5
    centuries = (julian_date - 2451545.0) / 36525.0
    omega = math.radians((125.04 - 1934.136 * centuries) % 360.0)
    solar_longitude = math.radians((280.47 + 36000.77 * centuries) % 360.0)
    lunar_longitude = math.radians((218.316 + 481267.881 * centuries) % 360.0)
    nutation_longitude_arcsec = (
        -17.2 * math.sin(omega)
        - 1.32 * math.sin(2 * solar_longitude)
        - 0.23 * math.sin(2 * lunar_longitude)
        + 0.21 * math.sin(2 * omega)
    )
    mean_obliquity = math.radians(23.4393 - 0.0130 * centuries)
    equation_of_equinoxes = nutation_longitude_arcsec * math.cos(mean_obliquity) / 3600.0
    return (greenwich_mean_sidereal_degrees(instant) + equation_of_equinoxes) % 360.0


def equatorial_to_horizontal(ra_degrees, dec_degrees, instant,
                             latitude_degrees, longitude_degrees):
    """Convert apparent equatorial coordinates to geometric altitude/azimuth."""
    ra = math.radians(float(ra_degrees))
    dec = math.radians(float(dec_degrees))
    latitude = math.radians(float(latitude_degrees))
    hour_angle = math.radians(
        (greenwich_apparent_sidereal_degrees(instant) + float(longitude_degrees)) % 360.0
    ) - ra
    sine_altitude = (
        math.sin(latitude) * math.sin(dec)
        + math.cos(latitude) * math.cos(dec) * math.cos(hour_angle)
    )
    altitude = math.asin(max(-1.0, min(1.0, sine_altitude)))
    azimuth = math.atan2(
        -math.sin(hour_angle),
        math.tan(dec) * math.cos(latitude) - math.sin(latitude) * math.cos(hour_angle),
    )
    return math.degrees(altitude), math.degrees(azimuth) % 360.0
