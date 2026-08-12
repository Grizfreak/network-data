from pathlib import Path
import re
from datetime import datetime

import pandas as pd

"""
data_loader
-----------
Helpers to discover, read and normalize CSV files exported by
the benchmark runs. Responsibilities include:
- Detecting stat vs event files
- Normalizing common column names (Frame, Time, Event, Value)
- Pairing stats and events by filename semantics and timestamps

Lecture note: this module isolates file-format variability so the
rest of the pipeline works with predictable column names.
"""


def detect_columns(df: pd.DataFrame):
    frame_col = None
    for c in ("Frame", "Time Stamp", "Time"):
        if c in df.columns:
            frame_col = c
            break
    fps_col = None
    for c in ("FPS", "average_frame_rate"):
        if c in df.columns:
            fps_col = c
            break
    return frame_col, fps_col


def _has_pcap_columns(df: pd.DataFrame) -> bool:
    return any(
        col in df.columns
        for col in (
            "PacketsPerSec",
            "BytesPerSec",
            "Packets",
            "Bytes",
            "BitsPerSec",
        )
    )


def _canonical_csv_name(file_name: str) -> str:
    """Return a stable capture name for CSV outputs derived from pcap files."""
    path = Path(file_name)
    stem = path.stem
    lower_stem = stem.lower()
    if lower_stem.endswith(".pcap"):
        stem = stem[:-5]
    elif lower_stem.endswith(".pcapng"):
        stem = stem[:-7]
    return f"{stem}{path.suffix.lower()}"


def extract_timestamp(file_name: str):
    """Extract timestamp from filename. Returns (timestamp_str, datetime_obj) or (None, None)."""
    patterns = [
        (r"\d{8}_\d{6}", "%Y%m%d_%H%M%S"),
        (r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}", "%Y.%m.%d-%H.%M"),
        (r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}", "%Y-%m-%dT%H-%M-%S"),
    ]
    for pattern, fmt in patterns:
        matches = list(re.finditer(pattern, file_name))
        if not matches:
            continue
        # Prefer the last timestamp in the file name (usually the current run).
        for match in reversed(matches):
            ts_str = match.group(0)
            try:
                return ts_str, datetime.strptime(ts_str, fmt)
            except ValueError:
                continue
    return None, None


def normalize_timestamp(ts: str):
    """Normalize timestamps to YYYYMMDD_HHMM format for display/comparison.

    Supports both the profiler-stats format `YYYY.MM.DD-HH.MM` (e.g.
    `2026.06.24-16.21`) and the event format `YYYYMMDD_HHMMSS`
    (e.g. `20260624_162005`). The event form may carry an underscore
    between the date and the time; we drop the trailing seconds so the
    resulting string always ends in exactly HHMM.
    """
    if not ts:
        return None
    if "." in ts and "-" in ts:
        parts = ts.replace(".", "").replace("-", "")
        return parts[:8] + "_" + parts[8:12]
    if "T" in ts and ts.count("-") >= 3:
        date_part, time_part = ts.split("T", 1)
        date_digits = date_part.replace("-", "")
        time_digits = time_part.replace("-", "")
        if len(date_digits) == 8 and len(time_digits) >= 4:
            return f"{date_digits}_{time_digits[:4]}"
    if "_" in ts:
        date_part, _, time_part = ts.partition("_")
        if len(date_part) == 8 and len(time_part) >= 4:
            return f"{date_part}_{time_part[:4]}"
    return ts[:8] + "_" + ts[-4:]


def _extract_source_label(file_name: str):
    lower = file_name.lower()
    if lower.startswith("[pc]"):
        return "pc"
    if lower.startswith("[quest]"):
        return "quest"
    if lower.startswith("[godot]"):
        return "godot"
    return None


def is_quest_server_artefact(name: str) -> bool:
    """Return True for a stats/events CSV that should be dropped when
    loading a Quest benchmark folder.

    The Quest headset never hosts a server, for any tech -- the server
    always runs on the PC. When a trial is recorded, the PC-hosted
    server's own profiler_stats/events CSVs routinely get dropped into
    the same benchmark folder as the Quest client's data for
    convenience, so without this filter they get tagged "[Quest]" and
    corrupt any analysis that groups by (platform, subsystem): the
    PC server's telemetry has nothing to do with what the headset
    measured.

    PCAP captures are exempt: they're the PC observing traffic while it
    routes the headset's connection, so they genuinely describe the
    Quest client's network activity (see `_is_quest_routed_capture`),
    even though their filename also carries a "server" token.

    Shared by the Streamlit app (`_load_source_files` in app.py) and the
    offline analysis pipeline (`ccl/analyze_data.py`) so both draw from
    the same definition of "this file doesn't belong on Quest".
    """
    lowered = name.lower()
    if lowered.endswith(".pcap.csv") or ".pcap.csv" in lowered:
        return False
    return "server" in lowered


def _preferred_event_patterns(stat_file_name: str):
    """Return ordered event filename patterns preferred for this stats file."""
    lower = stat_file_name.lower()

    if lower.startswith("[pc] "):
        lower = lower[5:]
    elif lower.startswith("[quest] "):
        lower = lower[8:]

    if "ngo_server" in lower:
        return ["ngo_server_events_", "ngo_client_events_"]
    if "ngo_client" in lower or "benchmarkngo" in lower:
        return ["ngo_client_events_", "ngo_server_events_"]
    if "photon_server" in lower:
        return ["photon_server_events_", "photon_client_events_"]
    if "photon_client" in lower or "photonfusion" in lower:
        return ["photon_client_events_", "photon_server_events_"]
    if "netcodeentities_server" in lower:
        return ["netcodeentities_server_dots_events_", "netcodeentities_client_dots_events_"]
    if "netcodeentities_client" in lower:
        return ["netcodeentities_client_dots_events_", "netcodeentities_server_dots_events_"]
    if "dots" in lower:
        return ["dots_events_"]
    if "gpu" in lower:
        return ["gpu_events_"]
    if "godot" in lower:
        return ["events_godot_", "events_"]
    if "benchmarkbase" in lower:
        return ["events_"]
    if "profiler_stats-" in lower:
        return ["events_"]

    return []


def _is_quest_routed_capture(name: str) -> bool:
    """Return True for a PCAP capture of Quest-client traffic taken on the
    PC side while it routes the headset's connection.

    Every capture dropped into a Quest benchmark folder follows
    `<tech>_server_capture[_quest_capture]_<ts>.pcap[.csv]` -- the
    `_quest_capture_` infix was only added to the naming convention
    partway through data collection, so the earliest captures
    (`benchmarkQuest#1`, e.g. `ngo_server_capture_20260604_154052.pcap`)
    lack it. Matching is therefore done on the "[Quest] " tag plus a bare
    "capture" + ".pcap" check instead of that infix, since no Quest
    folder has ever contained a client-side capture file -- every one of
    them is this same routed-traffic case regardless of exact filename.

    The `server` token in these names describes the traffic *direction*
    (captured en route to the server), not an actual server role -- the
    Quest headset never hosts a server, so this data genuinely describes
    the Quest client's own network activity. Without this exception, the
    literal "server" token makes `_pairing_score` reject pairing against
    the (correct) client events file via the client/server mismatch
    guard below.
    """
    lower = name.lower()
    if not lower.startswith("[quest]"):
        return False
    return ".pcap" in lower and "capture" in lower


def _pairing_score(stat_name: str, event_name: str, stat_dt: datetime | None, event_dt: datetime | None):
    """Compute pairing score. Higher is better."""
    score = 0.0
    event_lower = event_name.lower()

    # Strongly prefer same source prefix (PC/Quest) when present.
    stat_source = _extract_source_label(stat_name)
    event_source = _extract_source_label(event_name)
    if stat_source and event_source:
        if stat_source != event_source:
            return float("-inf")
        score += 200.0

    # Prefer exact semantic token matches from filenames (component and client/server).
    # If stat and event explicitly disagree on client/server, treat as incompatible.
    def _tokens(name: str):
        s = name.lower()
        s = re.sub(r"^\[pc\]\s*", "", s)
        s = re.sub(r"^\[quest\]\s*", "", s)
        return set(re.findall(r"[a-z0-9]+", s))

    stat_tokens = _tokens(stat_name)
    event_tokens = _tokens(event_name)

    if _is_quest_routed_capture(stat_name):
        stat_tokens.discard("server")
        stat_tokens.add("client")

    # If one is 'client' and the other is 'server', reject pairing
    if ("client" in stat_tokens and "server" in event_tokens) or ("server" in stat_tokens and "client" in event_tokens):
        return float("-inf")

    # Strongly prefer when both share the same major token (ngo, photon, dots, gpu, fishnet, profiler)
    common = stat_tokens.intersection(event_tokens)
    major_tokens = {"ngo", "photon", "dots", "gpu", "fishnet", "profiler", "benchmarkbase", "netcodeentities", "godot"}
    if common.intersection(major_tokens):
        score += 300.0

    # Boost if both explicitly mention client/server consistently
    if ("client" in stat_tokens and "client" in event_tokens) or ("server" in stat_tokens and "server" in event_tokens):
        score += 300.0

    # Prefer semantic filename matches first (server/client/framework).
    preferred_patterns = _preferred_event_patterns(stat_name)
    for idx, pattern in enumerate(preferred_patterns):
        if pattern in event_lower:
            score += 150.0 - (idx * 25.0)
            break

    # Time proximity is secondary to semantic match.
    if stat_dt is not None and event_dt is not None:
        delta = abs((stat_dt - event_dt).total_seconds())
        if delta <= 600:
            score += (100.0 - min(delta, 100.0))
        else:
            score -= min((delta - 600.0) / 10.0, 200.0)

    return score


def classify_subsystem(name: str) -> str:
    """Return a short subsystem tag (Photon/NGO/DOTS/Godot Network/Godot/Base) for a stat filename."""
    lower = name.lower()
    # Callers often pass a "[PC] "/"[Quest] " tagged label rather than a
    # bare filename; strip the tag so prefix checks below (baseline
    # detection) see the actual file name.
    lower = re.sub(r"^\[pc\]\s*|^\[quest\]\s*", "", lower)
    if "photon" in lower:
        return "Photon"
    if "fishnet" in lower:
        return "FishNet"
    if "ngo" in lower:
        return "NGO"
    if "netcodeentities" in lower:
        return "NetcodeEntities"
    if "godot" in lower:
        if any(token in lower for token in ("client", "server")):
            return "Godot Network"
        return "Godot"
    if "dots" in lower:
        return "DOTS"
    if "gpu" in lower:
        return "Base-GPU"
    if "base" in lower:
        return "Base"
    # The PC baseline stat/event pair has no "base" token at all --
    # it's just `profiler_stats-*.csv` / `events_*.csv` (see the
    # `_siblings` mapping in assemble.py). Every other stats/events
    # family is prefixed (dots_/gpu_/ngo_.../photon_.../netcodeEntities_...)
    # and already returned above, so this is unambiguous.
    if lower.startswith("profiler_stats-") or lower.startswith("events_"):
        return "Base"
    return "Other"


NETWORKED_SUBSYSTEMS = {"Photon", "FishNet", "NGO", "NetcodeEntities", "Godot Network"}


def is_networked_subsystem(subsystem: str) -> bool:
    """Return True when `subsystem` (a `classify_subsystem()` result) is an
    actually-networked tech.

    Non-networked baseline scenes (Base, Base-GPU, DOTS, solo Godot) can
    still carry an RTT/Upload/Download column in their exported CSV --
    some captures had a stray network-stats provider wired into the
    ProfilerStatsToCSVExporter component on the Unity side even though
    the scene never opens a connection, so the numbers exist but are
    meaningless. Column-presence checks alone (`_has_network_columns`)
    can't tell the difference; this goes by tech identity instead. Shared
    by the Streamlit app and the offline analysis pipeline so neither
    reports fabricated "network" stats for a baseline run.
    """
    return subsystem in NETWORKED_SUBSYSTEMS


def _is_quest_folder(folder_path: Path) -> bool:
    csv_files = list(folder_path.glob("*.csv"))
    return any("com.IMT_Atlantique" in csv_file.name for csv_file in csv_files)


def list_pc_and_quest_folders(data_root: Path):
    """List every non-empty PC and Quest data folder, most recently
    modified first.

    Returns: (pc_folders, quest_folders), each a list[Path] (possibly empty).
    """
    if not data_root.exists():
        return [], []

    all_folders = sorted(
        (folder for folder in data_root.iterdir() if folder.is_dir() and any(folder.glob("*.csv"))),
        key=lambda folder: folder.stat().st_mtime,
        reverse=True,
    )

    pc_folders, quest_folders = [], []
    for folder in all_folders:
        (quest_folders if _is_quest_folder(folder) else pc_folders).append(folder)

    return pc_folders, quest_folders


def get_pc_and_quest_folders(data_root: Path):
    """Find latest PC and Quest data folders.

    Returns: (pc_folder, quest_folder) where each can be None if not found.
    """
    pc_folders, quest_folders = list_pc_and_quest_folders(data_root)
    pc_folder = pc_folders[0] if pc_folders else None
    quest_folder = quest_folders[0] if quest_folders else None
    return pc_folder, quest_folder


def load_csv_files_from_folder(folder_path: Path):
    """Load all CSV files from a folder and classify them into stats and events.

    Returns: (stats_files, events_files, read_errors)
    """
    stats_files = []
    events_files = []
    read_errors = []
    stats_by_name = {}
    events_by_name = {}

    csv_files = list(folder_path.glob("*.csv"))

    def _candidate_priority(file_name: str) -> tuple[int, str]:
        lower_name = file_name.lower()
        # Prefer the canonical CSV name over the doubled-extension capture output.
        return (0 if lower_name.endswith((".pcap.csv", ".pcapng.csv")) else 1, lower_name)

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            file_name = csv_file.name
            lower_name = file_name.lower()
            canonical_name = _canonical_csv_name(file_name)
            # Normalize common column names to a canonical form so downstream
            # code can rely on `Event`, `Value`, `Frame`, and `Time` column names.
            col_map = {}
            cols_lower = {c.lower(): c for c in df.columns}
            if "frame" in cols_lower:
                col_map[cols_lower["frame"]] = "Frame"
            if "time stamp" in cols_lower or "timestamp" in cols_lower:
                col_map[cols_lower.get("time stamp", cols_lower.get("timestamp"))] = "Time Stamp"
            if "time" in cols_lower and "time stamp" not in cols_lower:
                col_map[cols_lower["time"]] = "Time"
            if "event" in cols_lower:
                col_map[cols_lower["event"]] = "Event"
            if "value" in cols_lower:
                col_map[cols_lower["value"]] = "Value"
            if col_map:
                df = df.rename(columns=col_map)

            # Detect event files by filename or by presence of an `Event` column
            if "event" in lower_name or "event" in (c.lower() for c in df.columns):
                candidate = (file_name, df)
                current = events_by_name.get(canonical_name)
                if current is None or _candidate_priority(file_name) > _candidate_priority(current[0]):
                    events_by_name[canonical_name] = candidate
            else:
                _, fpscol = detect_columns(df)
                if fpscol is not None or _has_pcap_columns(df):
                    candidate = (file_name, df)
                    current = stats_by_name.get(canonical_name)
                    if current is None or _candidate_priority(file_name) > _candidate_priority(current[0]):
                        stats_by_name[canonical_name] = candidate
        except Exception as exc:
            read_errors.append((csv_file.name, str(exc)))

    stats_files.extend(stats_by_name.values())
    events_files.extend(events_by_name.values())

    return stats_files, events_files, read_errors


def auto_pair_files(stats_list, events_list, min_score: float = 50.0):
    """Match stat files to event files using semantic name matching and timestamp proximity."""
    pairings = {}
    debug_info = []

    event_meta = []
    for ename, _ in events_list:
        _, e_dt = extract_timestamp(ename)
        event_meta.append((ename, e_dt))

    for sname, _ in stats_list:
        _, stat_dt = extract_timestamp(sname)
        match = None
        best_score = float("-inf")
        best_delta = None

        for ename, event_dt in event_meta:
            score = _pairing_score(sname, ename, stat_dt, event_dt)
            if score > best_score:
                best_score = score
                match = ename
                if stat_dt is not None and event_dt is not None:
                    best_delta = abs((stat_dt - event_dt).total_seconds())
                else:
                    best_delta = None

        # Keep low-confidence pairings as unmatched.
        if best_score < min_score:
            match = None

        if match is not None:
            if best_delta is not None:
                debug_info.append(f"✓ Paired {sname[:30]}... with {match[:30]}... (Δ{best_delta:.0f}s)")
            else:
                debug_info.append(f"✓ Paired {sname[:30]}... with {match[:30]}... (name match)")

        if match is None and len(events_list) == 1:
            match = events_list[0][0]
            debug_info.append(f"⚠ {sname[:30]}... → fallback to only event file")

        if match is None:
            debug_info.append(f"✗ No match for {sname[:30]}...")

        pairings[sname] = match

    return pairings, debug_info
