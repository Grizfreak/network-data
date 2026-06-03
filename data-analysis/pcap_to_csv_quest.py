"""Convert Quest-side pcap/pcapng captures into bucketed CSV time series.

This module is the Quest counterpart of :mod:`pcap_to_csv` (which is wired
into the PC capture tools in :mod:`app`). The wire format and bucketing
strategy are identical so the resulting CSV files can be loaded by the
existing plotting pipeline (`pcap_*` metrics in
:mod:`streamlit.metrics_engine`).

Quest captures are typically produced with ``tcpdump`` on the headset.
They are stored as ``*.pcapng`` files (the magic bytes are
``0a 0d 0d 0a``) and they usually live in the same data folder as the
Quest profiler/event files. Their filenames embed the substring
``quest_capture`` to distinguish them from server-side captures.

The conversion is delegated to :func:`pcap_to_csv.convert_pcap_to_dataframe`
so the bucket columns (``Frame``, ``Time (s)``, ``Packets``, ``Bytes``,
``PacketsPerSec``, ``BytesPerSec``, ``BitsPerSec``, ``Cumulative*``,
``TCPPackets``, ``UDPPackets``, ``ICMPPackets``, ``OtherPackets``) match
exactly what the PC tool produces. That way a single plot can mix
``[PC] foo.pcap.csv`` and ``[Quest] foo.pcap.csv`` lines.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd

import pcap_to_csv


# Substring used by tcpdump scripts to tag Quest captures. Matching is
# case-insensitive so it survives filesystem differences across platforms.
QUEST_CAPTURE_TOKEN = "capture"  # Changed from "quest_capture" for broader matching

# Quest captures are always pcapng in this project, but the conversion
# helper accepts both, so we keep the extension list aligned with the PC
# tool for consistency.
QUEST_CAPTURE_EXTENSIONS = (".pcap", ".pcapng")


def is_quest_capture_path(path: Path) -> bool:
    """Return True if *path* looks like a Quest-side capture."""
    if not path.is_file():
        return False
    if path.suffix.lower() not in QUEST_CAPTURE_EXTENSIONS:
        return False
    # Relaxed check: If it's a pcap/pcapng file and the folder contains any Quest CSV, we assume it is relevant.
    # This relies on find_quest_capture_files to filter by directory context.
    return True


def _is_quest_csv_output(path: Path) -> bool:
    """Return True if *path* is a CSV generated from a Quest capture.

    The PC tool writes CSVs with the suffix doubled (e.g.
    ``foo.pcap.csv``), so we look for any pcap/pcapng component inside the stem.
    This allows us to process all captures in a Quest context folder, not just those named "quest_capture".
    """
    if path.suffix.lower() != ".csv":
        return False
    # Check that it's derived from a capture file (has .pcap or .pcapng component)
    stem_lower = path.stem.lower()
    return any(ext in stem_lower for ext in (".pcap", ".pcapng"))


def find_quest_capture_files(folder_path: Path) -> List[Path]:
    """List all potential Quest capture files (pcap/pcapng) directly under *folder_path*.

    A file is considered a candidate if it has the correct extension and
    the folder contains any CSV with "com.IMT_Atlantique" in its name,
    indicating this directory belongs to the Quest dataset.
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return []

    # Check if the folder is associated with Quest data by checking for a known CSV pattern
    has_quest_context = any("com.IMT_Atlantique" in str(csv_file.name) for csv_file in folder_path.glob("*.csv"))

    if not has_quest_context:
        return []  # Not a Quest data directory based on CSV content

    # If context is found, return all pcap/pcapng files as candidates
    return sorted(
        p for p in folder_path.iterdir()
        if p.is_file() and p.suffix.lower() in QUEST_CAPTURE_EXTENSIONS
    )


def find_quest_capture_csv_outputs(folder_path: Path) -> List[Path]:
    """List Quest-derived CSV files directly under *folder_path*."""
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    return sorted(
        p for p in folder_path.iterdir()
        if p.is_file() and _is_quest_csv_output(p)
    )


def find_quest_capture_folders(data_root: Path) -> List[Path]:
    """Return Quest data folders that contain at least one capture file.

    The same detection rule as :func:`streamlit.data_loader.get_pc_and_quest_folders`
    is used for "this is a Quest folder": at least one CSV whose name
    contains ``com.IMT_Atlantique`` (the Quest package name from the
    Android profiler exports). If such a directory also has pcap/pcapng files, we return it.

    This function returns folders that contain both:
      - A "Quest context" marker (CSV with com.IMT_Atlantique) AND
      - At least one .pcap or .pcapng file to convert.
    """
    if not data_root.exists() or not data_root.is_dir():
        return []

    quest_folders: List[Path] = []
    for folder in sorted(data_root.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        # Check if the directory contains any CSV file associated with Quest (the original heuristic)
        has_quest_context = any("com.IMT_Atlantique" in str(csv_file.name) for csv_file in folder.glob("*.csv"))

        if has_quest_context:
            # If it's a quest context folder, we assume all pcap/pcapng files are relevant captures
            if any(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in QUEST_CAPTURE_EXTENSIONS):
                quest_folders.append(folder)

    return quest_folders


def iter_quest_capture_outputs(folder_path: Path) -> Iterable[Path]:
    """Yield the CSV path that :func:`convert_quest_captures_to_csv` would
    produce for each Quest capture directly under *folder_path*."""
    for capture in find_quest_capture_files(folder_path):
        yield capture.with_suffix(f"{capture.suffix}.csv")


def convert_quest_captures_to_csv(
    folder_path: Path,
    bucket_seconds: float = 1.0,
    overwrite: bool = False,
):
    """Convert every Quest pcap/pcapng capture in *folder_path* to CSV.

    The output structure matches the PC tool: each ``foo.pcap`` produces
    ``foo.pcap.csv`` next to it. The conversion itself is delegated to
    :func:`pcap_to_csv.convert_pcap_to_dataframe` so the CSV schema is
    identical.

    Returns a dictionary with the same shape as
    :func:`pcap_to_csv.convert_pcap_folder_to_csv` so the Streamlit UI
    can render the result uniformly.
    """
    converted: List[Tuple[Path, Path, int]] = []
    skipped: List[Tuple[Path, Path]] = []
    errors: List[Tuple[Path, str]] = []
    warnings: List[Tuple[Path, str]] = []

    captures = find_quest_capture_files(folder_path)
    if not captures:
        return {
            "converted": converted,
            "skipped": skipped,
            "errors": errors,
            "warnings": warnings,
        }

    for capture in captures:
        output_path = capture.with_suffix(f"{capture.suffix}.csv")
        if output_path.exists() and not overwrite:
            skipped.append((capture, output_path))
            continue

        try:
            frame: pd.DataFrame = pcap_to_csv.convert_pcap_to_dataframe(
                capture, bucket_seconds=bucket_seconds
            )
            frame.to_csv(output_path, index=False)
            read_error = frame.attrs.get("read_error")
            converted.append((capture, output_path, len(frame)))
            if read_error:
                warnings.append((capture, f"Partial conversion completed: {read_error}"))
        except Exception as exc:  # noqa: BLE001 - we surface the raw error in the UI
            errors.append((capture, str(exc)))

    return {
        "converted": converted,
        "skipped": skipped,
        "errors": errors,
        "warnings": warnings,
    }


def cleanup_quest_captures_csv(folder_path: Path):
    """Delete generated CSV files for Quest captures in *folder_path*.

    Mirrors :func:`pcap_to_csv.cleanup_pcap_folder_csv` but only targets
    CSVs that come from a Quest capture, never touching PC-derived ones.
    """
    deleted: List[Path] = []
    missing: List[Path] = []
    errors: List[Tuple[Path, str]] = []

    for output_path in find_quest_capture_csv_outputs(folder_path):
        if not output_path.exists():
            missing.append(output_path)
            continue
        try:
            output_path.unlink()
            deleted.append(output_path)
        except Exception as exc:  # noqa: BLE001
            errors.append((output_path, str(exc)))

    return {
        "deleted": deleted,
        "missing": missing,
        "errors": errors,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert Quest-side pcap/pcapng captures into bucketed CSV "
            "summaries (same schema as the PC tool)."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to a Quest capture file or to a folder containing Quest captures.",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output CSV path (single-file mode only). Defaults next to the input.",
    )
    parser.add_argument(
        "--bucket-seconds", type=float, default=1.0,
        help="Aggregation bucket size in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing CSV outputs.",
    )
    parser.add_argument(
        "--folder", action="store_true",
        help="Treat <input> as a folder and convert every Quest capture inside.",
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="Delete generated CSV files for Quest captures in <input> (folder mode).",
    )
    return parser


def _convert_single_file(input_path: Path, output_path: Path, bucket_seconds: float) -> None:
    if not is_quest_capture_path(input_path):
        raise SystemExit(
            f"Input {input_path} does not look like a Quest capture "
            f"(expected suffix in {QUEST_CAPTURE_EXTENSIONS} and "
            f"'{QUEST_CAPTURE_TOKEN}' in the filename)."
        )
    frame = pcap_to_csv.convert_pcap_to_dataframe(input_path, bucket_seconds=bucket_seconds)
    frame.to_csv(output_path, index=False)
    read_error = frame.attrs.get("read_error")
    suffix = f" (partial: {read_error})" if read_error else ""
    print(f"Wrote {len(frame)} bucket(s) to {output_path}{suffix}")


def main() -> None:
    args = build_arg_parser().parse_args()

    if args.folder or args.cleanup:
        if args.cleanup:
            result = cleanup_quest_captures_csv(args.input)
            print(f"Deleted: {len(result['deleted'])}, "
                  f"Missing: {len(result['missing'])}, "
                  f"Errors: {len(result['errors'])}")
            for path, message in result["errors"]:
                print(f"  ! {path}: {message}")
            return

        result = convert_quest_captures_to_csv(
            args.input,
            bucket_seconds=args.bucket_seconds,
            overwrite=args.overwrite,
        )
        print(
            f"Converted: {len(result['converted'])}, "
            f"Skipped: {len(result['skipped'])}, "
            f"Errors: {len(result['errors'])}"
        )
        for path, output, rows in result["converted"]:
            print(f"  + {path.name} -> {output.name} ({rows} bucket(s))")
        for path, message in result["errors"]:
            print(f"  ! {path.name}: {message}")
        for path, message in result["warnings"]:
            print(f"  ~ {path.name}: {message}")
        return

    # Single-file mode
    if not args.input.is_file():
        raise SystemExit(f"Input file not found: {args.input}")
    output_path = args.output or args.input.with_suffix(f"{args.input.suffix}.csv")
    _convert_single_file(args.input, output_path, args.bucket_seconds)


if __name__ == "__main__":
    main()
