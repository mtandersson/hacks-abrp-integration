"""Telemetry wire-to-state extractors and the `(key, value_fn)` registry.

Shared building blocks used by both ``sensor.py`` (which assembles the
``SENSORS`` tuple of :class:`AbrpTelemetrySensorEntityDescription` from these
helpers) and ``coordinator.py`` (which iterates ``SENSOR_VALUE_FNS`` to stamp
``last_reported_at`` per key as frames arrive).

The dataclass and the ``SENSORS`` tuple deliberately live in ``sensor.py``
to satisfy ``pylint: C7411 hass-enforce-class-module`` (derived
``SensorEntityDescription`` subclasses belong in the integration's sensor
module). Extracting only the value_fn helpers + the key registry here still
breaks the otherwise-cyclic ``coordinator.py → sensor.py → coordinator.py``
chain (``sensor.py`` already imports ``AbrpTelemetryCoordinator`` from
``coordinator.py``).

Underscore prefix matches ``_telemetry_models.py`` precedent in the same
package — internal-to-integration, not a HA platform module.
"""

from collections.abc import Callable, Mapping
from typing import Any


def _soc_percent(frame: Mapping[str, Any]) -> float | None:
    """Extract battery SoC as a percent, or None when the metric is absent.

    Tolerates every shape the server might emit for an unavailable metric:
    missing key, ``"soc": null``, ``"soc": {}``, ``"soc": {"frac": null}``,
    and any non-numeric inner value. Never raises. Display rounding is
    delegated to ``suggested_display_precision``.
    """
    soc = frame.get("soc")
    if not isinstance(soc, dict):
        return None
    frac = soc.get("frac")
    if not isinstance(frac, (int, float)) or isinstance(frac, bool):
        return None
    return frac * 100


def _power_w(frame: Mapping[str, Any]) -> float | None:
    """Extract instantaneous power in watts, or None when unavailable."""
    power = frame.get("power")
    if not isinstance(power, dict):
        return None
    watts = power.get("w")
    if not isinstance(watts, (int, float)) or isinstance(watts, bool):
        return None
    return watts


def _voltage_v(frame: Mapping[str, Any]) -> float | None:
    """Extract pack voltage in volts, or None when unavailable."""
    voltage = frame.get("voltage")
    if not isinstance(voltage, dict):
        return None
    volts = voltage.get("v")
    if not isinstance(volts, (int, float)) or isinstance(volts, bool):
        return None
    return volts


def _soe_wh(frame: Mapping[str, Any]) -> float | None:
    """Extract State of Energy in watt-hours, or None when unavailable."""
    soe = frame.get("soe")
    if not isinstance(soe, dict):
        return None
    wh = soe.get("wh")
    if not isinstance(wh, (int, float)) or isinstance(wh, bool):
        return None
    return wh


def _odometer_m(frame: Mapping[str, Any]) -> float | None:
    """Extract odometer reading in meters, or None when unavailable."""
    odometer = frame.get("odometer")
    if not isinstance(odometer, dict):
        return None
    meters = odometer.get("m")
    if not isinstance(meters, (int, float)) or isinstance(meters, bool):
        return None
    return meters


def _calibrated_ref_cons_wh_per_km(frame: Mapping[str, Any]) -> float | None:
    """Extract ABRP's calibrated reference consumption (Wh/km), or None."""
    ref_cons = frame.get("calibratedRefCons")
    if not isinstance(ref_cons, dict):
        return None
    wh_per_km = ref_cons.get("wh_per_km")
    if not isinstance(wh_per_km, (int, float)) or isinstance(wh_per_km, bool):
        return None
    return wh_per_km


def _battery_capacity_wh(frame: Mapping[str, Any]) -> float | None:
    """Extract effective battery capacity in watt-hours, or None."""
    capacity = frame.get("batteryCapacity")
    if not isinstance(capacity, dict):
        return None
    wh = capacity.get("wh")
    if not isinstance(wh, (int, float)) or isinstance(wh, bool):
        return None
    return wh


def _soh_percent(frame: Mapping[str, Any]) -> float | None:
    """Extract State of Health as a percentage (higher = healthier), or None.

    ABRP delivers ``soh.frac`` as a 0.0–1.0 fraction. Multiplied by 100 to
    surface a familiar 0–100% scale; intentionally NOT clamped at 100 — a
    post-recalibration overshoot (``frac > 1.0``) is meaningful drift the
    LTS sum is meant to capture, so flattening it would lose signal.
    """
    soh = frame.get("soh")
    if not isinstance(soh, dict):
        return None
    frac = soh.get("frac")
    if not isinstance(frac, (int, float)) or isinstance(frac, bool):
        return None
    return frac * 100


def _estimated_battery_range_m(frame: Mapping[str, Any]) -> float | None:
    """Extract estimated remaining range in meters, or None when unavailable.

    Native ``METERS`` so the LTS pipeline stores a unit-flip-safe canonical
    scale; ``suggested_unit_of_measurement=KILOMETERS`` (set on the
    description) renders km on the dashboard. Mirrors ``_odometer_m``.
    """
    range_value = frame.get("estimatedBatteryRange")
    if not isinstance(range_value, dict):
        return None
    meters = range_value.get("m")
    if not isinstance(meters, (int, float)) or isinstance(meters, bool):
        return None
    return meters


def _battery_temperature_c(frame: Mapping[str, Any]) -> float | None:
    """Extract battery pack temperature in Celsius, or None when unavailable.

    No lower-bound filter — winter operation (sub-zero pack temps) is a
    real wire shape, not a degenerate one. Distinct from any cabin or
    external temperature ABRP might surface in future fields.
    """
    temperature = frame.get("batteryTemperature")
    if not isinstance(temperature, dict):
        return None
    celsius = temperature.get("c")
    if not isinstance(celsius, (int, float)) or isinstance(celsius, bool):
        return None
    return celsius


# Cycle-breaking registry consumed by the coordinator's per-key stamp
# loop (in ``apply_frame``). ``sensor.py`` composes its ``SENSORS`` tuple
# from the same helpers above; the entries here mirror its set of keys,
# so adding a new metric requires touching both surfaces — the test
# suite cross-pins coverage.
#
# 3-tuple shape ``(registry_key, wire_key, value_fn)``: most metrics are
# named identically on the wire and in the registry, but a handful of
# fields camelCase on the wire (``calibratedRefCons``, ``batteryCapacity``,
# ``estimatedBatteryRange``, ``batteryTemperature``) while staying
# snake_case in HA's translation/unique_id surface. The wire_key column
# keeps the per-frame lookup (used by :func:`_extract_provider`) aligned
# with what the value_fn helper itself reads, while ``registry_key``
# keys both the coordinator stamp dicts and the sensor entity
# ``unique_id`` suffix. Co-locating the two strings next to the value_fn
# prevents the column from drifting away from the helper's own
# ``frame.get(...)`` literal.
SENSOR_VALUE_FNS: tuple[
    tuple[str, str, Callable[[Mapping[str, Any]], float | None]], ...
] = (
    ("soc", "soc", _soc_percent),
    ("power", "power", _power_w),
    ("voltage", "voltage", _voltage_v),
    ("soe", "soe", _soe_wh),
    ("odometer", "odometer", _odometer_m),
    ("calibrated_ref_cons", "calibratedRefCons", _calibrated_ref_cons_wh_per_km),
    ("battery_capacity", "batteryCapacity", _battery_capacity_wh),
    ("soh", "soh", _soh_percent),
    ("range", "estimatedBatteryRange", _estimated_battery_range_m),
    ("battery_temperature", "batteryTemperature", _battery_temperature_c),
)


def _extract_lat_long(frame: Mapping[str, Any]) -> tuple[float, float] | None:
    """Return ``(lat, long)`` from a telemetry frame, or ``None``.

    Tolerates every shape the server might emit while the metric is
    unavailable: missing key, ``location: null``, ``location: {}``,
    ``location: {"lat": null}``, partial leaves, and non-numeric values.
    Explicitly excludes ``bool`` because ``isinstance(True, int)`` is
    True in Python (``bool ⊂ int``) and a malformed ``"lat": true`` would
    otherwise sneak past the numeric check and produce a nonsense
    coordinate at the entity surface.

    Co-located with ``SENSOR_VALUE_FNS`` so the coordinator's stamp loop
    can iterate a single registry covering both the sensor platform and
    the device_tracker platform without importing from either platform
    module. The module name predates this colocation; location is a
    tracker concern, not a sensor concern.
    """
    location = frame.get("location")
    if not isinstance(location, dict):
        return None
    lat = location.get("lat")
    lng = location.get("long")
    if not isinstance(lat, (int, float)) or isinstance(lat, bool):
        return None
    if not isinstance(lng, (int, float)) or isinstance(lng, bool):
        return None
    # Coerce both axes to ``float`` at the live-wire boundary so an int-typed
    # wire value (``"lat": 51``) doesn't leak through to the tracker's
    # ``extra_state_attributes`` as ``int`` and contradict the function's
    # ``tuple[float, float]`` signature. Mirrors the N76-3 fix at the restore
    # boundary, keeping the two surfaces type-symmetric.
    return float(lat), float(lng)


# Device-tracker platform's presence-predicate key + value_fn. Mirrors the
# (key, callable) tuple shape used by ``SENSOR_VALUE_FNS`` so the
# coordinator's stamp loop can concatenate without ad-hoc shape adapters.
LOCATION_KEY = "location"
LOCATION_VALUE_FN: Callable[[Mapping[str, Any]], tuple[float, float] | None] = (
    _extract_lat_long
)


# Cross-platform stamped-key registry consumed by the coordinator's stamp
# loop. Concat-of-module-level-tuples (not runtime ``_presence_predicates``)
# so frames arriving during the pre-warm window get stamps too — platforms
# have not yet registered predicates at that point but the stamp registry
# is populated at import time.
STAMPED_VALUE_FNS: tuple[
    tuple[str, str, Callable[[Mapping[str, Any]], object | None]], ...
] = (*SENSOR_VALUE_FNS, (LOCATION_KEY, LOCATION_KEY, LOCATION_VALUE_FN))


def _extract_provider(frame: Mapping[str, Any], key: str) -> str | None:
    """Return the upstream provider string for ``frame[key]``, or ``None``.

    Symmetric-reject boundary: every non-string AND the empty string AND
    any whitespace-only or leading-/trailing-padded string map to ``None``
    via :func:`_is_clean_provider_str` so the
    coordinator's stamp loop and the entity-level restore guard share
    one contract. Per-metric ``provider`` is a ``NotRequired`` claim on
    each ``WithTimeAndProvider`` block (see
    ``~/abrp/abrp/spec/api/common/tlm.yaml``); absent / null /
    non-string / empty / whitespace-padded are all treated as "no
    usable provider on this frame" and the prior stamp survives
    (sticky-on-omission — providers don't flip mid-stream in normal
    operation).
    """
    block = frame.get(key)
    if not isinstance(block, dict):
        return None
    provider = block.get("provider")
    if _is_clean_provider_str(provider):
        return provider
    return None


def _is_clean_provider_str(value: object) -> bool:
    """Return True iff ``value`` is a non-empty, unpadded string.

    Single REJECT-ONLY contract for the provider-rejection guard. Used at
    three boundaries: wire extractor (:func:`_extract_provider`) plus the
    sensor + tracker ``async_added_to_hass`` restore guards. An upstream
    that pads its enum strings is a wire-shape regression we want loud,
    not silently normalised — so the guard rejects padding rather than
    stripping.

    **ASCII-whitespace contract.** The
    ``value == value.strip()`` check uses :meth:`str.strip` with no
    argument, which only strips characters for which
    ``str.isspace()`` returns True. Several Unicode characters
    commonly used as padding — ``U+200B`` (ZWS), ``U+200C`` (ZWNJ),
    ``U+200D`` (ZWJ), ``U+FEFF`` (BOM) — return False from
    ``isspace()`` and therefore survive both this guard and
    ``.strip()``: a ``"\u200bDERIVED"`` value would slip through as
    "clean". That gap is intentional. ABRP's ``Provider`` enum is
    closed and ASCII-only (see ``~/abrp/abrp/spec/api/common/tlm.yaml``);
    a Unicode-whitespace-padded provider value would be an upstream
    regression we want surfaced as a downstream mismatch / loud
    failure of the matching ``Provider`` literal, not silently
    sanitised at the boundary. ``NBSP`` (``U+00A0``) and other
    in-``isspace`` Unicode whitespace at edges behave differently:
    ``.strip()`` removes them, so ``value != value.strip()`` and the
    guard REJECTS them. That asymmetry vs. ZWS-family codepoints is
    also acceptable given the closed-ASCII contract — both shapes
    (slip-through-then-mismatch-downstream for ZWS-family, loud-
    rejection-at-boundary for NBSP-family) surface upstream regressions.
    """
    return isinstance(value, str) and bool(value) and value == value.strip()
