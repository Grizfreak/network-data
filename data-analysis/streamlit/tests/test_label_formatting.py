"""Characterization tests for streamlit/label_formatting.py.

`short_label()` and `_run_group_key()` are the second and third
independent, order-sensitive label-matching tables in this codebase
(alongside `data_loader.classify_subsystem()`, see test_data_loader.py) --
and until this module was extracted, they lived inline in `app.py`, which
runs the full Streamlit script as a side effect of import and so couldn't
be unit tested cheaply. These tests pin current behavior against real
filenames pulled from `../data/`, the same way test_data_loader.py does.

Run with: python -m unittest discover -s streamlit/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from label_formatting import (  # noqa: E402
    STANDARD_METRIC_KEYS,
    _group_key_to_display,
    _is_client_label,
    _is_godot_label,
    _is_networked_tech_label,
    _is_pc_label,
    _is_quest_label,
    _is_server_label,
    _keep_for_quest_standard_metric,
    _run_group_key,
    _split_subsystem_label,
    _type_tag_for,
    short_label,
)


class ShortLabelTests(unittest.TestCase):
    def test_pc_photon_client_stats_gets_client_suffix_and_timestamp(self):
        self.assertEqual(
            short_label("[PC] photon_client_profiler_stats-2026.05.20-16.29.csv"),
            "PC · Photon Client · 20.1629",
        )

    def test_pc_fishnet_server_events_gets_server_suffix(self):
        self.assertEqual(
            short_label("[PC] fishNet_server_events_20260529_095237.csv"),
            "PC · FishNet Server · 29.0952",
        )

    def test_quest_bare_trace_for_networked_tech_is_treated_as_client(self):
        # No `_client_`/`_server_` token in this filename at all -- FishNet
        # has no non-networked baseline mode, so the bare Quest trace is
        # unambiguously the client run (see the docstring in
        # label_formatting.short_label for why this doesn't apply to Godot).
        self.assertEqual(
            short_label(
                "[Quest] com.IMT_Atlantique.fishNet#UnityPlayerGameActivity-20260604_153302.csv"
            ),
            "Quest · FishNet Client · 04.1533",
        )

    def test_quest_godot_trace_is_always_labeled_client_even_for_baseline_runs(self):
        # Surprising but current, real behavior: unlike _run_group_key()
        # (which gives the non-networked-baseline Godot trace its own
        # distinct "Trace" role, see RunGroupKeyTests below),
        # short_label()'s Godot-trace branch appends " Client"
        # unconditionally for ANY Godot Android trace file, baseline or
        # networked -- it doesn't check for a "network" token the way
        # _run_group_key does. Pinned as-is; if display should distinguish
        # the two, that's a deliberate fix, not a side effect of a
        # refactor.
        self.assertEqual(
            short_label(
                "[Quest] com.example.godot_benchmark#GodotApp-20260710_150743.csv"
            ),
            "Quest · Godot Client · 10.1507",
        )

    def test_quest_routed_capture_is_client_despite_server_token(self):
        # The "server" token here describes traffic *direction* (captured
        # en route to the server), not an actual server role -- the Quest
        # headset never hosts a server.
        self.assertEqual(
            short_label(
                "[Quest] godot_server_capture_quest_capture_20260720_100309.pcap.csv"
            ),
            "Quest · Godot Client · 20.1003",
        )

    def test_pc_real_server_capture_is_server(self):
        self.assertEqual(
            short_label("[PC] netcodeEntities_server_capture_20260625_094135.pcap.csv"),
            "PC · NetcodeEntities Server · 25.0941",
        )

    def test_type_tag_disambiguates_siblings_sharing_a_display_name(self):
        stats = "[PC] dots_profiler_stats-2026.05.20-16.38.csv"
        events = "[PC] dots_events_20260520_163843.csv"
        all_labels = [stats, events]
        self.assertEqual(short_label(stats, all_labels), "PC · DOTS · 20.1638 (stats)")
        self.assertEqual(short_label(events, all_labels), "PC · DOTS · 20.1638 (events)")

    def test_unknown_tech_falls_back_to_base(self):
        # No error, no distinct tag -- a keyword not covered by the
        # if/elif chain silently renders as "Base". This is exactly the
        # failure mode documented in ../README.md's
        # "Adding a new benchmark type" section: a new tech's short_label
        # branch is easy to forget, and this is what forgetting it looks
        # like from the user's side.
        self.assertEqual(
            short_label("[PC] some_new_engine_client_profiler_stats-2026.05.20-16.29.csv"),
            "PC · Base Client · 20.1629",
        )


class TypeTagTests(unittest.TestCase):
    def test_events_file(self):
        self.assertEqual(_type_tag_for("dots_events_20260520_163843.csv"), "events")

    def test_stats_file(self):
        self.assertEqual(_type_tag_for("dots_profiler_stats-2026.05.20-16.38.csv"), "stats")

    def test_android_trace_file(self):
        self.assertEqual(
            _type_tag_for(
                "com.IMT_Atlantique.fishNet#UnityPlayerGameActivity-20260604_153302.csv"
            ),
            "trace",
        )

    def test_godot_android_trace_file(self):
        self.assertEqual(
            _type_tag_for("com.example.godot_benchmark#GodotApp-20260710_150743.csv"),
            "trace",
        )

    def test_pcap_capture_file(self):
        self.assertEqual(
            _type_tag_for("fishnet_client_capture_20260529_095237.pcap.csv"), "pcap"
        )

    def test_unrecognized_file_has_no_tag(self):
        self.assertEqual(_type_tag_for("some_totally_unrecognized_file.csv"), "")


class RoleLabelPredicateTests(unittest.TestCase):
    def test_is_client_label_requires_explicit_token(self):
        self.assertTrue(_is_client_label("[PC] photon_client_profiler_stats-2026.05.20-16.29.csv"))
        self.assertFalse(_is_client_label("[PC] dots_profiler_stats-2026.05.20-16.38.csv"))

    def test_is_server_label_is_pc_only(self):
        self.assertTrue(_is_server_label("[PC] fishNet_server_events_20260529_095237.csv"))
        # Quest never hosts a server -- a "*_server_*" Quest file is a
        # routed-traffic PCAP capture, not a real server role.
        self.assertFalse(
            _is_server_label("[Quest] godot_server_capture_quest_capture_20260720_100309.pcap.csv")
        )

    def test_platform_predicates(self):
        self.assertTrue(_is_pc_label("[PC] dots_profiler_stats-2026.05.20-16.38.csv"))
        self.assertFalse(_is_quest_label("[PC] dots_profiler_stats-2026.05.20-16.38.csv"))
        self.assertTrue(_is_quest_label("[Quest] gpu_events_20260602_105349.csv"))


class RunGroupKeyTests(unittest.TestCase):
    def test_client_and_server_of_same_run_stay_distinct(self):
        client_key = _run_group_key("[PC] fishNet_client_events_20260529_095244.csv")
        server_key = _run_group_key("[PC] fishNet_server_events_20260529_095237.csv")
        self.assertEqual(client_key, ("PC", "FishNet", "Client"))
        self.assertEqual(server_key, ("PC", "FishNet", "Server"))
        self.assertNotEqual(client_key, server_key)

    def test_godot_client_server_prefix_tokens_are_not_merged(self):
        # Regression case called out in the docstring: Godot Network files
        # use a bare "client_"/"server_" prefix, not "_client_"/"_server_"
        # wrapped in underscores, so the stricter _is_client_label /
        # _is_server_label predicates can't be used here.
        client_key = _run_group_key("[PC] client_godot_events_20260716_160226.csv")
        server_key = _run_group_key(
            "[PC] godot_server_capture_20260716_160227.pcap.csv"
        )
        self.assertEqual(client_key[2], "Client")
        self.assertEqual(server_key[2], "Server")

    def test_quest_routed_capture_is_forced_client_not_server(self):
        key = _run_group_key(
            "[Quest] godot_server_capture_quest_capture_20260720_100309.pcap.csv"
        )
        self.assertEqual(key, ("Quest", "Godot Network", "Client"))

    def test_quest_godot_trace_on_networked_run_gets_its_own_role(self):
        # Must NOT collide with the plain "" role used by the Godot
        # baseline group (see the docstring on _run_group_key).
        key = _run_group_key(
            "[Quest] com.IMT_Atlantique.godot_network_benchmark#GodotApp-20260720_100334.csv"
        )
        self.assertEqual(key, ("Quest", "Godot", "Trace (network run)"))

    def test_quest_bare_networked_tech_trace_joins_client_group(self):
        key = _run_group_key(
            "[Quest] com.IMT_Atlantique.fishNet#UnityPlayerGameActivity-20260604_153302.csv"
        )
        self.assertEqual(key, ("Quest", "FishNet", "Client"))

    def test_group_key_to_display_matches_short_label_style(self):
        self.assertEqual(
            _group_key_to_display(("PC", "FishNet", "Client")), "PC · FishNet Client"
        )
        self.assertEqual(_group_key_to_display(("PC", "Base", "")), "PC · Base")


class MiscHelperTests(unittest.TestCase):
    def test_split_subsystem_label(self):
        self.assertEqual(
            _split_subsystem_label("[PC] dots_profiler_stats-2026.05.20-16.38.csv"),
            ("PC", "dots_profiler_stats-2026.05.20-16.38.csv"),
        )
        self.assertEqual(
            _split_subsystem_label("[Quest] gpu_events_20260602_105349.csv"),
            ("Quest", "gpu_events_20260602_105349.csv"),
        )
        self.assertEqual(_split_subsystem_label("no_tag_here.csv"), ("Unknown", "no_tag_here.csv"))

    def test_is_networked_tech_label(self):
        self.assertTrue(_is_networked_tech_label("[PC] photon_client_profiler_stats-2026.05.20-16.29.csv"))
        self.assertFalse(_is_networked_tech_label("[PC] dots_profiler_stats-2026.05.20-16.38.csv"))

    def test_is_godot_label(self):
        self.assertTrue(_is_godot_label("[PC] client_godot_events_20260716_160226.csv"))
        self.assertFalse(_is_godot_label("[PC] dots_profiler_stats-2026.05.20-16.38.csv"))

    def test_keep_for_quest_standard_metric_drops_godot_trace(self):
        # The Android trace re-export of a Godot run must be dropped here so
        # it doesn't survive as an unaveraged singleton alongside the
        # profiler_stats source that's actually plotted.
        self.assertFalse(
            _keep_for_quest_standard_metric(
                "[Quest] com.example.godot_benchmark#GodotApp-20260710_150743.csv"
            )
        )
        self.assertTrue(
            _keep_for_quest_standard_metric(
                "[Quest] godot_profiler_stats_2026-07-10T15-07-40.csv"
            )
        )

    def test_keep_for_quest_standard_metric_requires_imt_atlantique_prefix(self):
        self.assertTrue(
            _keep_for_quest_standard_metric(
                "[Quest] com.IMT_Atlantique.fishNet#UnityPlayerGameActivity-20260604_153302.csv"
            )
        )
        self.assertFalse(_keep_for_quest_standard_metric("[Quest] fishNet_client_events_20260604_152707.csv"))

    def test_standard_metric_keys_constant(self):
        self.assertEqual(STANDARD_METRIC_KEYS, ("fps", "memory", "cpu", "gpu"))


if __name__ == "__main__":
    unittest.main()
