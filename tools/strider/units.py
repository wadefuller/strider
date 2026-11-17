"""Units and formatting.

Everything stored in a plan or snapshot is metric: metres, seconds, and pace as
seconds per kilometre. The runner's unit preference ("km" or "mi") only changes
how values are displayed.
"""
from __future__ import annotations

KM = 1000.0
MI = 1609.344

DISTANCES = {"5k": 5000.0, "10k": 10000.0, "half": 21097.5, "marathon": 42195.0}
DISTANCE_NAMES = {"5k": "5K", "10k": "10K", "half": "half marathon", "marathon": "marathon"}


def unit_m(units):
    return MI if units == "mi" else KM


def fmt_clock(seconds, force_hours=False):
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h or force_hours:
        return "%d:%02d:%02d" % (h, m, sec)
    return "%d:%02d" % (m, sec)


def parse_clock(text):
    """'1:35:00' or '45:30' -> seconds."""
    parts = [float(p) for p in str(text).strip().split(":")]
    if not 1 <= len(parts) <= 3:
        raise ValueError("not a time: %r" % (text,))
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def pace_in_units(s_per_km, units):
    return s_per_km * unit_m(units) / KM


def fmt_pace(s_per_km, units="km", suffix=True):
    text = fmt_clock(pace_in_units(s_per_km, units))
    return text + "/" + units if suffix else text


def fmt_band(band, units="km"):
    """A pace band is [fast, slow] in s/km."""
    return "%s to %s" % (fmt_pace(band[0], units, False), fmt_pace(band[1], units))


def fmt_dist(metres, units="km", digits=1):
    return "%.*f %s" % (digits, metres / unit_m(units), units)


def pace_to_mps(s_per_km):
    return KM / s_per_km


def riegel(time_s, from_m, to_m, exponent=1.06):
    """Riegel (1981) endurance model: T2 = T1 * (D2 / D1) ** 1.06."""
    return time_s * (to_m / from_m) ** exponent
