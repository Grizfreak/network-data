import os
import re
from datetime import datetime

_siblings = {
    "profiler_stats-" :"events_",
    "ngo_server_profiler_stats-" : "ngo_server_events_",
    "ngo_client_profiler_stats-" : "ngo_client_events_",
    "com.IMT_Atlantique.BenchmarkBase" : "events_",
    "com.IMT_Atlantique.BenchmarkNGO" : "ngo_client_events_"
}

_TIMESTAMP_PATTERNS = (
    (re.compile(r"\d{8}_\d{6}"), "%Y%m%d_%H%M%S"),
    (re.compile(r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}"), "%Y.%m.%d-%H.%M"),
)

class StatAndEvent:
    def __init__(self, stat_file, event_file):
        self.stat_file = stat_file
        self.event_file = event_file

    def __repr__(self):
        return f"StatAndEvent(stat_file={self.stat_file}, event_file={self.event_file})"

def get_latest_folder(path):
    folders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
    if not folders:
        return None
    latest_folder = max(folders, key=lambda f: os.path.getmtime(os.path.join(path, f)))
    return os.path.join(path, latest_folder)

def _parse_timestamp(file_name):
    for pattern, datetime_format in _TIMESTAMP_PATTERNS:
        matches = list(pattern.finditer(file_name))
        if matches:
            return datetime.strptime(matches[-1].group(0), datetime_format)
    return None

def _pick_latest_by_timestamp(file_names):
    return max(
        file_names,
        key=lambda name: (
            _parse_timestamp(name) or datetime.min,
            os.path.getmtime(name) if os.path.exists(name) else 0,
        ),
    )

def _pick_closest_event(stat_name, event_names):
    stat_timestamp = _parse_timestamp(stat_name)
    if stat_timestamp is None:
        return _pick_latest_by_timestamp(event_names)

    def sort_key(event_name):
        event_timestamp = _parse_timestamp(event_name)
        if event_timestamp is None:
            return (float("inf"), datetime.min)
        return (abs((event_timestamp - stat_timestamp).total_seconds()), event_timestamp)

    return min(event_names, key=sort_key)

def get_files_from_folder(folder_path) -> list[StatAndEvent]:
    # order files in a list with siblings together
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    ordered_files = []
    for sibling_prefix, sibling_suffix in _siblings.items():
        item = StatAndEvent(None, None)

        stat_candidates = [name for name in files if name.startswith(sibling_prefix)]
        event_candidates = [name for name in files if name.startswith(sibling_suffix)]

        stat_name = _pick_latest_by_timestamp(stat_candidates) if stat_candidates else None
        event_name = _pick_closest_event(stat_name, event_candidates) if stat_name and event_candidates else None

        if stat_name:
            item.stat_file = os.path.join(folder_path, stat_name)
        if event_name:
            item.event_file = os.path.join(folder_path, event_name)
        if item.stat_file and item.event_file:
            ordered_files.append(item)
    return ordered_files


def main():
    # get most recent folder in ./data
    latest_folder = get_latest_folder("./data")
    files = get_files_from_folder(latest_folder)
    for file in files:
        print(file)

if __name__ == "__main__":
    main()