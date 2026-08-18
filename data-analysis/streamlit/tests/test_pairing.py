"""Characterization tests for data_loader.py::_pairing_score() and
auto_pair_files().

_pairing_score() is a hand-tuned heuristic scoring function (source-prefix
match, token overlap, client/server mismatch rejection, filename-pattern
preference, time proximity) with no test coverage today despite being the
thing that decides which event file gets used for every per-GameObject plot
in the app. These tests pin its current behavior -- particularly the
"client is never paired with server" guarantee -- against real filenames
pulled from ../data/, the same way test_data_loader.py pins
classify_subsystem().

Run with: python -m unittest discover -s streamlit/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from data_loader import _pairing_score, auto_pair_files  # noqa: E402


class PairingScoreTests(unittest.TestCase):
    def test_matching_source_and_tech_and_role_scores_positively(self):
        score = _pairing_score(
            "[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv",
            "[PC] fishNet_client_events_20260529_095244.csv",
            None,
            None,
        )
        self.assertGreater(score, 0)

    def test_client_stat_rejects_server_event(self):
        score = _pairing_score(
            "[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv",
            "[PC] fishNet_server_events_20260529_095237.csv",
            None,
            None,
        )
        self.assertEqual(score, float("-inf"))

    def test_server_stat_rejects_client_event(self):
        score = _pairing_score(
            "[PC] fishNet_server_profiler_stats-2026.05.29-09.52.csv",
            "[PC] fishNet_client_events_20260529_095244.csv",
            None,
            None,
        )
        self.assertEqual(score, float("-inf"))

    def test_mismatched_platform_prefix_rejects_pairing(self):
        score = _pairing_score(
            "[PC] dots_profiler_stats-2026.05.20-16.38.csv",
            "[Quest] dots_events_20260602_104358.csv",
            None,
            None,
        )
        self.assertEqual(score, float("-inf"))

    def test_quest_routed_capture_pairs_with_client_not_server(self):
        # The "server" token in this filename is traffic *direction*, not
        # an actual server role -- see _is_quest_routed_capture. Without
        # that exception this would be wrongly rejected as a client/server
        # mismatch against the (correct) client events file.
        client_score = _pairing_score(
            "[Quest] godot_server_capture_quest_capture_20260720_100309.pcap.csv",
            "[Quest] client_godot_events_20260720_100332.csv",
            None,
            None,
        )
        self.assertGreater(client_score, float("-inf"))

    def test_matching_major_token_scores_higher_than_no_match(self):
        matching = _pairing_score(
            "[PC] dots_profiler_stats-2026.05.20-16.38.csv",
            "[PC] dots_events_20260520_163843.csv",
            None,
            None,
        )
        non_matching = _pairing_score(
            "[PC] dots_profiler_stats-2026.05.20-16.38.csv",
            "[PC] gpu_events_20260520_162916.csv",
            None,
            None,
        )
        self.assertGreater(matching, non_matching)

    def test_closer_timestamp_scores_higher_when_semantics_tie(self):
        from datetime import datetime

        stat_dt = datetime(2026, 5, 20, 16, 38, 0)
        close_event_dt = datetime(2026, 5, 20, 16, 38, 5)
        far_event_dt = datetime(2026, 5, 20, 16, 50, 0)
        close_score = _pairing_score(
            "[PC] dots_profiler_stats-2026.05.20-16.38.csv",
            "[PC] dots_events_A.csv",
            stat_dt,
            close_event_dt,
        )
        far_score = _pairing_score(
            "[PC] dots_profiler_stats-2026.05.20-16.38.csv",
            "[PC] dots_events_B.csv",
            stat_dt,
            far_event_dt,
        )
        self.assertGreater(close_score, far_score)


class AutoPairFilesTests(unittest.TestCase):
    def test_pairs_each_stat_file_with_its_matching_event_file(self):
        stats = [
            ("[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv", None),
            ("[PC] fishNet_server_profiler_stats-2026.05.29-09.52.csv", None),
        ]
        events = [
            ("[PC] fishNet_client_events_20260529_095244.csv", None),
            ("[PC] fishNet_server_events_20260529_095237.csv", None),
        ]
        pairings, _debug = auto_pair_files(stats, events)
        self.assertEqual(
            pairings["[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv"],
            "[PC] fishNet_client_events_20260529_095244.csv",
        )
        self.assertEqual(
            pairings["[PC] fishNet_server_profiler_stats-2026.05.29-09.52.csv"],
            "[PC] fishNet_server_events_20260529_095237.csv",
        )

    def test_single_event_file_is_used_as_fallback_for_unmatched_stat(self):
        # No platform tag and no shared tokens between the two names, so
        # the semantic/source scoring contributes nothing and the score
        # stays below min_score -- only then does the "single event file"
        # fallback in auto_pair_files() kick in.
        stats = [("xyz_readings.csv", None)]
        events = [("abc_moments.csv", None)]
        pairings, debug = auto_pair_files(stats, events)
        self.assertEqual(pairings["xyz_readings.csv"], events[0][0])
        self.assertTrue(any("fallback" in line for line in debug))

    def test_no_match_below_min_score_leaves_stat_unpaired(self):
        stats = [("[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv", None)]
        events = [
            ("[Quest] gpu_events_20260602_105349.csv", None),
            ("[PC] fishNet_server_events_20260529_095237.csv", None),
        ]
        pairings, _debug = auto_pair_files(stats, events)
        self.assertIsNone(pairings["[PC] fishNet_client_profiler_stats-2026.05.29-09.52.csv"])


if __name__ == "__main__":
    unittest.main()
