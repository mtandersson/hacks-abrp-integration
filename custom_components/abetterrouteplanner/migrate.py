"""One-shot entity-registry migrations for A Better Routeplanner.

Each helper runs from :func:`async_setup_entry` once per config entry, gated
by a marker flag in ``entry.data`` so subsequent setups short-circuit. They
all share the same shape:

* scope work via :func:`er.async_entries_for_config_entry` so foreign entries
  on the same instance are untouched;
* perform the in-place registry mutation;
* flip a ``CONF_*_MIGRATION_DONE`` flag on ``entry.data`` via
  :meth:`ConfigEntries.async_update_entry`.

Extracted from ``__init__.py`` to keep that module focused on
setup/unload/runtime_data.
"""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_CATALOG_SENSORS_CLEANUP_DONE, CONF_UX_B_MIGRATION_DONE

if TYPE_CHECKING:
    from . import AbetterrouteplannerConfigEntry

# Legacy unique_id suffixes for the three catalog-derived diagnostic sensors
# that have since been removed. The full legacy unique_id shape is
# ``<entry.unique_id>_<vehicle_id>_{maker|model|year}`` — the
# ``async_migrate_drop_catalog_sensors`` cleanup matches the trailing suffix
# AND verifies the middle segment is a digit-only vehicle_id, so unrelated
# rows whose unique_id coincidentally ends in ``_maker`` / ``_model`` /
# ``_year`` (e.g. a future telemetry key ``model_year`` whose unique_id
# would end in ``_model_year``) survive intact.
#
# Suffix-collision audit: the current telemetry sensor keys all end in
# distinct strings; none collide with the three dropped suffixes above.
# Future contributors adding a new telemetry metric must NOT use a key
# matching one of these three suffixes (e.g. a sensor key literally named
# ``year``) or this migration would wrongly remove them on legacy installs
# that re-run the cleanup. Adding a longer key such as ``model_year`` is
# safe because the digit-middle guard rejects
# ``<scope>_<vehicle_id>_model_year`` (the middle segment between prefix
# and the matched ``_year`` suffix is ``<vehicle_id>_model``, which is
# not digit-only).
_DROPPED_CATALOG_SENSOR_SUFFIXES: tuple[str, ...] = ("_maker", "_model", "_year")


def async_migrate_ux_b_hidden_by(
    hass: HomeAssistant, entry: AbetterrouteplannerConfigEntry
) -> None:
    """Clear stale ``hidden_by=INTEGRATION`` rows from UX-B-era installs.

    UX-B hid absent-metric sensors via
    ``_attr_entity_registry_visible_default = False`` plus a
    ``_handle_coordinator_update`` unhide. UX-C replaced that pattern
    with lazy/dispatcher creation: an entity only registers once its
    ``value_fn`` first returns non-None. UX-B-era ``hidden_by=INTEGRATION``
    flags survived the upgrade and now permanently mask the affected
    entities from the UI even after a fresh frame arrives.

    Runs once per entry, gated by ``CONF_UX_B_MIGRATION_DONE`` in
    ``entry.data``. Scoped to this entry's registry rows
    (``async_entries_for_config_entry``) so other integrations and other
    ABRP entries on the same instance are untouched. User-initiated hides
    (``RegistryEntryHider.USER``) are preserved — only the
    ``INTEGRATION`` rows are cleared. Fresh post-UX-C installs hit the
    same code path and simply no-op the loop before setting the flag.

    Precedent: ``homeassistant/components/group/__init__.py:163-166`` and
    ``homeassistant/components/switch_as_x/__init__.py:139-140`` use the
    same ``hidden_by=None`` clear shape.
    """
    if entry.data.get(CONF_UX_B_MIGRATION_DONE):
        return
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.hidden_by is er.RegistryEntryHider.INTEGRATION:
            entity_registry.async_update_entity(entity_entry.entity_id, hidden_by=None)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_UX_B_MIGRATION_DONE: True}
    )


def async_migrate_drop_catalog_sensors(
    hass: HomeAssistant, entry: AbetterrouteplannerConfigEntry
) -> None:
    """Remove legacy ``_maker`` / ``_model`` / ``_year`` registry rows.

    The integration previously shipped three catalog-derived diagnostic
    sensors per vehicle (``AbrpMakerSensor``, ``AbrpModelSensor``,
    ``AbrpYearSensor``) registered under unique_ids
    ``<entry.unique_id>_<vehicle_id>_{maker|model|year}``. Those sensor
    classes have been removed and the same nameplate information now
    surfaces via :attr:`DeviceInfo.model`. Without active cleanup, legacy
    installs would keep the orphan registry rows forever — the rows
    render as permanently-unavailable entities on the device card.

    Matching is exact-token, not substring: the unique_id must
    decompose as ``<entry.unique_id>_<digit_vehicle_id>_<suffix>`` for
    one of the three suffixes. This rejects future telemetry keys that
    happen to end with ``_year`` etc. (e.g. ``model_year`` whose
    unique_id ends in ``_year`` but whose middle segment between the
    prefix and the suffix is not digit-only).

    Runs once per entry, gated by ``CONF_CATALOG_SENSORS_CLEANUP_DONE``
    in ``entry.data``. Scoped via ``async_entries_for_config_entry`` so
    foreign entries (other ABRP accounts on the same instance,
    unrelated integrations that happen to share the substring) are
    untouched. Fresh installs hit this path with no matching rows and
    simply flip the flag.

    Mirrors :func:`async_migrate_ux_b_hidden_by` one-for-one in shape
    and call-site placement — keeps the two migrations visually parallel
    for future readers.
    """
    if entry.data.get(CONF_CATALOG_SENSORS_CLEANUP_DONE):
        return
    entity_registry = er.async_get(hass)
    scope_prefix = f"{entry.unique_id}_"
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        unique_id = entity_entry.unique_id
        if not unique_id.startswith(scope_prefix):
            continue
        remainder = unique_id[len(scope_prefix) :]
        for suffix in _DROPPED_CATALOG_SENSOR_SUFFIXES:
            if not remainder.endswith(suffix):
                continue
            middle = remainder[: -len(suffix)]
            if middle.isdigit():
                entity_registry.async_remove(entity_entry.entity_id)
                break
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CATALOG_SENSORS_CLEANUP_DONE: True}
    )
