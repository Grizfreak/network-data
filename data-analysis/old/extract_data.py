import argparse
import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Callable


DEFAULT_BASE_FOLDER = os.path.expandvars(r"%AppData%\..\LocalLow\IMT_Atlantique")
DEFAULT_QUEST_CAPTURE_PATH = "/sdcard/Android/data/com.oculus.ovrmonitormetricsservice/files/CapturedMetrics"
DEFAULT_ANDROID_DATA_PATH = "/sdcard/Android/data"
DEFAULT_PACKAGE_PREFIX = "com.IMT_Atlantique"

_TIMESTAMP_PATTERNS = (
    r"_\d{8}_\d{6}",
    r"-\d{8}_\d{6}",
    r"-\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}",
)


def _series_key(file_name: str) -> str:
    """Return a stable key for timestamped CSV series names."""
    stem, _ = os.path.splitext(file_name)
    timestamp_pattern = "|".join(_TIMESTAMP_PATTERNS)
    match = re.match(rf"^(.*?)(?:{timestamp_pattern}).*$", stem)
    if match:
        stem = match.group(1)
    return stem.rstrip("_-. ")


def _latest_file_per_series(
    files: list[str],
    path_getter: Callable[[str], str],
    sort_key: Callable[[str], float],
) -> dict[str, str]:
    latest_files: dict[str, str] = {}
    for file_name in files:
        key = _series_key(file_name)
        current_path = path_getter(file_name)
        if key not in latest_files or sort_key(current_path) > sort_key(latest_files[key]):
            latest_files[key] = current_path
    return latest_files


def get_latest_csv_files(base_folder: str = DEFAULT_BASE_FOLDER) -> dict[str, str]:
    """Return latest local CSV files grouped by normalized series key."""
    latest_files: dict[str, str] = {}
    for root, _dirs, files in os.walk(base_folder):
        csv_files = [file for file in files if file.endswith(".csv")]
        folder_latest = _latest_file_per_series(
            csv_files,
            lambda file_name: os.path.join(root, file_name),
            os.path.getmtime,
        )
        for key, file_path in folder_latest.items():
            if key not in latest_files or os.path.getmtime(file_path) > os.path.getmtime(latest_files[key]):
                latest_files[key] = file_path
    return latest_files


def _adb_ls_sorted(remote_path: str) -> list[str]:
    """Return remote entries from adb shell ls -t (newest first), or empty list on failure."""
    result = subprocess.run(
        ["adb", "shell", "ls", "-t", remote_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def get_latest_quest_files(
    remote_path: str = DEFAULT_QUEST_CAPTURE_PATH,
    file_prefix: str = DEFAULT_PACKAGE_PREFIX,
) -> dict[str, str]:
    """Return latest Quest capture CSV files grouped by normalized series key."""
    files = _adb_ls_sorted(remote_path)
    files = [file for file in files if file.startswith(file_prefix) and file.endswith(".csv")]
    if not files:
        return {}

    # ls -t already returns newest first.
    file_order = {file_name: index for index, file_name in enumerate(files)}
    return _latest_file_per_series(
        files,
        lambda file_name: f"{remote_path}/{file_name}",
        lambda remote_file: -file_order[os.path.basename(remote_file)],
    )


def get_latest_android_app_data_files(
    package_prefix: str = DEFAULT_PACKAGE_PREFIX,
    android_data_path: str = DEFAULT_ANDROID_DATA_PATH,
) -> dict[str, str]:
    """Return latest CSV files from /sdcard/Android/data/<package>/files for matching packages."""
    result = subprocess.run(
        ["adb", "shell", "ls", "-d", f"{android_data_path}/{package_prefix}.*"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}

    app_dirs = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    latest_files: dict[str, str] = {}

    for app_dir in app_dirs:
        files_dir = f"{app_dir}/files"
        files = [name for name in _adb_ls_sorted(files_dir) if name.endswith(".csv")]
        if not files:
            continue

        file_order = {file_name: index for index, file_name in enumerate(files)}
        app_latest = _latest_file_per_series(
            files,
            lambda file_name: f"{files_dir}/{file_name}",
            lambda remote_file: -file_order[os.path.basename(remote_file)],
        )

        # Keep one latest file per normalized series globally.
        for key, remote_file in app_latest.items():
            if key not in latest_files:
                latest_files[key] = remote_file

    return latest_files


def collect_latest_files(
    base_folder: str = DEFAULT_BASE_FOLDER,
    include_quest_capture: bool = True,
    include_android_app_data: bool = True,
    package_prefix: str = DEFAULT_PACKAGE_PREFIX,
) -> tuple[dict[str, str], dict[str, str]]:
    """Collect latest local files and latest remote files for reuse by other scripts."""
    local_files = get_latest_csv_files(base_folder)
    remote_files: dict[str, str] = {}

    if include_quest_capture:
        remote_files.update(get_latest_quest_files(file_prefix=package_prefix))

    if include_android_app_data:
        remote_files.update(get_latest_android_app_data_files(package_prefix=package_prefix))

    return local_files, remote_files


def save_files_to_data_folder(
    local_files: dict[str, str],
    remote_files: dict[str, str],
    output_root: str = "data",
) -> str:
    """Copy local files and pull remote files to data/<timestamp> and return the folder path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(output_root, timestamp)
    os.makedirs(output_folder, exist_ok=True)

    for _key, file_path in local_files.items():
        shutil.copy(file_path, output_folder)

    for _key, remote_file in remote_files.items():
        local_path = os.path.join(output_folder, os.path.basename(remote_file))
        subprocess.run(["adb", "pull", remote_file, local_path], check=False)

    return output_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect latest benchmark CSV files")
    parser.add_argument("--base-folder", default=DEFAULT_BASE_FOLDER)
    parser.add_argument("--prefix", default=DEFAULT_PACKAGE_PREFIX)
    parser.add_argument("--no-quest-capture", action="store_true")
    parser.add_argument("--no-app-data", action="store_true")
    parser.add_argument("--no-copy", action="store_true")
    args = parser.parse_args()

    local_files, remote_files = collect_latest_files(
        base_folder=args.base_folder,
        include_quest_capture=not args.no_quest_capture,
        include_android_app_data=not args.no_app_data,
        package_prefix=args.prefix,
    )

    print(f"Searching for CSV files in: {args.base_folder}")
    print("Latest local CSV files:")
    for key, file_path in sorted(local_files.items()):
        print(f"{key}: {os.path.basename(file_path)}")

    print("Latest remote CSV files:")
    for key, remote_file in sorted(remote_files.items()):
        print(f"{key}: {remote_file}")

    if not args.no_copy:
        output_folder = save_files_to_data_folder(local_files, remote_files)
        print(f"Saved files to: {output_folder}")


if __name__ == "__main__":
    main()
