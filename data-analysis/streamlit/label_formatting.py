from data_loader import (
    base_tech_label,
    classify_subsystem,
    extract_timestamp,
    is_networked_subsystem,
    normalize_timestamp,
    _is_quest_routed_capture,
)

"""
label_formatting
-----------------
Pure, Streamlit-free label parsing/formatting helpers used by `app.py`'s UI:
turning a raw "[PC]  photon_client_profiler_stats-....csv" style label into
a friendly display string, and classifying labels by platform/role/tech for
the quick filters and run-averaging groups.

Extracted out of `app.py` specifically so this logic can be unit tested
without importing `app.py` itself -- `app.py` runs the whole Streamlit
script (folder scanning, pcap tooling, `st.stop()` calls) as a side effect
of being imported, which this module has no need to depend on: everything
here is a pure function of a label string plus `data_loader`'s shared
classification helpers.
"""


def _split_subsystem_label(label: str):
    """Splits a subsystem label string to determine if it belongs to PC or Quest."""
    if label.startswith("[PC] "):
        return "PC", label[5:]
    if label.startswith("[Quest] "):
        return "Quest", label[8:]
    return "Unknown", label


def _is_networked_tech_label(label: str) -> bool:
    """Keep only series from an actually-networked tech for network/PCAP plots.

    Non-networked baseline scenes (Base, Base-GPU, DOTS, solo Godot) can
    still carry an RTT/Upload/Download column in their exported CSV --
    some captures had a stray network-stats provider wired into the
    ProfilerStatsToCSVExporter component on the Unity side even though
    the scene never opens a connection, so the numbers exist but are
    meaningless. `_has_network_columns` only checks column presence, so
    without this filter those baseline runs sneak into "Network - RTT"
    etc. plots as if they were real network telemetry. Delegates to
    `classify_subsystem` + `is_networked_subsystem` (shared with the
    offline analysis pipeline) instead of a filename substring check:
    a "godot client"/"godot server" (space-joined) substring check used
    to sit here, but real filenames are underscore-joined
    (`godot_client_capture`, `server_godot_...`), so it never actually
    matched anything and silently excluded every Godot PCAP series.
    """
    return is_networked_subsystem(classify_subsystem(label))


def short_label(label: str, all_labels: list[str] | None = None) -> str:
    """Return a friendly, human-readable label like 'PC · DOTS Server'.

    The label disambiguates client/server roles for both platforms and
    appends a short timestamp when several files would otherwise map to
    the same display name (e.g. multiple NetcodeEntities runs). When a
    `all_labels` collection is provided, the function also appends a
    short type tag — `(stats)`, `(events)`, or `(trace)` — so files that
    share the same capture timestamp but are different artefacts
    (events CSV, profiler stats CSV, Android trace CSV) remain
    distinguishable in the legend and dropdown.
    """
    if label.startswith("[PC]"):
        platform = "PC"
    elif label.startswith("[Quest]"):
        platform = "Quest"
    else:
        platform = "Quest"

    name = label.lower()

    # Derived from data_loader's `_CLASSIFICATION_RULES` -- the same
    # ordered keyword table `classify_subsystem()` uses -- rather than a
    # second, independently-maintained elif chain. Registering a new
    # benchmark type in `_CLASSIFICATION_RULES` is now enough for it to
    # show up correctly here too; see `base_tech_label()`'s docstring for
    # why it returns the base ("Godot", never "Godot Network") form.
    tech = base_tech_label(label)
    if platform == "Quest" and _is_quest_routed_capture(label):
        # PCAP capture of Quest-client traffic taken on the PC side while
        # it routes the headset's connection. Its filename carries a
        # literal "server" token (traffic direction, not an actual
        # server role) that the plain substring checks below would
        # otherwise misread as a server capture -- the Quest headset
        # never hosts a server, for any tech.
        tech += " Client"
    elif "client" in name:
        tech += " Client"
    elif "server" in name:
        tech += " Server"
    elif platform == "Quest" and tech == "Godot" and _type_tag_for(label) == "trace":
        # The Quest Godot Android trace (`com.IMT_Atlantique.godot_network_benchmark#GodotApp-*.csv`)
        # is emitted by the running app itself, i.e. the client. It carries
        # no `_client_` / `_server_` token in its filename, so without this
        # branch it would render as a bare `Quest · Godot` line that
        # duplicates the client view. The PCAP capture output and the
        # events/stats CSVs all already have explicit `client`/`server`
        # tokens, so they are unaffected.
        tech += " Client"
    elif platform == "Quest" and is_networked_subsystem(tech) and _type_tag_for(label) == "trace":
        # Same situation as the Godot branch above, generalized: FishNet /
        # NGO / Photon / NetcodeEntities have no non-networked baseline
        # mode, so their bare Quest trace (`com.IMT_Atlantique.<tech>#...`,
        # no `_client_`/`_server_` token) is unambiguously the client run
        # -- unlike Godot there's no unrelated baseline group it could
        # collide with. Without this branch it rendered as a separate,
        # confusingly-named `Quest · FishNet` line next to
        # `Quest · FishNet Client`, as if they were two different runs.
        tech += " Client"

    # Append a compact timestamp so files from different captures remain
    # distinguishable in the legend / dropdown. The label may carry either
    # the profiler-stats format "YYYY.MM.DD-HH.MM" or the event format
    # "YYYYMMDD_HHMMSS" (which contains seconds we want to drop).
    short_ts, _ = extract_timestamp(label)
    if short_ts:
        normalized = normalize_timestamp(short_ts)  # YYYYMMDD_HHMM
        if normalized and len(normalized) >= 13:
            time_part = normalized[9:13]
            tech = f"{tech} · {normalized[6:8]}.{time_part}"

    base = f"{platform} · {tech}"

    # Detect collisions: when more than one underlying label maps to the
    # same `base` string, append a type tag so the dropdown / legend lets
    # the user tell events, profiler stats, and Android trace apart.
    if all_labels:
        siblings = [lbl for lbl in all_labels if short_label(lbl) == base]
        if len(siblings) > 1 and label in siblings:
            type_tag = _type_tag_for(label)
            if type_tag:
                base = f"{base} ({type_tag})"

    return base


def _type_tag_for(label: str) -> str:
    """Classify a CSV label as stats, events or trace for disambiguation."""
    lower = label.lower()
    if "events" in lower:
        return "events"
    if "profiler_stats" in lower:
        return "stats"
    if (
        "unityplayer" in lower
        or "imt_atlantique" in lower
        or lower.endswith("#unityplayergameactivity")
        or "#godotapp" in lower
    ):
        # "#GodotApp-<timestamp>.csv" is the Android on-device trace
        # naming convention regardless of package id -- the earliest
        # Quest capture used the default "com.example" package before
        # it was renamed to "com.IMT_Atlantique", so package-name
        # matching alone misses it.
        return "trace"
    if ".pcap.csv" in lower or "_capture_" in lower:
        return "pcap"
    return ""


def _is_pc_label(label: str) -> bool:
    return label.startswith("[PC]")


def _is_quest_label(label: str) -> bool:
    return label.startswith("[Quest]")


def _is_client_label(label: str) -> bool:
    """Return True only when the label carries an explicit client marker.

    Matches both the profiler-stats naming convention (`..._client_...`)
    and the event-style naming convention (`..._client_events_...`).
    Quest Android traces (`com.IMT_Atlantique.*`) carry no role token
    and are matched separately via `_is_quest_label` — they are NOT
    treated as client by this predicate so that the "Quest clients" /
    "Client only" quick filters stay focused on network-stack captures.

    PC baseline files (dots / gpu / events / generic `profiler_stats`
    without a client/server token) are role-agnostic and intentionally
    excluded: they are still selectable via "PC only" / "Non-network"
    presets or the manual multiselect.
    """
    lowered = label.lower()
    return (
        "_client_" in lowered
        or "_client_events_" in lowered
        or "_client_profiler_" in lowered
    )


def _is_server_label(label: str) -> bool:
    """Return True only when the label belongs to a real server-side role.

    In this dataset, the Quest device never acts as a server: any
    `*_server_*` file coming from the Quest is actually a PCAP capture of
    *server-bound* traffic observed on the Quest, not a server hosted on
    the device. To avoid surfacing misleading "server" lines, this
    predicate is intentionally scoped to PC files only.
    """
    if not _is_pc_label(label):
        return False
    lowered = label.lower()
    return (
        "_server_" in lowered
        or "_server_events_" in lowered
        or "_server_profiler_" in lowered
    )


def _run_group_key(label: str) -> tuple[str, str, str]:
    """Group key identifying "the same system" across repeated run
    folders, ignoring per-run timestamps: (platform, subsystem, role).
    Used to average multiple runs of the same platform/subsystem/role
    into one line -- client and server stay distinct so a trial folder's
    client/server pair is never averaged together as if it were two
    repeats of the same measurement.

    Role uses a plain "client"/"server" substring match (same approach
    as short_label()'s tech-role suffix) rather than the stricter
    _is_client_label()/_is_server_label() predicates: those require a
    `_client_`/`_server_` token wrapped in underscores, which the Godot
    Network files (`client_godot_...csv` / `server_godot_...csv`, role
    token as a bare prefix) don't have -- using the strict predicates
    here silently merged a single run's Godot client+server pair into
    one averaged "run".
    """
    platform = "PC" if _is_pc_label(label) else "Quest"
    subsystem = classify_subsystem(label)
    lowered = label.lower()
    if platform == "Quest" and _is_quest_routed_capture(label):
        # PCAP capture of Quest-client traffic taken on the PC side
        # while it routes the headset's connection. Its filename carries
        # a literal "server" token (denoting traffic *direction*, not an
        # actual server role) that would otherwise misclassify this as
        # server data -- the Quest headset never hosts a server, for any
        # tech, so this must always be Client.
        role = "Client"
    elif "client" in lowered:
        role = "Client"
    elif "server" in lowered:
        role = "Server"
    elif platform == "Quest" and subsystem == "Godot" and _type_tag_for(label) == "trace":
        # Every Quest tech is exported twice per run: once as a
        # profiler_stats CSV and once as the on-device Android trace
        # (`com.IMT_Atlantique...#GodotApp-*.csv` / `#UnityPlayerGameActivity-*.csv`).
        # Godot is the only tech with a *legitimate* role="" group (the
        # single-player baseline) that the trace could collide with -- and
        # for the networked-run trace specifically, colliding would
        # silently mix networked-client data into the baseline average.
        # Giving the trace its own non-colliding role avoids that. (Every
        # other networked tech's trace is handled by the branch below,
        # which folds it straight into "Client" instead -- see there for
        # why that's safe for them but not for Godot.)
        role = "Trace (network run)" if "network" in lowered else "Trace"
    elif platform == "Quest" and is_networked_subsystem(subsystem) and _type_tag_for(label) == "trace":
        # FishNet / NGO / Photon / NetcodeEntities have no non-networked
        # baseline mode, so their bare Quest trace (no `_client_`/
        # `_server_` token) is unambiguously the client run -- there's no
        # unrelated role="" group it could wrongly get averaged into, so
        # unlike Godot it can just join the real "Client" group instead of
        # needing its own separate "Trace" bucket. This collapses the
        # previous `Quest · FishNet` / `Quest · FishNet Client` split
        # (same physical run, two exports) into a single line.
        role = "Client"
    else:
        role = ""
    return platform, subsystem, role


def _group_key_to_display(key: tuple[str, str, str]) -> str:
    """Render a `_run_group_key()` tuple as the display string used both
    by the averaged legend line (see create_standard_plot) and by the
    aggregated-mode Line Filter dropdown, so the two stay in sync."""
    platform, subsystem, role = key
    role_suffix = f" {role}" if role else ""
    return f"{platform} · {subsystem}{role_suffix}"


def _is_godot_label(label: str) -> bool:
    """Return True when the file name (after the platform tag) is a Godot run.

    Godot files used to be tagged with a separate `[Godot] ` prefix, but
    they are now treated like every other benchmark: they keep the
    platform tag from the capture folder (`[PC]` / `[Quest]`) and expose
    "Godot" as the tech. We detect them by their `godot` token in the
    filename instead of by an exclusive prefix.
    """
    return "godot" in label.lower()


def _is_godot_file_name(file_name: str) -> bool:
    return "godot" in file_name.lower()


STANDARD_METRIC_KEYS = ("fps", "memory", "cpu", "gpu")


def _keep_for_quest_standard_metric(label: str) -> bool:
    """For FPS/Memory/CPU/GPU on Quest, keep only the data source that
    actually ends up plotted -- see the call site in build_metric_figures
    for why. Shared with the Line Filter candidate list so the dropdown
    never offers a label (e.g. "Quest · Godot Trace") that these metrics
    silently drop later, which used to leave dead entries in the filter."""
    if not label.startswith("[Quest] "):
        return True
    if _is_godot_label(label):
        # Godot is exempted from the "trace files only" rule below so it
        # uses the same profiler_stats source as every other platform/tech.
        # But its Android trace re-export of that same run
        # (com.IMT_Atlantique...#GodotApp-*.csv) must still be dropped here
        # rather than left to _collapse_datasets: that dedupe only merges
        # siblings whose short_label() timestamps round to the same minute,
        # which is a coincidence that fails for roughly one run in five
        # (profiler_stats and the trace routinely start a couple seconds
        # apart, straddling a minute boundary) -- when it fails, the trace
        # survives as an unmerged, unaveraged singleton line instead of
        # quietly disappearing like its siblings. Dropping every Godot
        # trace file here, unconditionally, makes the outcome deterministic.
        return _type_tag_for(label) != "trace"
    return "com.IMT_Atlantique" in label
