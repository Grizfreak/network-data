"""Unit tests for ccl/check_subsystem_coverage.py.

Run with: python -m unittest discover -s ccl/tests -v
"""

from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from check_subsystem_coverage import check, evaluate, streamlit_display_gaps  # noqa: E402


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


class StreamlitDisplayGapsTests(unittest.TestCase):
    """`streamlit_display_gaps()` guards against a *regression*: since
    base_tech_label() derives from the same _CLASSIFICATION_RULES table as
    classify_subsystem(), they should never disagree on a real filename.
    """

    def test_recognized_real_filenames_produce_no_gaps(self):
        examples = {
            "Photon": "photon_client_profiler_stats-2026.05.20-16.29.csv",
            "FishNet": "fishNet_client_events_20260529_095244.csv",
            "DOTS": "dots_profiler_stats-2026.05.20-16.38.csv",
            "Godot Network": "client_godot_events_20260716_160226.csv",
            "Base-GPU": "gpu_profiler_stats-2026.05.20-16.29.csv",
            "Base": "profiler_stats-2026.05.20-16.19.csv",
            "Other": "some_totally_unknown_capture_file.csv",
        }
        self.assertEqual(streamlit_display_gaps(examples), [])

    def test_unrecognized_example_filename_is_flagged(self):
        # A subsystem name paired with a filename base_tech_label() can't
        # actually match (simulating the two lists having drifted apart)
        # must be reported, not silently ignored.
        examples = {"NewLib": "some_file_with_no_matching_keyword.csv"}
        messages = streamlit_display_gaps(examples)
        self.assertEqual(len(messages), 1)
        self.assertIn("NewLib", messages[0])
        self.assertIn("base_tech_label()", messages[0])

    def test_real_data_has_no_display_gaps(self):
        from check_subsystem_coverage import DATA_ROOT, _observed_subsystem_examples

        examples = _observed_subsystem_examples(DATA_ROOT)
        self.assertEqual(streamlit_display_gaps(examples), [])


if __name__ == "__main__":
    unittest.main()
