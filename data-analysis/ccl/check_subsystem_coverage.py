"""Read-only check: does every subsystem actually present under ../data/
show up in the report-facing "known subsystem" lists?

A subsystem `classify_subsystem()` can identify but that isn't registered
in `render_conclusions.py::LIBS`, `render_base_conclusions.py::RAW_TO_DISPLAY`,
or `load_analysis.py::PLANNED_COMPARISONS` gets silently dropped from
whichever report forgot it -- no error, no missing row, just absence. This
script turns that into a printed warning instead, so adding a new
benchmark type (new networking library, new engine variant) surfaces
exactly which of those lists still need the new name.

Doesn't write anything and doesn't depend on analyze_data.py or
load_analysis.py having been run first -- it re-derives "what subsystems
exist" straight from the raw file names under ../data/, so it's safe to
run at any time, independently of the rest of the pipeline.

Also checks the Streamlit app's display layer (`base_tech_label()`, used by
`../streamlit/label_formatting.py::short_label()`): since that function now
derives its tech tag from the same `_CLASSIFICATION_RULES` table as
`classify_subsystem()` (rather than a separately hand-maintained elif
chain), the two should never disagree on whether a given file is
recognized. This check exists to catch a *regression* -- e.g. someone
reintroducing a bespoke branch in `short_label()` instead of extending
`_CLASSIFICATION_RULES` -- not a currently-known gap.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "streamlit"))
from data_loader import (  # noqa: E402
    NETWORKED_SUBSYSTEMS,
    base_tech_label,
    classify_subsystem,
)

from load_analysis import PLANNED_COMPARISONS
from render_base_conclusions import BASE_RAW_LIBS
from render_conclusions import LIBS as NETWORK_REPORT_LIBS

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


def _observed_subsystems(data_root: Path) -> Counter:
    counts: Counter = Counter()
    for csv_path in sorted(data_root.glob("*/*.csv")):
        counts[classify_subsystem(csv_path.name)] += 1
    return counts


def _observed_subsystem_examples(data_root: Path) -> dict[str, str]:
    """One example filename per observed subsystem -- `base_tech_label()`
    (unlike `classify_subsystem()`, which this module otherwise only deals
    with as plain subsystem-name strings) needs an actual filename to
    classify, for the display-layer check below."""
    examples: dict[str, str] = {}
    for csv_path in sorted(data_root.glob("*/*.csv")):
        examples.setdefault(classify_subsystem(csv_path.name), csv_path.name)
    return examples


def streamlit_display_gaps(examples: dict[str, str]) -> list[str]:
    """Flag any subsystem `classify_subsystem()` recognizes whose
    `base_tech_label()` falls back to the generic "Base" tag -- i.e. the
    Streamlit app's legend/quick filters would no longer distinguish it
    from the baseline scene.

    Pure function of a {subsystem: example_filename} mapping so it's
    testable without real data, same as `evaluate()`. Should never fire
    today: `base_tech_label()` and `classify_subsystem()` share the same
    `_CLASSIFICATION_RULES` table, so they can't disagree on whether a
    given file is recognized unless someone reintroduces a separate,
    independently-maintained list (which is exactly the regression this
    guards against -- see the module docstring).
    """
    messages: list[str] = []
    for subsystem, example_name in sorted(examples.items()):
        if subsystem in ("Other", "Base"):
            continue
        if base_tech_label(example_name) == "Base":
            messages.append(
                f"[WARN] '{subsystem}' (e.g. {example_name}) is recognized by "
                f"classify_subsystem() but base_tech_label() falls back to the "
                f"generic 'Base' tag for it -- the Streamlit app's legend and "
                f"quick filters won't distinguish it from the baseline scene."
            )
    return messages


def _planned_subsystems(planned_comparisons) -> set[str]:
    subsystems: set[str] = set()
    for a, b in planned_comparisons:
        subsystems.add(a)
        subsystems.add(b)
    return subsystems


def evaluate(
    observed: Counter,
    *,
    network_report_libs,
    base_raw_libs,
    networked_subsystems,
    planned_comparisons,
) -> list[str]:
    """Pure comparison logic, independent of the filesystem -- takes the
    observed subsystem counts and the "known" registries as plain
    arguments so it's testable without real data or monkeypatching."""
    planned = _planned_subsystems(planned_comparisons)
    messages: list[str] = []

    for subsystem, n in sorted(observed.items()):
        if subsystem == "Other":
            messages.append(
                f"[INFO] {n} file(s) classify_subsystem() could not identify "
                f"(tagged 'Other') -- see conclusions.md caveat #3."
            )
            continue

        if subsystem in networked_subsystems:
            if subsystem not in network_report_libs:
                messages.append(
                    f"[WARN] '{subsystem}' ({n} file(s)) is networked but missing "
                    f"from render_conclusions.py::LIBS -- it will be silently "
                    f"excluded from conclusions.md."
                )
        elif subsystem not in base_raw_libs:
            messages.append(
                f"[WARN] '{subsystem}' ({n} file(s)) is classified but not "
                f"registered in render_conclusions.py::LIBS or "
                f"render_base_conclusions.py::RAW_TO_DISPLAY -- it will be "
                f"silently excluded from both reports."
            )

        if subsystem not in planned:
            messages.append(
                f"[WARN] '{subsystem}' ({n} file(s)) has no entry in "
                f"load_analysis.py::PLANNED_COMPARISONS -- no load-based "
                f"comparison will run for it (unless you pass --comparisons all)."
            )

    return messages


def check(data_root: Path = DATA_ROOT) -> list[str]:
    """Return a list of warning/info strings (empty if fully registered)."""
    observed = _observed_subsystems(data_root)
    messages = evaluate(
        observed,
        network_report_libs=NETWORK_REPORT_LIBS,
        base_raw_libs=BASE_RAW_LIBS,
        networked_subsystems=NETWORKED_SUBSYSTEMS,
        planned_comparisons=PLANNED_COMPARISONS,
    )
    messages += streamlit_display_gaps(_observed_subsystem_examples(data_root))
    return messages


def main():
    messages = check()
    warn_count = sum(1 for m in messages if m.startswith("[WARN]"))
    if not messages:
        print("All subsystems found in data/ are registered in every report.")
        return
    print(f"{len(messages)} note(s), {warn_count} warning(s):\n")
    for m in messages:
        print(m)


if __name__ == "__main__":
    main()
