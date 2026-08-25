"""Tests for plotting.py::build_metric_figures() and its dataset-dedup
helpers.

build_metric_figures() used to be a closure over app.py's module-level
Streamlit widget state, which made it impossible to call without importing
all of app.py (which runs the whole Streamlit script -- folder scanning,
pcap tooling, st.stop() calls -- as an import side effect). It now takes
every one of those inputs as an explicit keyword argument, so these tests
exercise it directly with small synthetic DataFrames instead of the real
dataset under ../data/.

Run with: python -m unittest discover -s streamlit/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from plotting import (  # noqa: E402
    _collapse_datasets,
    _dedupe_candidates,
    _dedupe_candidates_by_group,
    _pick_canonical,
    build_metric_figures,
)


def _fps_df(fps_value: float, n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({"Frame": list(range(n)), "FPS": [fps_value] * n})


METRIC_OPTIONS = {"FPS": "fps"}


class BuildMetricFiguresTests(unittest.TestCase):
    def _stats(self):
        return [
            ("[PC] photon_client_profiler_stats-2026.05.20-16.29.csv", _fps_df(72.0)),
            ("[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv", _fps_df(60.0)),
        ]

    def test_builds_one_figure_per_selected_metric_with_a_trace_per_run(self):
        figures, skipped = build_metric_figures(
            stats_files=self._stats(),
            events_files=[],
            user_pairings={},
            selected_metric_keys=["fps"],
            metric_options=METRIC_OPTIONS,
            per_gameobject=False,
            average_runs=False,
            include_unpaired=True,
            active_line_filters=set(),
            line_filter_candidates=set(),
        )
        self.assertEqual(skipped, [])
        self.assertIn("FPS", figures)
        self.assertEqual(len(figures["FPS"].data), 2)

    def test_active_line_filter_narrows_to_selected_runs(self):
        # build_datasets() strips the file extension to form its dataset
        # label (see metrics_engine.build_datasets: `label =
        # sname.rsplit(".", 1)[0]`) -- active_line_filters/
        # line_filter_candidates must use that same stripped form, exactly
        # as app.py's real line_filter_candidates (itself built from
        # build_datasets output) does.
        stats = self._stats()
        stripped_label = stats[0][0].rsplit(".", 1)[0]
        other_stripped_label = stats[1][0].rsplit(".", 1)[0]
        figures, skipped = build_metric_figures(
            stats_files=stats,
            events_files=[],
            user_pairings={},
            selected_metric_keys=["fps"],
            metric_options=METRIC_OPTIONS,
            per_gameobject=False,
            average_runs=False,
            include_unpaired=True,
            active_line_filters={stripped_label},
            line_filter_candidates={stripped_label, other_stripped_label},
        )
        self.assertEqual(skipped, [])
        self.assertEqual(len(figures["FPS"].data), 1)

    def test_line_filter_excluding_everything_reports_metric_as_skipped(self):
        stats = self._stats()
        figures, skipped = build_metric_figures(
            stats_files=stats,
            events_files=[],
            user_pairings={},
            selected_metric_keys=["fps"],
            metric_options=METRIC_OPTIONS,
            per_gameobject=False,
            average_runs=False,
            include_unpaired=True,
            active_line_filters={"some label not present in any dataset"},
            line_filter_candidates={stats[0][0], stats[1][0]},
        )
        self.assertEqual(figures, {})
        self.assertEqual(skipped, ["FPS"])

    def test_no_stats_files_produces_no_figures_and_no_error(self):
        figures, skipped = build_metric_figures(
            stats_files=[],
            events_files=[],
            user_pairings={},
            selected_metric_keys=["fps"],
            metric_options=METRIC_OPTIONS,
            per_gameobject=False,
            average_runs=False,
            include_unpaired=True,
            active_line_filters=set(),
            line_filter_candidates=set(),
        )
        self.assertEqual(figures, {})
        self.assertEqual(skipped, [])


class DedupeHelperTests(unittest.TestCase):
    def test_pick_canonical_prefers_stats_over_events_and_trace(self):
        siblings = [
            "[PC] dots_events_20260520_163843.csv",
            "[PC] dots_profiler_stats-2026.05.20-16.38.csv",
        ]
        self.assertEqual(
            _pick_canonical(siblings), "[PC] dots_profiler_stats-2026.05.20-16.38.csv"
        )

    def test_dedupe_candidates_collapses_siblings_sharing_a_display_name(self):
        candidates = {
            "[PC] dots_events_20260520_163843.csv",
            "[PC] dots_profiler_stats-2026.05.20-16.38.csv",
            "[PC] photon_client_profiler_stats-2026.05.20-16.29.csv",
        }
        deduped = _dedupe_candidates(candidates)
        self.assertEqual(len(deduped), 2)
        self.assertIn("[PC] dots_profiler_stats-2026.05.20-16.38.csv", deduped)
        self.assertNotIn("[PC] dots_events_20260520_163843.csv", deduped)

    def test_collapse_datasets_keeps_one_entry_per_group(self):
        datasets = [
            ("[PC] dots_events_20260520_163843.csv", _fps_df(1.0)),
            ("[PC] dots_profiler_stats-2026.05.20-16.38.csv", _fps_df(2.0)),
        ]
        collapsed = _collapse_datasets(datasets)
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0][0], "[PC] dots_profiler_stats-2026.05.20-16.38.csv")

    def test_dedupe_candidates_by_group_gives_one_representative_per_run_group(self):
        candidates = {
            "[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv",
            "[PC] fishNet_server_profiler_stats-2026.05.29-09.52.csv",
        }
        deduped = _dedupe_candidates_by_group(candidates)
        self.assertEqual(len(deduped), 2)  # client and server stay distinct groups


if __name__ == "__main__":
    unittest.main()
