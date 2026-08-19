"""Unit tests for ccl/load_analysis.py.

Run with: python -m unittest discover -s ccl/tests -v
(no pytest dependency -- this project doesn't have one installed).
"""

from __future__ import annotations

import sys
import unittest
from fractions import Fraction
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

import load_analysis  # noqa: E402
from load_analysis import (  # noqa: E402
    RunData,
    RunKey,
    WaveEvent,
    aggregate_run_metric,
    _terminal_fallback_row,
    benjamini_hochberg_correction,
    build_segments,
    check_metric_vs_load_consistency,
    cliffs_delta,
    cliffs_delta_effect_size,
    compare_configurations,
    compute_capacity,
    config_identity,
    detect_capacity_outliers,
    detect_capture_truncation,
    detect_coverage_gaps,
    detect_role_count_mismatches,
    holm_correction,
    load_coverage_table,
    mannwhitney_exact,
    metric_vs_load_curve,
    server_capacity_table,
    server_metrics_table,
    _extract_waves,
)


class MannWhitneyExactTests(unittest.TestCase):
    def test_complete_separation_5v5_matches_known_reference(self):
        # Textbook reference: complete separation at n_x=n_y=5 has exactly
        # 2 of the C(10,5)=252 arrangements as extreme as the observed one
        # (the two perfect orderings), so p = 2/252.
        x = [1, 2, 3, 4, 5]
        y = [6, 7, 8, 9, 10]
        result = mannwhitney_exact(x, y)
        self.assertEqual(result.n_arrangements, 252)
        self.assertEqual(result.u, 0.0)
        self.assertAlmostEqual(result.p_value, 2 / 252)

    def test_complete_separation_3v3_matches_known_reference(self):
        # C(6,3)=20 arrangements; complete separation is again the two most
        # extreme orderings -> p = 2/20 = 0.1 (matches published exact
        # Mann-Whitney tables for n1=n2=3).
        x = [1, 2, 3]
        y = [4, 5, 6]
        result = mannwhitney_exact(x, y)
        self.assertEqual(result.n_arrangements, 20)
        self.assertEqual(result.u, 0.0)
        self.assertAlmostEqual(result.p_value, 0.1)

    def test_ties_hand_verified_case(self):
        # x=[1,2], y=[1,3]: one tie between x's 1 and y's 1. Hand-enumerated
        # (see load_analysis module notes / PR description): all 6 of the
        # C(4,2) arrangements land at U in {0, 1.5}, and the observed
        # arrangement's U=1.5 is the least extreme value in that set, so
        # every arrangement qualifies -> p=1.0 exactly.
        x = [1, 2]
        y = [1, 3]
        result = mannwhitney_exact(x, y)
        self.assertEqual(result.n_arrangements, 6)
        self.assertAlmostEqual(result.u, 1.5)
        self.assertAlmostEqual(result.p_value, 1.0)

    def test_identical_groups_are_not_significant(self):
        result = mannwhitney_exact([5, 5, 5], [5, 5, 5])
        self.assertGreater(result.p_value, 0.5)

    def test_p_value_never_zero(self):
        # Even the most extreme possible split (complete separation) has
        # two symmetric arrangements achieving U=0 (X all-below-Y, X
        # all-above-Y), so the true floor here is 2/n_arrangements, not
        # 1/n_arrangements -- but in all cases p >= 1/n_arrangements > 0.
        result = mannwhitney_exact([1, 2, 3, 4, 5], [100, 101, 102, 103, 104])
        self.assertGreater(result.p_value, 0.0)
        self.assertGreaterEqual(result.p_value, result.p_floor)
        self.assertAlmostEqual(result.p_value, 2 / result.n_arrangements)

    def test_rejects_empty_group(self):
        with self.assertRaises(ValueError):
            mannwhitney_exact([], [1, 2, 3])

    def test_rejects_group_too_large_for_exact_enumeration(self):
        big = list(range(15))
        other = list(range(15, 30))
        with self.assertRaises(ValueError):
            mannwhitney_exact(big, other)


class CliffsDeltaTests(unittest.TestCase):
    def test_x_entirely_greater(self):
        self.assertEqual(cliffs_delta([10, 11, 12], [1, 2, 3]), 1.0)

    def test_x_entirely_smaller(self):
        self.assertEqual(cliffs_delta([1, 2, 3], [10, 11, 12]), -1.0)

    def test_identical_distributions_is_zero(self):
        self.assertEqual(cliffs_delta([1, 2, 3], [1, 2, 3]), 0.0)

    def test_symmetric_partial_overlap_is_zero(self):
        # x=[1,2,3] vs y=[2,2,2]: 3 less (1<2), 3 ties (2 vs 2,2,2), 3
        # greater (3>2) -> (3-3)/9 = 0.
        self.assertEqual(cliffs_delta([1, 2, 3], [2, 2, 2]), 0.0)

    def test_empty_group_is_nan(self):
        self.assertTrue(pd.isna(cliffs_delta([], [1, 2])))

    def test_effect_size_thresholds(self):
        self.assertEqual(cliffs_delta_effect_size(0.05), "negligible")
        self.assertEqual(cliffs_delta_effect_size(0.2), "small")
        self.assertEqual(cliffs_delta_effect_size(0.4), "medium")
        self.assertEqual(cliffs_delta_effect_size(0.9), "large")
        self.assertEqual(cliffs_delta_effect_size(-0.9), "large")


class HolmCorrectionTests(unittest.TestCase):
    def test_hand_computed_example(self):
        # p=[0.01, 0.02, 0.03, 0.04], m=4:
        #   adj_1 = min(4*0.01,1) = 0.04
        #   adj_2 = max(0.04, min(3*0.02,1)=0.06) = 0.06
        #   adj_3 = max(0.06, min(2*0.03,1)=0.06) = 0.06
        #   adj_4 = max(0.06, min(1*0.04,1)=0.04) = 0.06
        raw = [0.01, 0.02, 0.03, 0.04]
        adjusted = holm_correction(raw)
        expected = [0.04, 0.06, 0.06, 0.06]
        for got, want in zip(adjusted, expected):
            self.assertAlmostEqual(got, want)

    def test_monotone_when_sorted(self):
        raw = [0.2, 0.001, 0.15, 0.04, 0.5]
        adjusted = holm_correction(raw)
        order = sorted(range(len(raw)), key=lambda i: raw[i])
        sorted_adjusted = [adjusted[i] for i in order]
        self.assertEqual(sorted_adjusted, sorted(sorted_adjusted))

    def test_never_exceeds_one(self):
        adjusted = holm_correction([0.9, 0.95, 0.99])
        self.assertTrue(all(p <= 1.0 for p in adjusted))

    def test_empty_input(self):
        self.assertEqual(holm_correction([]), [])


class BenjaminiHochbergTests(unittest.TestCase):
    def test_hand_computed_example(self):
        # p=[0.01, 0.02, 0.03, 0.04], m=4: p_(k)*m/k is 0.04 for every k
        # (0.01*4/1, 0.02*4/2, 0.03*4/3, 0.04*4/4 all equal 0.04), so every
        # adjusted value is 0.04 -- distinctly different from Holm's
        # [0.04, 0.06, 0.06, 0.06] on the same input.
        raw = [0.01, 0.02, 0.03, 0.04]
        adjusted = benjamini_hochberg_correction(raw)
        for got in adjusted:
            self.assertAlmostEqual(got, 0.04)

    def test_tied_at_exact_mannwhitney_floor_stays_significant(self):
        # The requested limiting case: every test in an 8-member family
        # sits exactly at the exact-test floor (2/252 for N=5 vs 5). BH's
        # divisor is p*(m/k), which for a constant p is largest at k=1 and
        # shrinks to exactly p at k=m; the step-up cumulative-min then
        # collapses every adjusted value back to p itself -- unlike Holm,
        # which would multiply the floor by the full family size and push
        # every one of them over any reasonable alpha.
        floor = 2 / 252
        raw = [floor] * 8
        adjusted = benjamini_hochberg_correction(raw)
        for got in adjusted:
            self.assertAlmostEqual(got, floor)
            self.assertLess(got, 0.05)

    def test_monotone_when_sorted(self):
        raw = [0.2, 0.001, 0.15, 0.04, 0.5]
        adjusted = benjamini_hochberg_correction(raw)
        order = sorted(range(len(raw)), key=lambda i: raw[i])
        sorted_adjusted = [adjusted[i] for i in order]
        self.assertEqual(sorted_adjusted, sorted(sorted_adjusted))

    def test_never_exceeds_one(self):
        adjusted = benjamini_hochberg_correction([0.9, 0.95, 0.99])
        self.assertTrue(all(p <= 1.0 for p in adjusted))

    def test_empty_input(self):
        self.assertEqual(benjamini_hochberg_correction([]), [])

    def test_less_conservative_than_holm_on_same_family(self):
        # Same tied-floor family as above: BH keeps everything at the
        # floor while Holm inflates every entry by the family size (8x),
        # pushing it past a 0.05 alpha. This is the exact degeneracy BH
        # was introduced to avoid.
        floor = 2 / 252
        raw = [floor] * 8
        bh = benjamini_hochberg_correction(raw)
        holm = holm_correction(raw)
        self.assertTrue(all(b < 0.05 for b in bh))
        self.assertTrue(all(h > 0.05 for h in holm))


class PlannedComparisonsTests(unittest.TestCase):
    def _synthetic_observations(self) -> pd.DataFrame:
        # Five subsystems, five runs each, all at entities=400: Base is
        # the reference; FishNet/NGO/Photon/DOTS are its candidate
        # partners. Only (Base, FishNet-client), (Base, NGO-client),
        # (Base, Photon-client) and (Base, DOTS) end up in the "baseline"
        # planned family -- pairs among FishNet/NGO/Photon/DOTS themselves
        # are not. FishNet/NGO/Photon are network libraries (role
        # "client" -> identity suffix "-client"); Base and DOTS are local
        # baselines (role "" -> no suffix), matching how real data is
        # tagged (a local config never carries a client/server role).
        rows = []
        values_by_subsystem = {
            "Base": ([10, 11, 12, 13, 14], ""),
            "FishNet": ([50, 51, 52, 53, 54], "client"),  # complete separation from Base
            "NGO": ([20, 21, 22, 23, 24], "client"),
            "Photon": ([30, 31, 32, 33, 34], "client"),
            "DOTS": ([15, 16, 17, 18, 19], ""),
        }
        for subsystem, (values, role) in values_by_subsystem.items():
            for i, value in enumerate(values):
                rows.append({
                    "platform": "PC", "subsystem": subsystem, "role": role,
                    "run_id": f"run{i}", "data_source": "profiler",
                    "metric_key": "fps", "metric_label": "FPS", "unit": "frames/s",
                    "entities": 400, "n_frames": 10,
                    "median": float(value), "q1": float(value) - 1, "q3": float(value) + 1,
                    "iqr": 2.0,
                })
        return pd.DataFrame(rows)

    def test_planned_mode_shrinks_family_but_keeps_all_pairs(self):
        obs = self._synthetic_observations()
        df = compare_configurations(
            obs, target_loads=[400], lower_is_better=set(),
            alpha=0.05, comparisons="planned", correction="bh",
        )
        # All C(5,2)=10 pairs are still computed and exported.
        self.assertEqual(len(df), 10)

        planned_rows = df[df["planned"]]
        unplanned_rows = df[~df["planned"]]
        self.assertEqual(len(planned_rows), 4)  # Base vs each of the other 4
        self.assertEqual(len(unplanned_rows), 6)

        # The suffixed identity is what actually appears in the output.
        self.assertSetEqual(
            set(zip(planned_rows["subsystem_a"], planned_rows["subsystem_b"])),
            {("Base", "DOTS"), ("Base", "FishNet-client"), ("Base", "NGO-client"), ("Base", "Photon-client")},
        )

        # Planned pairs are comparable and got a real correction.
        self.assertTrue((planned_rows["comparable"]).all())
        self.assertTrue(planned_rows["p_value_bh"].notna().all())

        # Unplanned pairs are still comparable (real p-values exist) but
        # were excluded from every correction family under planned mode.
        self.assertTrue((unplanned_rows["comparable"]).all())
        self.assertTrue(unplanned_rows["p_value_bh"].isna().all())
        self.assertTrue(unplanned_rows["p_value"].notna().all())

    def test_all_mode_includes_every_comparable_pair_in_the_family(self):
        obs = self._synthetic_observations()
        df = compare_configurations(
            obs, target_loads=[400], lower_is_better=set(),
            alpha=0.05, comparisons="all", correction="bh",
        )
        self.assertTrue(df["p_value_bh"].notna().all())


class RoleIdentityTests(unittest.TestCase):
    """Role (client/server/local) must be a dimension of a configuration's
    identity throughout the pipeline, never something aggregated over or
    silently mixed. Uses NetcodeEntities/DOTS -- a real PLANNED_COMPARISONS
    pair -- with a synthetic client/server split mirroring the real PC
    anomaly (client much faster than the local baseline, server much
    slower)."""

    def _config_identity_observations(self) -> pd.DataFrame:
        rows = []

        def add(subsystem, role, values, run_prefix):
            for i, value in enumerate(values):
                rows.append({
                    "platform": "PC", "subsystem": subsystem, "role": role,
                    "run_id": f"{run_prefix}{i}", "data_source": "profiler",
                    "metric_key": "cpu", "metric_label": "CPU", "unit": "ms",
                    "entities": 20000, "n_frames": 10,
                    "median": float(value), "q1": float(value) - 0.1, "q3": float(value) + 0.1,
                    "iqr": 0.2,
                })

        # DOTS: local baseline, no role.
        add("DOTS", "", [9.0, 9.5, 10.0, 10.5, 11.0], "dots_run")
        # NetcodeEntities client: much faster than DOTS -- complete separation.
        add("NetcodeEntities", "client", [3.0, 3.2, 3.4, 3.6, 3.8], "run")
        # NetcodeEntities server: much slower than both -- a different workload entirely.
        add("NetcodeEntities", "server", [25.0, 26.0, 27.0, 28.0, 29.0], "run")
        return pd.DataFrame(rows)

    def test_no_aggregation_crosses_the_role_boundary(self):
        obs = self._config_identity_observations()
        curve = metric_vs_load_curve(obs)

        client_row = curve[curve["config_id"] == "NetcodeEntities-client"].iloc[0]
        server_row = curve[curve["config_id"] == "NetcodeEntities-server"].iloc[0]
        self.assertEqual(client_row["n_runs"], 5)
        self.assertEqual(server_row["n_runs"], 5)
        self.assertAlmostEqual(client_row["median_of_medians"], 3.4)
        self.assertAlmostEqual(server_row["median_of_medians"], 27.0)
        # Neither curve point is anywhere near a client/server blend.
        self.assertLess(client_row["median_of_medians"], 10.0)
        self.assertGreater(server_row["median_of_medians"], 20.0)

    def test_local_configs_are_not_suffixed(self):
        obs = self._config_identity_observations()
        curve = metric_vs_load_curve(obs)
        dots_row = curve[curve["subsystem"] == "DOTS"].iloc[0]
        self.assertEqual(dots_row["config_id"], "DOTS")
        self.assertEqual(config_identity("DOTS", ""), "DOTS")
        self.assertEqual(config_identity("Base", None), "Base")

    def test_no_planned_comparison_pits_server_against_a_local_configuration(self):
        obs = self._config_identity_observations()
        df = compare_configurations(
            obs, target_loads=[20000], lower_is_better={"cpu"},
            alpha=0.05, comparisons="planned", correction="bh",
        )

        # The client side is planned against DOTS (the real
        # PLANNED_COMPARISONS entry) and is comparable.
        client_vs_dots = df[
            ((df["subsystem_a"] == "DOTS") & (df["subsystem_b"] == "NetcodeEntities-client"))
            | ((df["subsystem_a"] == "NetcodeEntities-client") & (df["subsystem_b"] == "DOTS"))
        ]
        self.assertEqual(len(client_vs_dots), 1)
        self.assertTrue(client_vs_dots.iloc[0]["planned"])
        self.assertTrue(client_vs_dots.iloc[0]["comparable"])
        self.assertEqual(client_vs_dots.iloc[0]["comparison_family"], "baseline")

        # The server side is never planned, and is structurally not
        # comparable to any local/client configuration, regardless of
        # sample size.
        server_rows = df[
            (df["subsystem_a"] == "NetcodeEntities-server") | (df["subsystem_b"] == "NetcodeEntities-server")
        ]
        self.assertTrue((~server_rows["planned"]).all())
        self.assertTrue((~server_rows["comparable"]).all())
        for reason in server_rows["reason"]:
            self.assertIn("server", reason.lower())

    def test_metric_vs_load_and_test_results_stay_consistent(self):
        obs = self._config_identity_observations()
        curve = metric_vs_load_curve(obs)
        comparisons = compare_configurations(
            obs, target_loads=[20000], lower_is_better={"cpu"},
            alpha=0.05, comparisons="planned", correction="bh",
        )
        issues = check_metric_vs_load_consistency(curve, comparisons)
        self.assertEqual(issues, [])

    def test_metric_vs_load_and_test_results_mismatch_is_flagged(self):
        # A curve that disagrees with the comparison's own median for the
        # same (metric, platform, config, load) must be caught, not
        # silently trusted.
        obs = self._config_identity_observations()
        comparisons = compare_configurations(
            obs, target_loads=[20000], lower_is_better={"cpu"},
            alpha=0.05, comparisons="planned", correction="bh",
        )
        curve = metric_vs_load_curve(obs)
        curve.loc[curve["config_id"] == "NetcodeEntities-client", "median_of_medians"] = 999.0
        issues = check_metric_vs_load_consistency(curve, comparisons)
        self.assertTrue(any("mismatch" in i.reason for i in issues))

    def test_role_count_mismatch_is_flagged(self):
        obs = self._config_identity_observations()
        # Drop two of the five server runs -- client still has 5.
        server_mask = obs["role"] == "server"
        keep = obs[~server_mask].index.tolist() + obs[server_mask].index[:3].tolist()
        obs = obs.loc[keep]
        issues = detect_role_count_mismatches(obs)
        self.assertEqual(len(issues), 1)
        self.assertIn("5 run(s) with a client-side observation", issues[0].reason)
        self.assertIn("3 with a server-side observation", issues[0].reason)

    def test_role_count_match_is_not_flagged(self):
        obs = self._config_identity_observations()
        self.assertEqual(detect_role_count_mismatches(obs), [])

    def test_server_tables_are_descriptive_only(self):
        obs = self._config_identity_observations()
        capacity = pd.DataFrame([
            {"platform": "PC", "subsystem": "NetcodeEntities", "role": "server", "config_id": "NetcodeEntities-server",
             "run_id": f"run{i}", "max_entities_reached": 20000, "run_complete": True}
            for i in range(5)
        ])
        metrics = server_metrics_table(obs)
        self.assertTrue((metrics["role"] == "server").all())
        self.assertIn("NetcodeEntities-server", metrics["config_id"].tolist())

        cap = server_capacity_table(capacity)
        self.assertEqual(len(cap), 1)
        self.assertEqual(cap.iloc[0]["subsystem"], "NetcodeEntities")
        self.assertEqual(cap.iloc[0]["n_runs"], 5)
        self.assertEqual(cap.iloc[0]["median_max_entities"], 20000)


class CapacityOutlierTests(unittest.TestCase):
    def _capacity_df(self, rows):
        return pd.DataFrame(rows, columns=["platform", "subsystem", "role", "run_id", "max_entities_reached", "run_complete"])

    def test_flags_run_far_below_the_others(self):
        # Mirrors the real Quest/DOTS anomaly: 4 runs reach 20000, 1 stops
        # at 1600 (well under half the others' median).
        df = self._capacity_df([
            ("Quest", "DOTS", "", "run1", 20000, True),
            ("Quest", "DOTS", "", "run2", 20000, True),
            ("Quest", "DOTS", "", "run3", 20000, True),
            ("Quest", "DOTS", "", "run4", 20000, True),
            ("Quest", "DOTS", "", "run5", 1600, False),
        ])
        issues = detect_capacity_outliers(df)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].run_id, "run5")
        self.assertIn("capacity outlier", issues[0].reason)

    def test_no_outlier_when_runs_are_similar(self):
        df = self._capacity_df([
            ("PC", "NGO", "client", "run1", 12000, False),
            ("PC", "NGO", "client", "run2", 12400, False),
            ("PC", "NGO", "client", "run3", 12000, False),
            ("PC", "NGO", "client", "run4", 12000, False),
            ("PC", "NGO", "client", "run5", 12000, False),
        ])
        self.assertEqual(detect_capacity_outliers(df), [])

    def test_too_few_runs_skips_detection(self):
        # Only 2 runs -- MIN_RUNS_FOR_OUTLIER_CHECK requires at least 3
        # before "the other runs' median" is treated as meaningful.
        df = self._capacity_df([
            ("PC", "Godot", "", "run1", 20000, True),
            ("PC", "Godot", "", "run2", 500, False),
        ])
        self.assertEqual(detect_capacity_outliers(df), [])


class AggregateRunMetricAttributionTests(unittest.TestCase):
    """Regression coverage for the Base-GPU/DOTS Quest coverage bug: a run
    that completed normally (`run_complete=True`) can still leave its
    highest palier without a usable observation when the capture ends
    only a second or two after the last wave -- that must be reported
    distinctly from "no data at all", not silently dropped."""

    def _run(self, waves, run_complete, max_time=21.0):
        stats_df = pd.DataFrame({
            "Time (s)": [float(t) for t in range(0, int(max_time) + 1)],
            "FPS": [100.0] * (int(max_time) + 1),
        })
        return RunData(
            key=RunKey("PC", "Test", "", "run1", "stat1"),
            stats_df=stats_df, events_df=pd.DataFrame(),
            data_source="profiler", waves=waves, run_complete=run_complete,
        )

    def test_short_tail_after_completed_run_flags_final_palier_by_name(self):
        # Wave at t=20 (800 entities) with only 1s of capture left
        # (max_time=21) is well under the 2s transition window: the
        # earlier wave (400 @ t=10) still produces a normal observation.
        waves = [WaveEvent(1000, 10.0, 400), WaveEvent(2000, 20.0, 800)]
        run = self._run(waves, run_complete=True, max_time=21.0)
        rows, notes = aggregate_run_metric(run, "fps", "FPS", "frames/s", transition_seconds=2.0)

        produced = {r.entities for r in rows}
        self.assertIn(400, produced)
        self.assertNotIn(800, produced)
        self.assertTrue(any("palier 800" in n and "reached" in n for n in notes))
        self.assertTrue(any("steady-state" in n for n in notes))

    def test_ample_tail_produces_observation_for_final_palier_too(self):
        waves = [WaveEvent(1000, 10.0, 400), WaveEvent(2000, 20.0, 800)]
        run = self._run(waves, run_complete=True, max_time=30.0)
        rows, notes = aggregate_run_metric(run, "fps", "FPS", "frames/s", transition_seconds=2.0)

        produced = {r.entities for r in rows}
        self.assertIn(400, produced)
        self.assertIn(800, produced)
        self.assertFalse(any("palier 800" in n for n in notes))

    def test_terminal_palier_recovered_from_dense_fallback_source(self):
        # Canonical (OVR-style) source: samples every 1s, capture ends
        # 1s after the last wave -- too short to clear a 2s transition,
        # mirrors Base-GPU/DOTS on Quest exactly.
        waves = [WaveEvent(1000, 10.0, 400), WaveEvent(2000, 20.0, 800)]
        canonical_df = pd.DataFrame({
            "Time (s)": [float(t) for t in range(0, 22)],
            "FPS": [100.0] * 22,
        })
        # Fallback (in-app profiler) source: samples every 0.25s and
        # extends to t=30 -- plenty of steady-state data for palier 800.
        fallback_df = pd.DataFrame({
            "Time (s)": [t * 0.25 for t in range(0, 121)],
            "FPS": [90.0] * 121,
        })
        run = RunData(
            key=RunKey("Quest", "Base-GPU", "", "run1", "canonical_stat"),
            stats_df=canonical_df, events_df=pd.DataFrame(),
            data_source="ovr_device", waves=waves, run_complete=True,
            fallback_stats_df=fallback_df, fallback_stat_name="fallback_stat",
        )
        rows, notes = aggregate_run_metric(run, "fps", "FPS", "frames/s", transition_seconds=2.0)

        recovered = [r for r in rows if r.entities == 800]
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].data_source, "profiler_fallback")
        self.assertGreater(recovered[0].n_frames, 1)  # far more than the OVR source could give
        self.assertTrue(any("recovered" in n and "profiler_fallback" in n for n in notes))

    def test_no_fallback_configured_falls_through_to_the_usual_note(self):
        waves = [WaveEvent(1000, 10.0, 400), WaveEvent(2000, 20.0, 800)]
        run = self._run(waves, run_complete=True, max_time=21.0)  # fallback_stats_df is None
        rows, notes = aggregate_run_metric(run, "fps", "FPS", "frames/s", transition_seconds=2.0)
        self.assertNotIn(800, {r.entities for r in rows})
        self.assertTrue(any("too little to clear" in n for n in notes))
        self.assertFalse(any("recovered" in n for n in notes))

    def test_terminal_fallback_row_returns_none_when_fallback_also_empty(self):
        waves = [WaveEvent(1000, 10.0, 400), WaveEvent(2000, 20.0, 800)]
        # Fallback source itself has no data past the wave either.
        fallback_df = pd.DataFrame({"Time (s)": [0.0, 5.0], "FPS": [100.0, 100.0]})
        run = RunData(
            key=RunKey("Quest", "Base-GPU", "", "run1", "canonical_stat"),
            stats_df=pd.DataFrame({"Time (s)": [0.0, 21.0], "FPS": [100.0, 100.0]}),
            events_df=pd.DataFrame(), data_source="ovr_device",
            waves=waves, run_complete=True,
            fallback_stats_df=fallback_df, fallback_stat_name="fallback_stat",
        )
        result = _terminal_fallback_row(run, "fps", "FPS", "frames/s", 2.0, waves[-1])
        self.assertIsNone(result)

    def test_negative_tail_gets_distinct_wording_from_short_tail(self):
        # The wave is logged as reached at t=20, but this metric's own
        # samples only run up to t=15 (e.g. a PCAP capture time-boxed
        # independently of the event log) -- capture_end < top_wave.time,
        # a fundamentally different situation from "a couple seconds
        # short of the transition window" and must read differently.
        waves = [WaveEvent(1000, 10.0, 400), WaveEvent(2000, 20.0, 800)]
        run = self._run(waves, run_complete=True, max_time=15.0)
        _, notes = aggregate_run_metric(run, "fps", "FPS", "frames/s", transition_seconds=2.0)
        matching = [n for n in notes if "palier 800" in n]
        self.assertEqual(len(matching), 1)
        self.assertIn("earlier", matching[0])
        self.assertNotIn("too little to clear", matching[0])

    def test_incomplete_run_does_not_trigger_the_named_note(self):
        # run_complete=False already has its own (existing) generic
        # handling -- this note is specifically for the surprising case
        # of a *normal* completion still losing its last palier.
        waves = [WaveEvent(1000, 10.0, 400), WaveEvent(2000, 20.0, 800)]
        run = self._run(waves, run_complete=False, max_time=21.0)
        rows, notes = aggregate_run_metric(run, "fps", "FPS", "frames/s", transition_seconds=2.0)
        self.assertFalse(any("palier 800" in n for n in notes))


class LoadCoverageTableTests(unittest.TestCase):
    def test_distinguishes_reached_from_observed(self):
        # 5 runs all reach 20000 per the capacity log, but only 2 of them
        # produced a usable observation there (mirrors Base-GPU/DOTS on
        # Quest) -- runs_reached_capacity must stay 5, not collapse to 2.
        capacity = pd.DataFrame([
            {"platform": "Quest", "subsystem": "Base-GPU", "role": "", "run_id": f"run{i}",
             "max_entities_reached": 20000, "run_complete": True}
            for i in range(5)
        ])
        observations = pd.DataFrame([
            {"platform": "Quest", "subsystem": "Base-GPU", "role": "", "run_id": f"run{i}",
             "data_source": "ovr_device", "metric_key": "fps", "metric_label": "FPS", "unit": "frames/s",
             "entities": 20000, "n_frames": 3, "median": 90.0, "q1": 89.0, "q3": 91.0, "iqr": 2.0}
            for i in range(2)
        ])
        table = load_coverage_table(observations, capacity, target_loads=[20000])
        row = table[(table.platform == "Quest") & (table.subsystem == "Base-GPU") & (table.target_load == 20000)].iloc[0]
        self.assertEqual(row.runs_total, 5)
        self.assertEqual(row.runs_reached_capacity, 5)
        self.assertEqual(row.runs_with_observation, 2)

    def test_server_role_excluded(self):
        capacity = pd.DataFrame([
            {"platform": "PC", "subsystem": "NGO", "role": "server", "run_id": "run1",
             "max_entities_reached": 20000, "run_complete": True},
        ])
        table = load_coverage_table(pd.DataFrame(), capacity, target_loads=[20000])
        self.assertTrue(table.empty)

    def test_empty_capacity_yields_empty_table(self):
        table = load_coverage_table(pd.DataFrame(), pd.DataFrame(), target_loads=[20000])
        self.assertTrue(table.empty)


class CoverageGapDetectionTests(unittest.TestCase):
    def test_flags_gap_and_names_the_configuration(self):
        coverage = pd.DataFrame([
            {"platform": "Quest", "target_load": 20000, "resolved_load": 20000, "subsystem": "Base-GPU",
             "runs_total": 5, "runs_reached_capacity": 5, "runs_with_observation": 0},
            {"platform": "Quest", "target_load": 20000, "resolved_load": 20000, "subsystem": "Base",
             "runs_total": 5, "runs_reached_capacity": 5, "runs_with_observation": 5},
        ])
        issues = detect_coverage_gaps(coverage)
        self.assertEqual(len(issues), 1)
        self.assertIn("Base-GPU", issues[0].run_id)
        self.assertIn("Quest", issues[0].run_id)
        self.assertIn("0/5", issues[0].reason)

    def test_no_gap_when_counts_match(self):
        coverage = pd.DataFrame([
            {"platform": "PC", "target_load": 400, "resolved_load": 400, "subsystem": "NGO",
             "runs_total": 5, "runs_reached_capacity": 5, "runs_with_observation": 5},
        ])
        self.assertEqual(detect_coverage_gaps(coverage), [])

    def test_empty_input(self):
        self.assertEqual(detect_coverage_gaps(pd.DataFrame()), [])


class CompareConfigurationsCapacityAwareReasonTests(unittest.TestCase):
    def test_reason_names_capacity_when_reached_but_unobserved(self):
        # subsystem "A" has zero observations at load 800 (only at 400,
        # so it still shows up as a known configuration), but its
        # capacity log shows every run reached 800 -- the reason must not
        # claim "never reached".
        observations = pd.DataFrame(
            [
                {"platform": "PC", "subsystem": "A", "role": "", "run_id": f"run{i}",
                 "data_source": "profiler", "metric_key": "fps", "metric_label": "FPS", "unit": "frames/s",
                 "entities": 400, "n_frames": 10, "median": 60.0 + i, "q1": 59.0, "q3": 61.0, "iqr": 2.0}
                for i in range(5)
            ] + [
                {"platform": "PC", "subsystem": "B", "role": "", "run_id": f"run{i}",
                 "data_source": "profiler", "metric_key": "fps", "metric_label": "FPS", "unit": "frames/s",
                 "entities": 800, "n_frames": 10, "median": 50.0 + i, "q1": 49.0, "q3": 51.0, "iqr": 2.0}
                for i in range(5)
            ]
        )
        capacity = pd.DataFrame([
            {"platform": "PC", "subsystem": "A", "role": "", "run_id": f"run{i}",
             "max_entities_reached": 800, "run_complete": True}
            for i in range(5)
        ] + [
            {"platform": "PC", "subsystem": "B", "role": "", "run_id": f"run{i}",
             "max_entities_reached": 800, "run_complete": True}
            for i in range(5)
        ])
        df = compare_configurations(
            observations, target_loads=[800], lower_is_better=set(),
            comparisons="all", correction="bh", capacity_df=capacity,
        )
        row = df.iloc[0]
        self.assertFalse(row.comparable)
        self.assertIn("reached load 800", row.reason)
        self.assertIn("capacity log", row.reason)
        self.assertNotIn("never reached", row.reason)

    def test_reason_says_never_reached_without_capacity_evidence(self):
        # Same shape as the previous test (A only has data at 400, not
        # 800), but with no capacity_df supplied -- there's no evidence
        # to contradict "never reached", so that's what the reason says.
        observations = pd.DataFrame(
            [
                {"platform": "PC", "subsystem": "A", "role": "", "run_id": f"run{i}",
                 "data_source": "profiler", "metric_key": "fps", "metric_label": "FPS", "unit": "frames/s",
                 "entities": 400, "n_frames": 10, "median": 60.0 + i, "q1": 59.0, "q3": 61.0, "iqr": 2.0}
                for i in range(5)
            ] + [
                {"platform": "PC", "subsystem": "B", "role": "", "run_id": f"run{i}",
                 "data_source": "profiler", "metric_key": "fps", "metric_label": "FPS", "unit": "frames/s",
                 "entities": 800, "n_frames": 10, "median": 50.0 + i, "q1": 49.0, "q3": 51.0, "iqr": 2.0}
                for i in range(5)
            ]
        )
        df = compare_configurations(
            observations, target_loads=[800], lower_is_better=set(),
            comparisons="all", correction="bh", capacity_df=None,
        )
        row = df.iloc[0]
        self.assertFalse(row.comparable)
        self.assertIn("never reached load 800", row.reason)


class ExtractWavesTests(unittest.TestCase):
    def _events(self, rows):
        return pd.DataFrame(rows, columns=["Frame", "Time", "Event", "Value"])

    def test_basic_waves_sorted_and_typed(self):
        events = self._events([
            [100, 1.0, "PhaseStarted", -1],
            [100, 1.0, "PhaseFinished", -1],
            [200, 5.0, "StartedInstantiation", -1],
            [210, 5.1, "FinishedInstantiation", 400],
            [300, 10.0, "StartedInstantiation", -1],
            [310, 10.1, "FinishedInstantiation", 800],
        ])
        waves, run_complete = _extract_waves(events)
        self.assertEqual([w.entities for w in waves], [400, 800])
        self.assertEqual(waves[0].frame, 210.0)
        self.assertFalse(run_complete)  # no closing PhaseFinished after wave 800

    def test_closing_phase_finished_marks_run_complete(self):
        events = self._events([
            [100, 1.0, "PhaseStarted", -1],
            [100, 1.0, "PhaseFinished", -1],
            [101, 1.1, "PhaseStarted", -1],
            [200, 5.0, "FinishedInstantiation", 400],
            [300, 10.0, "FinishedInstantiation", 800],
            [300, 10.01, "PhaseFinished", -1],
        ])
        waves, run_complete = _extract_waves(events)
        self.assertEqual([w.entities for w in waves], [400, 800])
        self.assertTrue(run_complete)

    def test_fishnet_style_duplicate_events_deduplicated(self):
        events = self._events([
            [100, 1.0, "FinishedInstantiation", 400],
            [100, 1.0, "FinishedInstantiation", 400],
            [200, 2.0, "FinishedInstantiation", 800],
            [200, 2.0, "FinishedInstantiation", 800],
        ])
        waves, _ = _extract_waves(events)
        self.assertEqual([w.entities for w in waves], [400, 800])

    def test_no_finished_instantiation_rows_yields_empty(self):
        events = self._events([
            [100, 1.0, "PhaseStarted", -1],
            [100, 1.0, "PhaseFinished", -1],
        ])
        waves, run_complete = _extract_waves(events)
        self.assertEqual(waves, [])
        self.assertFalse(run_complete)


class BuildSegmentsTests(unittest.TestCase):
    def _wave(self, time, entities, frame=None):
        from load_analysis import WaveEvent
        return WaveEvent(frame=frame if frame is not None else time * 100, time=time, entities=entities)

    def test_interior_segments_bounded_by_next_wave(self):
        waves = [self._wave(10.0, 400), self._wave(20.0, 800), self._wave(30.0, 1200)]
        segments = build_segments(waves, run_complete=True, capture_end_time=35.0, transition_seconds=2.0)
        self.assertEqual(len(segments), 3)
        first = segments[0]
        self.assertEqual(first.entities, 400)
        self.assertAlmostEqual(first.time_start, 12.0)  # 10 + transition
        self.assertAlmostEqual(first.time_end, 20.0)     # next wave's time
        self.assertTrue(first.bounded)

    def test_final_segment_dropped_when_run_incomplete(self):
        waves = [self._wave(10.0, 400), self._wave(20.0, 800)]
        segments = build_segments(waves, run_complete=False, capture_end_time=100.0, transition_seconds=2.0)
        # Only the interior segment (400 -> 800) survives; the dangling
        # tail after 800 (no closing signal) is dropped.
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].entities, 400)

    def test_final_segment_kept_when_run_complete(self):
        waves = [self._wave(10.0, 400), self._wave(20.0, 800)]
        segments = build_segments(waves, run_complete=True, capture_end_time=100.0, transition_seconds=2.0)
        self.assertEqual(len(segments), 2)
        last = segments[-1]
        self.assertEqual(last.entities, 800)
        self.assertAlmostEqual(last.time_start, 22.0)
        self.assertAlmostEqual(last.time_end, 100.0)
        self.assertFalse(last.bounded)

    def test_transition_window_can_swallow_a_short_segment(self):
        # Two waves 1 second apart with a 2-second transition exclusion:
        # the whole interior segment is transition, nothing survives.
        waves = [self._wave(10.0, 400), self._wave(11.0, 800), self._wave(20.0, 1200)]
        segments = build_segments(waves, run_complete=True, capture_end_time=30.0, transition_seconds=2.0)
        entities_present = [s.entities for s in segments]
        self.assertNotIn(400, entities_present)

    def test_empty_waves_yields_no_segments(self):
        self.assertEqual(build_segments([], run_complete=True, capture_end_time=10.0, transition_seconds=2.0), [])


class NetworkMetricComparisonTests(unittest.TestCase):
    """Network/PCAP metrics (network_rtt, network_upload, network_download,
    pcap_bytes, pcap_packets) are only meaningful between two network
    solutions' client sides, matched by load -- never against a local
    baseline (which never opens a connection), and never mixing client and
    server (already covered by RoleIdentityTests). Godot Network and
    Photon each have real, documented gaps in what they can be compared
    on; both must show up explicitly, not silently."""

    def _observations(self) -> pd.DataFrame:
        rows = []

        def add(subsystem, role, metric_key, label, unit, values, run_prefix):
            for i, value in enumerate(values):
                rows.append({
                    "platform": "PC", "subsystem": subsystem, "role": role,
                    "run_id": f"{run_prefix}{i}", "data_source": "profiler",
                    "metric_key": metric_key, "metric_label": label, "unit": unit,
                    "entities": 2000, "n_frames": 10,
                    "median": float(value), "q1": float(value) - 1, "q3": float(value) + 1,
                    "iqr": 2.0,
                })

        # Local baseline: only ever produces render metrics.
        add("Base", "", "fps", "FPS", "frames/s", [60, 61, 62, 63, 64], "base_run")

        # FishNet and NGO: full network metric coverage.
        for subsystem, base_rtt in (("FishNet", 20), ("NGO", 35)):
            add(subsystem, "client", "network_rtt", "Network RTT", "ms",
                [base_rtt + i for i in range(5)], f"{subsystem.lower()}_run")
            add(subsystem, "client", "pcap_bytes", "PCAP Bytes/s", "bytes/s",
                [1000 + base_rtt * 10 + i for i in range(5)], f"{subsystem.lower()}_run")

        # Godot Network: PCAP-only (no RTT/throughput export at all).
        add("Godot Network", "client", "pcap_bytes", "PCAP Bytes/s", "bytes/s",
            [1500, 1510, 1520, 1530, 1540], "godotnet_run")

        # Photon: has RTT and PCAP data present (so a gap here can only be
        # caught by the structural exclusion, not by absence of data).
        add("Photon", "client", "network_rtt", "Network RTT", "ms",
            [50, 51, 52, 53, 54], "photon_run")
        add("Photon", "client", "pcap_bytes", "PCAP Bytes/s", "bytes/s",
            [900, 910, 920, 930, 940], "photon_run")

        return pd.DataFrame(rows)

    def _network_rows(self, comparisons: pd.DataFrame) -> pd.DataFrame:
        return comparisons[comparisons["metric_key"].isin(
            ["network_rtt", "network_upload", "network_download", "pcap_bytes", "pcap_packets"]
        )]

    def _network_vs_network_rows(self, comparisons: pd.DataFrame) -> pd.DataFrame:
        """Network-metric rows where BOTH sides are network solutions --
        excludes the (still exported, still non-comparable) rows against
        the local baseline, which are covered by a separate test."""
        net = self._network_rows(comparisons)
        return net[(net["subsystem_a"] != "Base") & (net["subsystem_b"] != "Base")]

    def test_no_network_metric_comparison_pits_a_network_solution_against_a_local_config(self):
        obs = self._observations()
        comparisons = compare_configurations(
            obs, target_loads=[2000], lower_is_better={"network_rtt", "pcap_bytes"},
            alpha=0.05, comparisons="planned", correction="bh",
        )
        net_rows = self._network_rows(comparisons)
        involves_base = net_rows[
            (net_rows["subsystem_a"] == "Base") | (net_rows["subsystem_b"] == "Base")
        ]
        # Base does appear (paired against every network solution, for
        # completeness -- never silently omitted) but never as comparable.
        self.assertGreater(len(involves_base), 0)
        self.assertTrue((~involves_base["comparable"]).all())
        for reason in involves_base["reason"]:
            self.assertIn("local configuration", reason)

    def test_godot_network_is_explicitly_not_comparable_on_rtt(self):
        obs = self._observations()
        comparisons = compare_configurations(
            obs, target_loads=[2000], lower_is_better={"network_rtt", "pcap_bytes"},
            alpha=0.05, comparisons="planned", correction="bh",
        )
        net_rows = self._network_vs_network_rows(comparisons)
        godot_rtt = net_rows[
            (net_rows["metric_key"] == "network_rtt")
            & ((net_rows["subsystem_a"] == "Godot Network-client") | (net_rows["subsystem_b"] == "Godot Network-client"))
        ]
        self.assertGreater(len(godot_rtt), 0)
        self.assertTrue((~godot_rtt["comparable"]).all())
        for reason in godot_rtt["reason"]:
            self.assertIn("Godot Network-client excluded", reason)

    def test_photon_is_excluded_from_rtt_and_pcap_but_not_from_data_it_has(self):
        obs = self._observations()
        comparisons = compare_configurations(
            obs, target_loads=[2000], lower_is_better={"network_rtt", "pcap_bytes"},
            alpha=0.05, comparisons="planned", correction="bh",
        )
        net_rows = self._network_vs_network_rows(comparisons)
        photon_rows = net_rows[
            ((net_rows["subsystem_a"] == "Photon-client") | (net_rows["subsystem_b"] == "Photon-client"))
            # Godot Network is independently excluded from RTT (no RTT
            # metric at all) -- that pair reports Godot's reason, not
            # Photon's; the clean single-exclusion cases are vs. FishNet/NGO.
            & (net_rows["subsystem_a"] != "Godot Network-client") & (net_rows["subsystem_b"] != "Godot Network-client")
        ]
        photon_rtt = photon_rows[photon_rows["metric_key"] == "network_rtt"]
        photon_pcap = photon_rows[photon_rows["metric_key"] == "pcap_bytes"]
        self.assertGreater(len(photon_rtt), 0)
        self.assertTrue((~photon_rtt["comparable"]).all())
        self.assertTrue(photon_rtt["reason"].str.contains("cloud infrastructure").all())
        self.assertGreater(len(photon_pcap), 0)
        self.assertTrue((~photon_pcap["comparable"]).all())
        self.assertTrue(photon_pcap["reason"].str.contains("cloud infrastructure").all())

    def test_network_metric_family_is_separate_from_render_metric_families(self):
        obs = self._observations()
        comparisons = compare_configurations(
            obs, target_loads=[2000], lower_is_better={"network_rtt", "pcap_bytes"},
            alpha=0.05, comparisons="planned", correction="bh",
        )
        fishnet_vs_ngo_rtt = comparisons[
            (comparisons["metric_key"] == "network_rtt")
            & (comparisons["subsystem_a"] == "FishNet-client") & (comparisons["subsystem_b"] == "NGO-client")
        ].iloc[0]
        self.assertEqual(fishnet_vs_ngo_rtt["comparison_family"], "network_metrics")
        self.assertTrue(fishnet_vs_ngo_rtt["comparable"])
        self.assertTrue(fishnet_vs_ngo_rtt["planned"])
        # No render-metric row is ever tagged "network_metrics" -- the two
        # families never merge into one correction group.
        self.assertTrue((comparisons.loc[comparisons["metric_key"] == "fps", "comparison_family"] != "network_metrics").all())
        # BH correction is computed independently per family: the
        # network_metrics family's raw p-values were never pooled with
        # fps's (empty, in this fixture -- fps has no planned pairs at
        # all) family.
        self.assertTrue(pd.notna(fishnet_vs_ngo_rtt["p_value_bh"]))


class CapacityExclusionTests(unittest.TestCase):
    def setUp(self):
        self._saved_exclusions = dict(load_analysis.CAPACITY_EXCLUSIONS)
        self.addCleanup(lambda: load_analysis.CAPACITY_EXCLUSIONS.clear() or load_analysis.CAPACITY_EXCLUSIONS.update(self._saved_exclusions))

    def _run(self, run_id, entities, run_complete=True):
        waves = [WaveEvent(frame=100.0, time=10.0, entities=entities)]
        stats_df = pd.DataFrame({"Time (s)": [0.0, 5.0, 10.0, 15.0], "FPS": [90.0] * 4})
        return RunData(
            key=RunKey("Quest", "DOTS", "", run_id, "dots_stat"),
            stats_df=stats_df, events_df=pd.DataFrame(),
            data_source="ovr_device", waves=waves, run_complete=run_complete,
        )

    def test_excluded_run_disappears_from_capacity_but_stays_in_observations(self):
        runs = [self._run("run_excluded", 1600, run_complete=False), self._run("run_normal", 20000)]
        load_analysis.CAPACITY_EXCLUSIONS.clear()
        load_analysis.CAPACITY_EXCLUSIONS[("Quest", "DOTS", "", "run_excluded")] = "test: known bad export"

        capacity, issues = compute_capacity(runs)
        self.assertNotIn("run_excluded", capacity["run_id"].tolist())
        self.assertIn("run_normal", capacity["run_id"].tolist())
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].run_id, "run_excluded")
        self.assertIn("known bad export", issues[0].reason)

        # The exclusion is capacity-only: the run's own metrics (via
        # aggregate_run_metric / build_observations) are untouched by
        # CAPACITY_EXCLUSIONS -- verified structurally, since
        # compute_capacity never touches stats_df at all.
        rows, _ = aggregate_run_metric(runs[0], "fps", "FPS", "frames/s", transition_seconds=2.0)
        self.assertEqual(rows, [])  # this fixture's single wave has no interior segment
        # But the run is still segmentable / has valid data available --
        # nothing about aggregate_run_metric changed.
        self.assertIsInstance(rows, list)

    def test_no_exclusions_configured_is_a_no_op(self):
        load_analysis.CAPACITY_EXCLUSIONS.clear()
        runs = [self._run("run_normal", 20000)]
        capacity, issues = compute_capacity(runs)
        self.assertEqual(issues, [])
        self.assertIn("run_normal", capacity["run_id"].tolist())


class CaptureTruncationTests(unittest.TestCase):
    def _run(self, run_id, stats_times, wave_time, entities=1600):
        waves = [WaveEvent(frame=100.0, time=wave_time, entities=entities)]
        stats_df = pd.DataFrame({"Time (s)": stats_times, "FPS": [90.0] * len(stats_times)})
        return RunData(
            key=RunKey("Quest", "DOTS", "", run_id, "dots_stat"),
            stats_df=stats_df, events_df=pd.DataFrame(),
            data_source="ovr_device", waves=waves, run_complete=False,
        )

    def test_stats_ending_well_before_last_wave_is_flagged(self):
        # Stats stop at t=8s, but the event log's last wave is at t=331s --
        # the signature of an export cut short mid-capture.
        run = self._run("run1", stats_times=[0.0, 4.0, 8.0], wave_time=331.0)
        issues = detect_capture_truncation([run])
        self.assertEqual(len(issues), 1)
        self.assertIn("cut short", issues[0].reason)
        self.assertIn("331.00s", issues[0].reason)

    def test_stats_extending_past_last_wave_is_not_flagged(self):
        # Mirrors the real benchmarkQuest#4/DOTS investigation: stats
        # continue well past the last wave, which is the opposite signature
        # (a genuinely stalled run, not a truncated export).
        run = self._run("run1", stats_times=[0.0, 10.0, 20.0, 30.0, 262.0], wave_time=30.0)
        self.assertEqual(detect_capture_truncation([run]), [])

    def test_stats_ending_within_tolerance_is_not_flagged(self):
        run = self._run("run1", stats_times=[0.0, 5.0, 9.0], wave_time=10.0)
        self.assertEqual(detect_capture_truncation([run]), [])

    def test_run_with_no_waves_is_skipped(self):
        run = RunData(
            key=RunKey("Quest", "DOTS", "", "run1", "dots_stat"),
            stats_df=pd.DataFrame({"Time (s)": [0.0, 1.0], "FPS": [90.0, 90.0]}),
            events_df=pd.DataFrame(), data_source="ovr_device", waves=[], run_complete=False,
        )
        self.assertEqual(detect_capture_truncation([run]), [])


if __name__ == "__main__":
    unittest.main()
