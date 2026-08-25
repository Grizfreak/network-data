"""Single source of truth for which subsystems each conclusion report
covers.

Previously `render_conclusions.py::LIBS` and `render_base_conclusions.py::
DISPLAY_LIBS`/`RAW_TO_DISPLAY` were two independent hand-maintained lists.
Same pattern as `metrics_catalog.py`, applied to subsystems: each entry is
tagged by category so both `render_*.py` scripts filter from here instead
of each keeping its own list.

`raw_name` is what `../streamlit/data_loader.py::classify_subsystem()`
returns. `display_name` is what the report shows -- identical to
`raw_name` for network libraries, but base-engine variants get a friendlier
name (e.g. raw `"Base-GPU"` displays as `"Unity GPU"`). `baseline_of` is
the raw name of the subsystem this one should be statistically compared
against (its local baseline, or `"Base"` for a non-networked variant) --
`None` for `"Base"` itself, the one subsystem nothing else compares it to.
"""
from __future__ import annotations

from dataclasses import dataclass

CATEGORY_NETWORK_LIBRARY = "network_library"
CATEGORY_BASE_ENGINE = "base_engine"


@dataclass(frozen=True)
class SubsystemSpec:
    raw_name: str
    display_name: str
    category: str
    baseline_of: str | None = None


SUBSYSTEMS: list[SubsystemSpec] = [
    SubsystemSpec("Photon", "Photon", CATEGORY_NETWORK_LIBRARY, baseline_of="Base"),
    SubsystemSpec("NGO", "NGO", CATEGORY_NETWORK_LIBRARY, baseline_of="Base"),
    SubsystemSpec("FishNet", "FishNet", CATEGORY_NETWORK_LIBRARY, baseline_of="Base"),
    SubsystemSpec("NetcodeEntities", "NetcodeEntities", CATEGORY_NETWORK_LIBRARY, baseline_of="DOTS"),
    SubsystemSpec("Godot Network", "Godot Network", CATEGORY_NETWORK_LIBRARY, baseline_of="Godot"),
    SubsystemSpec("Godot", "Godot", CATEGORY_BASE_ENGINE, baseline_of="Base"),
    SubsystemSpec("Base", "Unity base", CATEGORY_BASE_ENGINE, baseline_of=None),
    SubsystemSpec("Base-GPU", "Unity GPU", CATEGORY_BASE_ENGINE, baseline_of="Base"),
    SubsystemSpec("DOTS", "Unity DOTS", CATEGORY_BASE_ENGINE, baseline_of="Base"),
]

# Used by render_conclusions.py -- the network-library report. Raw and
# display names are identical for this category, so this doubles as both.
NETWORK_LIBS = [s.display_name for s in SUBSYSTEMS if s.category == CATEGORY_NETWORK_LIBRARY]

# Used by render_base_conclusions.py -- the base-engine report.
BASE_ENGINE_DISPLAY = [s.display_name for s in SUBSYSTEMS if s.category == CATEGORY_BASE_ENGINE]
RAW_TO_DISPLAY = {
    s.raw_name: s.display_name for s in SUBSYSTEMS if s.category == CATEGORY_BASE_ENGINE
}

# Used by load_analysis.py -- which subsystem pairs are meaningful to test
# for statistical significance (Pipeline B's --comparisons planned, the
# default). Order doesn't matter: consumers only check set membership.
PLANNED_COMPARISONS: tuple[tuple[str, str], ...] = tuple(
    (s.raw_name, s.baseline_of) for s in SUBSYSTEMS if s.baseline_of is not None
)
