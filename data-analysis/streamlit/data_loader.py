from pathlib import Path
import re
from datetime import datetime

import pandas as pd


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


def extract_timestamp(file_name: str):
    """Extract timestamp from filename. Returns (timestamp_str, datetime_obj) or (None, None)."""
    patterns = [
        (r"\d{8}_\d{6}", "%Y%m%d_%H%M%S"),
        (r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}", "%Y.%m.%d-%H.%M"),
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
    """Normalize timestamps to YYYYMMDD_HHMM format for display/comparison."""
    if not ts:
        return None
    if "." in ts and "-" in ts:
        parts = ts.replace(".", "").replace("-", "")
        return parts[:8] + "_" + parts[8:12]
    return ts[:8] + "_" + ts[-4:]


def _extract_source_label(file_name: str):
    lower = file_name.lower()
    if lower.startswith("[pc]"):
        return "pc"
    if lower.startswith("[quest]"):
        return "quest"
    return None


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
    if "dots" in lower:
        return ["dots_events_"]
    if "gpu" in lower:
        return ["gpu_events_"]
    if "benchmarkbase" in lower:
        return ["events_"]
    if "profiler_stats-" in lower:
        return ["events_"]

    return []


def _pairing_score(stat_name: str, event_name: str, stat_dt: datetime, event_dt: datetime):
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

    # If one is 'client' and the other is 'server', reject pairing
    if ("client" in stat_tokens and "server" in event_tokens) or ("server" in stat_tokens and "client" in event_tokens):
        return float("-inf")

    # Strongly prefer when both share the same major token (ngo, photon, dots, gpu, fishnet, profiler)
    common = stat_tokens.intersection(event_tokens)
    major_tokens = {"ngo", "photon", "dots", "gpu", "fishnet", "profiler", "benchmarkbase"}
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


def _is_quest_folder(folder_path: Path) -> bool:
    csv_files = list(folder_path.glob("*.csv"))
    return any("com.IMT_Atlantique" in csv_file.name for csv_file in csv_files)


def get_pc_and_quest_folders(data_root: Path):
    """Find latest PC and Quest data folders.

    Returns: (pc_folder, quest_folder) where each can be None if not found.
    """
    if not data_root.exists():
        return None, None

    all_folders = sorted(
        [folder for folder in data_root.iterdir() if folder.is_dir()],
        key=lambda folder: folder.stat().st_mtime,
        reverse=True,
    )

    pc_folder = None
    quest_folder = None

    for folder in all_folders:
        is_quest = _is_quest_folder(folder)
        if is_quest and quest_folder is None:
            quest_folder = folder
        elif not is_quest and pc_folder is None:
            pc_folder = folder

        if pc_folder and quest_folder:
            break

    return pc_folder, quest_folder


def load_csv_files_from_folder(folder_path: Path):
    """Load all CSV files from a folder and classify them into stats and events.

    Returns: (stats_files, events_files, read_errors)
    """
    stats_files = []
    events_files = []
    read_errors = []

    csv_files = list(folder_path.glob("*.csv"))

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            file_name = csv_file.name
            lower_name = file_name.lower()
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
                events_files.append((file_name, df))
            else:
                _, fpscol = detect_columns(df)
                if fpscol is not None:
                    stats_files.append((file_name, df))
        except Exception as exc:
            read_errors.append((csv_file.name, str(exc)))

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
