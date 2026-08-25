import pandas as pd
import plotly.express as px

from data_loader import extract_timestamp, normalize_timestamp, _is_quest_routed_capture
from label_formatting import (
    STANDARD_METRIC_KEYS,
    _group_key_to_display,
    _is_client_label,
    _is_networked_tech_label,
    _keep_for_quest_standard_metric,
    _run_group_key,
    _type_tag_for,
    short_label,
)
from metrics_engine import average_series_across_runs, build_datasets

"""
plotting
--------
Pure (Streamlit-free) dataset-dedup, line-filter-expansion, and Plotly
figure-construction logic for the Benchmark Metrics Viewer, tied together
by `build_metric_figures()` -- one figure per selected metric.

Extracted out of `app.py` for the same reason `label_formatting.py` was:
`build_metric_figures()` used to be a closure over app.py's module-level
widget state (`stats_files`, `selected_metric_keys`, `active_line_filters`,
...), set by Streamlit widgets earlier in the same top-to-bottom script
run. That made it impossible to call, or test, without importing all of
`app.py` -- which runs the whole Streamlit script (folder scanning, pcap
tooling, `st.stop()` calls) as an import side effect, and ties the
function's behavior to the widgets' *execution order* rather than to
explicit inputs. `build_metric_figures()` here takes every one of those as
an explicit argument instead. The rest of this module (dedup helpers,
`create_standard_plot`, filter expansion) never depended on Streamlit state
in the first place -- they already took explicit parameters -- and moved
along with it purely to keep the figure-construction logic in one place.
"""

_TYPE_PRIORITY = {"stats": 0, "pcap": 1, "events": 2, "trace": 3, "": 4}


def _pick_canonical(siblings: list[str]) -> str:
    """Return the canonical label for a group of siblings sharing a display name."""
    return sorted(
        siblings,
        key=lambda lbl: (
            _TYPE_PRIORITY.get(_type_tag_for(lbl), 99),
            _type_tag_for(lbl),
            lbl,
        ),
    )[0]


def _dedupe_candidates(candidates: set[str]) -> list[str]:
    groups: dict[str, list[str]] = {}
    for label in candidates:
        base = short_label(label)
        groups.setdefault(base, []).append(label)
    deduped = []
    for base, siblings in groups.items():
        if len(siblings) == 1:
            deduped.append(siblings[0])
            continue
        deduped.append(_pick_canonical(siblings))
    return sorted(deduped)


def _collapse_datasets(datasets: list[tuple[str, pd.DataFrame]]) -> list[tuple[str, pd.DataFrame]]:
    """Reduce a list of (label, df) pairs to one entry per short_label().

    Keeps the same canonical label as `_dedupe_candidates` so the legend
    matches the line-filter dropdown exactly.
    """
    groups: dict[str, list[tuple[str, pd.DataFrame]]] = {}
    for entry in datasets:
        base = short_label(entry[0])
        groups.setdefault(base, []).append(entry)
    collapsed: list[tuple[str, pd.DataFrame]] = []
    for base, siblings in groups.items():
        if len(siblings) == 1:
            collapsed.append(siblings[0])
            continue
        canonical = _pick_canonical([lbl for lbl, _ in siblings])
        for lbl, df in siblings:
            if lbl == canonical:
                collapsed.append((lbl, df))
                break
    return collapsed


def _dedupe_candidates_by_group(candidates: set[str]) -> list[str]:
    """One representative raw label per (platform, subsystem, role) group.

    Used for the Line Filter dropdown in aggregated mode: once runs get
    averaged into a single line per group, listing every individual run
    (each with its own timestamp) just floods the dropdown with entries
    that all collapse into the same plotted line anyway. Picking one
    canonical representative per group keeps the options list matching
    what's actually going to be drawn -- one entry per averaged line.
    """
    groups: dict[tuple[str, str, str], list[str]] = {}
    for label in candidates:
        groups.setdefault(_run_group_key(label), []).append(label)
    representatives = [
        _pick_canonical(siblings) if len(siblings) > 1 else siblings[0]
        for siblings in groups.values()
    ]
    return sorted(representatives, key=lambda lbl: _group_key_to_display(_run_group_key(lbl)))


def _drop_truncated_gameobject_runs(entries, x_col_group, min_coverage=0.4, min_points=3):
    """Drop per-run per-GameObject series whose captured range is much
    shorter than its sibling runs' in the same average group.

    A Quest on-device trace that stops recording after a few seconds
    instead of covering the full multi-minute benchmark only yields a
    handful of early, still-healthy FPS samples pinned to GameObjects
    values that don't line up with the other runs' milestone grid (their
    FinishedInstantiation events keep firing off-camera while the trace
    isn't recording anymore). Averaging that alongside complete runs
    turns a smooth trend into a jagged sawtooth: at some GameObjects
    values only the complete runs contribute (showing the real decline),
    while immediately next to them a lone truncated-run sample sits at
    ~72 FPS, and the line connecting the two looks like a crash-and-recover
    cycle that never happened. Filtering on point count (rather than max
    GameObjects reached) is deliberate: a truncated run can still report a
    numerically high "GameObjects" value if its events counter kept
    incrementing quickly, but it will always have far fewer recorded
    per-GameObject segments than a run that stayed alive for the whole
    benchmark.
    """
    if x_col_group != "GameObjects" or len(entries) <= 2:
        return entries
    counts = sorted(len(df) for _, df in entries)
    mid = len(counts) // 2
    median_count = counts[mid] if len(counts) % 2 else (counts[mid - 1] + counts[mid]) / 2
    if median_count < min_points:
        return entries
    kept = [(label, df) for label, df in entries if len(df) >= median_count * min_coverage]
    return kept if kept else entries


def create_standard_plot(datasets, selected_labels, metric_label, metric_key, per_gameobject, xcol, log_scale=False, average_runs=False):
    """Create a standard line plot for non-network metrics."""
    combined = []
    plot_ycol = None
    run_groups = {}  # (platform, subsystem, role) -> [(raw_label, temp_df), ...]

    # No movement-phase-specific trimming; keep series as-is

    for label, df in datasets:
        if label not in selected_labels:
            continue
        temp = df.copy()
        if temp.empty:
            continue
        if plot_ycol is None and "_ycol" in temp.columns:
            plot_ycol = temp["_ycol"].iloc[0]
        if average_runs:
            run_groups.setdefault(_run_group_key(label), []).append((label, temp))
        else:
            temp["label"] = short_label(label, [lbl for lbl, _ in datasets])
            combined.append(temp)

    if average_runs:
        for (platform, subsystem, role), entries in run_groups.items():
            # A group with only one contributing run has nothing to
            # average -- plot it exactly like the non-averaged path.
            if len(entries) > 1:
                sample_df = entries[0][1]
                ycol_group = sample_df["_ycol"].iloc[0] if "_ycol" in sample_df.columns else plot_ycol
                x_col_group = "GameObjects" if "GameObjects" in sample_df.columns else xcol
                if ycol_group is not None and x_col_group in sample_df.columns:
                    kept_entries = _drop_truncated_gameobject_runs(entries, x_col_group)
                    avg_df = average_series_across_runs(
                        [d for _, d in kept_entries], x_col=x_col_group, y_col=ycol_group
                    )
                    if not avg_df.empty:
                        role_suffix = f" {role}" if role else ""
                        avg_df = avg_df.rename(columns={"mean": ycol_group})
                        avg_df["label"] = f"{platform} · {subsystem}{role_suffix} (avg of {len(kept_entries)} runs)"
                        avg_df["_ycol"] = ycol_group
                        combined.append(avg_df[[x_col_group, ycol_group, "label", "_ycol"]])
                        continue
                # Couldn't determine a common x/y column for this group;
                # fall back to plotting each run separately below.
            for run_label, run_df in entries:
                run_df["label"] = short_label(run_label, [lbl for lbl, _ in datasets])
                combined.append(run_df)

    if not combined:
        return None

    if not combined:
        return None

    all_df = pd.concat(combined, ignore_index=True)

    # Normalize y-column names: if Quest and PC have different column names for the same metric,
    # rename Quest's column to match PC's (e.g., "CPU Utilization (%)" -> "CPU (ms)")
    # This allows both platforms to render on the same plot
    if "_ycol" in all_df.columns:
        # Get all unique y-column names used in this dataset
        unique_ycols = set(all_df["_ycol"].dropna().unique())
        # If there are multiple column names for the same metric, pick the first one and rename all to it
        if len(unique_ycols) > 1:
            canonical_ycol = list(unique_ycols)[0]
            for alt_ycol in unique_ycols:
                if alt_ycol in all_df.columns and alt_ycol != canonical_ycol:
                    # Rename the alternative column to the canonical name
                    all_df[canonical_ycol] = all_df[canonical_ycol].fillna(all_df[alt_ycol])
                    all_df = all_df.drop(columns=[alt_ycol], errors="ignore")
            ycol = canonical_ycol
        else:
            ycol = plot_ycol if plot_ycol is not None else "FPS"
    else:
        ycol = plot_ycol if plot_ycol is not None else "FPS"

    all_df = all_df.drop(columns=["_ycol"], errors="ignore")

    plot_xcol = xcol if xcol in all_df.columns else ("GameObjects" if "GameObjects" in all_df.columns else ("Frame" if "Frame" in all_df.columns else xcol))

    # If log scale requested, remove non-positive values for the plot y-column
    all_df[ycol] = pd.to_numeric(all_df[ycol], errors="coerce")
    all_df = all_df.dropna(subset=[ycol])
    if log_scale:
        all_df = all_df[all_df[ycol] > 0]

    fig = px.line(all_df, x=plot_xcol, y=ycol, color="label", markers=True)

    if metric_key == "fps":
        fig.add_hline(
            y=72,
            line_dash="dash",
            line_color="gray",
            annotation_text="72 FPS",
            annotation_position="top left",
        )
    elif metric_key in ("cpu", "gpu"):
        # 1000 ms / 72 FPS ≈ 13.89 ms — the frame-time budget required to
        # sustain a 72 FPS refresh rate (Quest 3 / Pico 4 default).
        fig.add_hline(
            y=14,
            line_dash="dash",
            line_color="gray",
            annotation_text="14 ms (~72 FPS budget)",
            annotation_position="top left",
        )

    phase_suffix = ""
    # Use the actual y-column name for the y-axis label (in case Quest/PC differ)
    y_axis_label = metric_label if metric_key.startswith("godot_") else (ycol if ycol not in ("FPS", metric_label) else metric_label)
    figure_title = f"{metric_label}{phase_suffix} per GameObject pool" if per_gameobject and plot_xcol == "GameObjects" else f"{metric_label}{phase_suffix} vs {plot_xcol}"
    fig.update_layout(title=figure_title, xaxis_title=plot_xcol, yaxis_title=y_axis_label, height=600)
    if log_scale:
        fig.update_yaxes(type="log")
    return fig


def _capture_timestamp_key(label: str) -> str | None:
    """Return the capture timestamp used to group files from the same run.

    This is the same normalized YYYYMMDD_HHMM value produced by
    `normalize_timestamp`. Note that for the same Unity capture run, the
    Android trace file (`com.IMT_Atlantique.*#UnityPlayerGameActivity-*.csv`)
    and the corresponding stats file (`*_profiler_stats-*.csv`) often
    start within a minute or two of each other, so a strict equality
    match on this key is too narrow. Callers should use
    `_capture_date_key` when they want to allow that tolerance.
    """
    ts, _ = extract_timestamp(label)
    if not ts:
        return None
    return normalize_timestamp(ts)


def _capture_date_key(label: str) -> str | None:
    """Return the capture date (YYYYMMDD) for grouping files from the
    same Unity session. Android trace files and stats files from the same
    run usually share this date but can be minutes apart, so this key
    is broader than `_capture_timestamp_key`.
    """
    key = _capture_timestamp_key(label)
    if not key or len(key) < 8:
        return None
    return key[:8]


def _label_has_server_role(label: str) -> bool:
    """Return True when the label explicitly identifies a server-side role.

    Used to prevent the same-capture-date expansion from leaking server
    captures into a client-only filter: a Photon *client* selection on
    `20260605` must not pull in the Photon *server* capture that happens
    to share the same Unity capture date.
    """
    if _is_quest_routed_capture(label):
        # Its "_server_capture_" token describes traffic direction, not
        # an actual server role -- see _run_group_key/_is_quest_routed_capture.
        return False
    lowered = label.lower()
    return (
        "_server_" in lowered
        or "_server_events_" in lowered
        or "_server_profiler_" in lowered
        or "_server_capture_" in lowered
    )


def _expand_filter_labels(
    selected: set[str],
    candidates: list[str],
    datasets_labels: list[str],
) -> set[str]:
    """Expand each selected dropdown label to every related file in `datasets`.

    Two expansion rules are tried, in order:
    1. Same `short_label()` — covers cases where sibling files were
       kept alongside the canonical entry (e.g. PCAP stats vs trace
       with identical display names).
    2. Same capture date (YYYYMMDD) — covers cases where the trace
       file's display name differs from the stats file (no
       Client/Server suffix, different sub-minute timestamp) but the
       files belong to the same Unity capture session.

    Rule 2 is gated by role safety: a candidate that explicitly carries
    a server-side role token (`_server_`, `_server_events_`,
    `_server_profiler_`, `_server_capture_`) is never pulled in by a
    selection whose `short_label()` is client-side, even when the
    capture dates match. This avoids the "Client only" plot leaking in
    Fishnet / NetcodeEntities / NGO / Photon server traces from the
    same Unity session, which share the same capture timestamp family
    (`_capture_timestamp_key` collapses seconds to minutes).
    """
    expanded: set[str] = set()
    for label in selected:
        expanded.add(label)
        base = short_label(label)
        selection_is_client = _is_client_label(label)
        selection_type = _type_tag_for(label)
        cap_ts = _capture_timestamp_key(label)
        cap_date = cap_ts[:8] if cap_ts else None
        for candidate in candidates:
            if candidate == label or candidate in expanded:
                continue
            if short_label(candidate) == base:
                expanded.add(candidate)
                continue
            if cap_date:
                cand_date = _capture_date_key(candidate)
                if cand_date != cap_date:
                    continue
                candidate_type = _type_tag_for(candidate)
                # Only use same-date expansion to bridge the intended stats/trace
                # sibling case. Without this guard, choosing a PC Base line filter
                # also pulls in unrelated DOTS/GPU stat files that happen to share
                # the same capture date.
                if {selection_type, candidate_type} != {"stats", "trace"}:
                    continue
                # Same-date expansion: refuse to bring in any capture
                # that is explicitly labelled as a server-side role when
                # the user is filtering on a client selection. This is
                # the role-gating guarantee promised by the docstring.
                if selection_is_client and _label_has_server_role(candidate):
                    continue
                expanded.add(candidate)
    return expanded


def build_metric_figures(
    *,
    stats_files,
    events_files,
    user_pairings,
    selected_metric_keys,
    metric_options,
    per_gameobject,
    average_runs,
    include_unpaired,
    active_line_filters,
    line_filter_candidates,
    per_gameobject_override=None,
    x_axis_mode="frame",
    log_scale=False,
):
    """Build one Plotly figure per selected metric.

    Every input that used to be read implicitly from app.py's module scope
    (set by Streamlit widgets earlier in the script) is now an explicit
    argument -- see this module's docstring for why. `app.py` passes its
    widget-derived values in by name at the call site; nothing here reads
    Streamlit state directly, so this function can be called (and tested)
    with plain Python values.
    """
    metric_figures = {}
    skipped_by_filter = []
    for metric_key in selected_metric_keys:
        metric_label = [k for k, v in metric_options.items() if v == metric_key][0]
        use_per_gameobject = per_gameobject if per_gameobject_override is None else per_gameobject_override
        use_average_runs = average_runs and use_per_gameobject
        datasets, _ = build_datasets(
            stats_files=stats_files,
            events_files=events_files,
            user_pairings=user_pairings,
            selected_metric_key=metric_key,
            selected_metric_label=metric_label,
            per_gameobject=use_per_gameobject,
            x_axis_mode=x_axis_mode,
            include_unpaired=include_unpaired,
        )

        if metric_key.startswith(("network_", "pcap_")) and datasets:
            datasets = [
                (label, df)
                for label, df in datasets
                if _is_networked_tech_label(label)
            ]

        # Filter out non-com.IMT_Atlantique Quest files for standard metrics (FPS, Memory, CPU, GPU).
        # We want to use ONLY com.IMT_Atlantique files for these specific metrics on Quest, as requested.
        # However, we also need to include godot-quest data in the plots like godot-pc ones.
        if metric_key in STANDARD_METRIC_KEYS and datasets:
            datasets = [
                (label, df) for label, df in datasets
                if _keep_for_quest_standard_metric(label)
            ]

        if datasets:
            # Collapse datasets by short_label() so the legend stays
            # consistent with the line-filter dropdown (one entry per
            # capture run, no duplicate "(stats)" / "(trace)" siblings).
            datasets = _collapse_datasets(datasets)
            labels = [t[0] for t in datasets]
            if active_line_filters:
                if use_average_runs:
                    # Aggregated mode: the dropdown holds one
                    # representative label per (platform, subsystem,
                    # role) group (see _dedupe_candidates_by_group), so
                    # expand each selection to every run sharing that
                    # exact group key -- the same grouping
                    # create_standard_plot uses to build the averaged
                    # line, so the filter and the plot always agree.
                    wanted_keys = {_run_group_key(sel) for sel in active_line_filters}
                    labels = [
                        label for label in labels
                        if _run_group_key(label) in wanted_keys
                    ]
                else:
                    # Per-run mode: expand each selected dropdown label
                    # back to every sibling file that shares the same
                    # short_label() (or the same capture timestamp when
                    # display names diverge between stats and trace
                    # files).
                    expanded = _expand_filter_labels(
                        active_line_filters,
                        list(line_filter_candidates),
                        labels,
                    )
                    labels = [label for label in labels if label in expanded]
            if not labels:
                skipped_by_filter.append(metric_label)
                continue
            fig = create_standard_plot(
                datasets,
                labels,
                metric_label,
                metric_key,
                use_per_gameobject,
                "GameObjects" if use_per_gameobject else ("Time" if x_axis_mode == "time" else "Frame"),
                log_scale=log_scale,
                average_runs=use_average_runs,
            )
            if fig:
                metric_figures[metric_label] = fig

    return metric_figures, skipped_by_filter
