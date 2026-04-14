import os

_siblings = {
    "profiler_stats-" :"events_"
}

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

def get_files_from_folder(folder_path) -> list[StatAndEvent]:
    # order files in a list with siblings together
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(folder_path, f)), reverse=True)
    ordered_files = []
    for sibling_prefix, sibling_suffix in _siblings.items():
        item = StatAndEvent(None, None)
        for file in files:
            if file.startswith(sibling_prefix):
                item.stat_file = os.path.join(folder_path, file)
            elif file.startswith(sibling_suffix):
                item.event_file = os.path.join(folder_path, file)
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