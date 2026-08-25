"""Characterization tests for streamlit/data_loader.py::classify_subsystem()
and is_networked_subsystem().

`classify_subsystem()` has no test coverage today despite being imported by
both the Streamlit app and the whole ccl/ pipeline, and it's an
order-sensitive if/elif chain doing substring matching -- exactly the kind
of thing that's easy to break while "just adding one more branch." These
tests pin its CURRENT behavior against real filenames pulled from data/, so
a future refactor (e.g. into a data-driven table) can be checked against
them rather than checked by eye.

Some pinned cases are surprising, not obviously "correct" -- see the
comments on those. The point of a characterization test is to record what
the code actually does today, not to bless it as right; if a future change
wants to alter one of those, do it on purpose and update the test in the
same commit, not as a side effect of an unrelated refactor.

Run with: python -m unittest discover -s streamlit/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from data_loader import (  # noqa: E402
    NETWORKED_SUBSYSTEMS,
    NETWORKED_TECH_KEYWORDS,
    base_tech_label,
    classify_subsystem,
    is_networked_subsystem,
)


class ClassifySubsystemTests(unittest.TestCase):
    def test_photon(self):
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.photonFusion#UnityPlayerGameActivity-20260605_141059.csv"
            ),
            "Photon",
        )
        self.assertEqual(
            classify_subsystem("photon_client_profiler_stats-2026.05.20-16.29.csv"), "Photon"
        )

    def test_fishnet(self):
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.fishNet#UnityPlayerGameActivity-20260604_153302.csv"
            ),
            "FishNet",
        )
        self.assertEqual(classify_subsystem("fishNet_client_events_20260529_095244.csv"), "FishNet")

    def test_ngo(self):
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.BenchmarkNGO#UnityPlayerGameActivity-20260604_154219.csv"
            ),
            "NGO",
        )

    def test_netcode_entities(self):
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.NetcodeEntities#UnityPlayerGameActivity-20260624_162139.csv"
            ),
            "NetcodeEntities",
        )

    def test_netcode_entities_wins_over_dots_when_both_present(self):
        # Real filename: contains both "netcodeentities" and "dots" as
        # substrings. netcodeentities must be checked first (it is, in the
        # current if/elif order) or this would misclassify as DOTS.
        self.assertEqual(
            classify_subsystem("netcodeEntities_client_dots_events_20260624_162201.csv"),
            "NetcodeEntities",
        )

    def test_godot_network_via_client_or_server_token(self):
        self.assertEqual(classify_subsystem("client_godot_events_20260716_160226.csv"), "Godot Network")
        self.assertEqual(
            classify_subsystem("godot_server_capture_quest_capture_20260720_100309.pcap"),
            "Godot Network",
        )

    def test_godot_baseline_without_client_or_server_token(self):
        self.assertEqual(classify_subsystem("events_godot_20260708_105330.csv"), "Godot")
        self.assertEqual(
            classify_subsystem("com.IMT_Atlantique.godot_benchmark#GodotApp-20260811_105424.csv"),
            "Godot",
        )

    def test_godot_network_benchmark_name_is_NOT_godot_network(self):
        # Surprising but current, real behavior: the file literally has
        # "network" in its name, but "network" doesn't contain "client" or
        # "server" as a substring, so this falls through to the plain
        # "Godot" (baseline) branch, not "Godot Network". Pinned as-is --
        # if this should actually be "Godot Network", that's a real bug to
        # fix deliberately, not something a table-ification refactor
        # should silently change.
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.godot_network_benchmark#GodotApp-20260720_100334.csv"
            ),
            "Godot",
        )

    def test_dots(self):
        self.assertEqual(
            classify_subsystem("dots_profiler_stats-2026.05.20-16.38.csv"), "DOTS"
        )

    def test_dots_wins_over_base_when_both_present(self):
        # "base_DOTS" contains "base" as a substring too; "dots" must be
        # checked before "base" (it is) or this would misclassify as Base.
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.base_DOTS#UnityPlayerGameActivity-20260602_104356.csv"
            ),
            "DOTS",
        )

    def test_base_gpu(self):
        self.assertEqual(classify_subsystem("gpu_profiler_stats-2026.05.20-16.29.csv"), "Base-GPU")

    def test_base_gpu_wins_over_base_when_both_present(self):
        # Same ordering hazard as DOTS: "base_GPU" contains "base" too.
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.base_GPU#UnityPlayerGameActivity-20260602_105347.csv"
            ),
            "Base-GPU",
        )

    def test_base_via_explicit_token(self):
        self.assertEqual(
            classify_subsystem(
                "com.IMT_Atlantique.BenchmarkBase#UnityPlayerGameActivity-20260602_103308.csv"
            ),
            "Base",
        )

    def test_base_via_generic_pc_prefix_with_no_base_token(self):
        # The PC baseline stat/event pair has no "base" token at all -- see
        # the comment above this branch in classify_subsystem().
        self.assertEqual(classify_subsystem("profiler_stats-2026.05.20-16.19.csv"), "Base")
        self.assertEqual(classify_subsystem("events_20260520_161954.csv"), "Base")

    def test_unrecognized_name_is_other(self):
        self.assertEqual(classify_subsystem("some_totally_unknown_capture_file.csv"), "Other")

    def test_pc_and_quest_tags_are_stripped_before_matching(self):
        self.assertEqual(classify_subsystem("[PC] profiler_stats-2026.05.20-16.19.csv"), "Base")
        self.assertEqual(
            classify_subsystem(
                "[Quest] com.IMT_Atlantique.photonFusion#UnityPlayerGameActivity-20260605_141059.csv"
            ),
            "Photon",
        )

    def test_matching_is_case_insensitive(self):
        self.assertEqual(classify_subsystem("PHOTON_CLIENT_EVENTS.CSV"), "Photon")


class NetworkedSubsystemTests(unittest.TestCase):
    def test_networked_subsystems_are_exactly_the_five_libraries(self):
        self.assertEqual(
            NETWORKED_SUBSYSTEMS,
            {"Photon", "FishNet", "NGO", "NetcodeEntities", "Godot Network"},
        )

    def test_is_networked_subsystem_matches_the_set(self):
        for name in NETWORKED_SUBSYSTEMS:
            self.assertTrue(is_networked_subsystem(name))
        for name in ("Godot", "Base", "Base-GPU", "DOTS", "Other"):
            self.assertFalse(is_networked_subsystem(name))

    def test_networked_tech_keywords_are_exactly_the_four_networked_rules(self):
        # Godot is deliberately excluded: its rule has no is_networked=True
        # (only its "Godot Network" *variant* is networked), and it has no
        # dedicated networking library keyword of its own on the wire --
        # see app.py::_NETWORK_TOKENS' docstring for how its traffic is
        # still surfaced (generic "server"/"client"/"pcap"/"capture" tokens).
        self.assertEqual(
            NETWORKED_TECH_KEYWORDS, ("photon", "fishnet", "ngo", "netcodeentities")
        )


class BaseTechLabelTests(unittest.TestCase):
    """`base_tech_label()` backs `label_formatting.short_label()`'s tech
    tag -- it must return the *base* form even for a rule with a
    network_variant, since short_label() appends its own Client/Server
    suffix separately (see the docstring on _ClassificationRule)."""

    def test_matches_classify_subsystem_for_non_variant_rules(self):
        for name, expected in (
            ("photon_client_profiler_stats-2026.05.20-16.29.csv", "Photon"),
            ("fishNet_client_events_20260529_095244.csv", "FishNet"),
            ("dots_profiler_stats-2026.05.20-16.38.csv", "DOTS"),
            ("com.IMT_Atlantique.BenchmarkBase#UnityPlayerGameActivity-x.csv", "Base"),
        ):
            self.assertEqual(base_tech_label(name), classify_subsystem(name))

    def test_godot_network_file_returns_base_godot_not_the_variant(self):
        # classify_subsystem() returns the "Godot Network" variant for this
        # file; base_tech_label() must return plain "Godot" so
        # short_label() doesn't double up the role information when it
        # appends " Client"/" Server" afterwards.
        name = "client_godot_events_20260716_160226.csv"
        self.assertEqual(classify_subsystem(name), "Godot Network")
        self.assertEqual(base_tech_label(name), "Godot")

    def test_gpu_display_text_differs_from_raw_subsystem_name(self):
        # Deliberate divergence: subsystem_catalog.py/classify_subsystem()
        # use the hyphenated "Base-GPU" raw name; the UI legend uses a
        # space, "Base GPU".
        self.assertEqual(classify_subsystem("gpu_profiler_stats-x.csv"), "Base-GPU")
        self.assertEqual(base_tech_label("gpu_profiler_stats-x.csv"), "Base GPU")

    def test_unrecognized_name_falls_back_to_base_not_other(self):
        # Deliberately different from classify_subsystem()'s "Other"
        # fallback -- this preserves short_label()'s pre-refactor behavior
        # of always falling back to "Base" for the tech tag.
        self.assertEqual(classify_subsystem("some_totally_unknown_capture_file.csv"), "Other")
        self.assertEqual(base_tech_label("some_totally_unknown_capture_file.csv"), "Base")


if __name__ == "__main__":
    unittest.main()
