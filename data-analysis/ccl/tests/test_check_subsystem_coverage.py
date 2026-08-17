"""Unit tests for ccl/check_subsystem_coverage.py.

Run with: python -m unittest discover -s ccl/tests -v
"""

from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from check_subsystem_coverage import check, evaluate  # noqa: E402


# A minimal, self-consistent set of registries standing in for the real
# LIBS / BASE_RAW_LIBS / NETWORKED_SUBSYSTEMS / PLANNED_COMPARISONS, so
# these tests don't depend on (or need updating alongside) the real ones.
_NETWORK_LIBS = {"Photon", "NGO"}
_BASE_LIBS = {"Base", "DOTS"}
_NETWORKED = {"Photon", "NGO"}
_PLANNED = (("Photon", "Base"), ("NGO", "Base"), ("DOTS", "Base"))


def _evaluate(observed: dict[str, int]) -> list[str]:
    return evaluate(
        Counter(observed),
        network_report_libs=_NETWORK_LIBS,
        base_raw_libs=_BASE_LIBS,
        networked_subsystems=_NETWORKED,
        planned_comparisons=_PLANNED,
    )


class EvaluateTests(unittest.TestCase):
    def test_fully_registered_subsystems_produce_no_messages(self):
        observed = {"Photon": 4, "NGO": 3, "Base": 5, "DOTS": 2}
        self.assertEqual(_evaluate(observed), [])

    def test_new_networked_subsystem_missing_from_report_libs_warns(self):
        # NewLib is networked (per this fixture's registry) but absent from
        # both network_report_libs and planned_comparisons -- both gaps
        # should be reported.
        messages = evaluate(
            Counter({"NewLib": 2}),
            network_report_libs=_NETWORK_LIBS,
            base_raw_libs=_BASE_LIBS,
            networked_subsystems=_NETWORKED | {"NewLib"},
            planned_comparisons=_PLANNED,
        )
        self.assertTrue(any("render_conclusions.py::LIBS" in m for m in messages))
        self.assertTrue(any("PLANNED_COMPARISONS" in m for m in messages))

    def test_unregistered_non_networked_subsystem_warns_about_both_reports(self):
        messages = _evaluate({"UnknownEngine": 1})
        self.assertEqual(len(messages), 2)
        self.assertTrue(any("LIBS or" in m for m in messages))
        self.assertTrue(any("PLANNED_COMPARISONS" in m for m in messages))

    def test_registered_but_unplanned_subsystem_only_warns_about_planned_comparisons(self):
        observed = {"Photon": 4, "NGO": 3, "Base": 5, "DOTS": 2, "AnotherKnown": 1}
        messages = evaluate(
            Counter(observed),
            network_report_libs=_NETWORK_LIBS | {"AnotherKnown"},
            base_raw_libs=_BASE_LIBS,
            networked_subsystems=_NETWORKED | {"AnotherKnown"},
            planned_comparisons=_PLANNED,
        )
        self.assertEqual(len(messages), 1)
        self.assertIn("AnotherKnown", messages[0])
        self.assertIn("PLANNED_COMPARISONS", messages[0])

    def test_other_is_reported_as_info_not_warning_and_skips_further_checks(self):
        messages = _evaluate({"Other": 3})
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0].startswith("[INFO]"))

    def test_empty_observed_is_empty_result(self):
        self.assertEqual(_evaluate({}), [])


class CheckAgainstRealDataTests(unittest.TestCase):
    """Guard against silent drift in the real registries: every subsystem
    actually present in ../data/ today should be fully registered. If this
    starts failing, either a new benchmark type was added without updating
    LIBS/RAW_TO_DISPLAY/PLANNED_COMPARISONS, or one of those was edited in
    a way that dropped an existing subsystem."""

    def test_real_data_has_no_coverage_warnings(self):
        messages = check()
        warnings = [m for m in messages if m.startswith("[WARN]")]
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
