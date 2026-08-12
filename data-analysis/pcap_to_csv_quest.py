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
from typing import Callable, Iterable, List, Optional, Tuple, cast

import pandas as pd

import pcap_to_csv


# Substring used by tcpdump scripts to tag Quest captures. Matching is
# case-insensitive so it survives filesystem differences across platforms.
QUEST_CAPTURE_TOKEN = "capture"  # Changed from "quest_capture" for broader matching

# Quest captures are always pcapng in this project, but the conversion
# helper accepts both, so we keep the extension list aligned with the PC
# tool for consistency.
QUEST_CAPTURE_EXTENSIONS = (".pcap", ".pcapng")

# Filename tokens that mark a capture as Photon-specific. Used to decide
# whether the dominant-conversation filter should be applied.
PHOTON_CAPTURE_TOKENS = ("photon",)

# Loopback / link-local addresses that frequently pollute Quest captures
# and should not be considered when picking a "main" conversation.
_QUEST_CONVERSATION_EXCLUDED_IPS = (
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "255.255.255.255",
    "fe80::",
)


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


def is_photon_capture_path(path: Path) -> bool:
    """Return True if *path* looks like a Photon capture file.

    Detection is filename-based: the stem must contain ``photon`` after
    lowercasing. This matches the naming convention used by the
    project (e.g. ``photon_client_capture_*.pcap``,
    ``photon_server_capture_quest_capture_*.pcap``).
    """
    if not path.is_file():
        return False
    if path.suffix.lower() not in QUEST_CAPTURE_EXTENSIONS:
        return False
    return any(token in path.stem.lower() for token in PHOTON_CAPTURE_TOKENS)


def find_dominant_quest_conversation(
    pcap_path: Path,
    exclude_ips: Iterable[str] | None = None,
) -> Optional[Tuple[tuple[str, str], int]]:
    """Return the IP pair that exchanges the most packets in *pcap_path*.

    Thin wrapper around :func:`pcap_to_csv.find_dominant_conversation`
    that injects the default Quest-side exclusion list (loopback,
    multicast, etc.) so the result isn't biased by background traffic.
    Returns ``None`` when no IP packets were found or if all packets are filtered out.

    Note: If a capture contains data but scapy cannot extract any valid IP-layer conversations 
    (e.g., due to non-IP packet types, malformed captures, etc.), this function returns None.
    """
    merged_excluded = list(_QUEST_CONVERSATION_EXCLUDED_IPS)
    if exclude_ips:
        merged_excluded.extend(exclude_ips)
    result = pcap_to_csv.find_dominant_conversation(pcap_path, merged_excluded)
    # `result` is a tuple `(pair_with_count)` where pair_with_count itself 
    # is the (ip_pair, packet_count). If no packets found, it's an empty list.
    if not result:  # noqa: SIM108 - we check for falsy to catch None or []
        return None
    ip_pair = result[0]
    _packet_count = result[1]
    return (ip_pair, _packet_count)


def _photon_ip_filter_for(pcap_path: Path) -> Tuple[Optional[set[str]], Optional[Tuple[tuple[str, str], int]], Optional[str]]:
    """Compute the IP filter that keeps only the dominant Photon conversation.

    Returns a ``(ip_filter, pair_with_count, error)`` triple. ``ip_filter`` is
    ``None`` when no conversation could be found, in which case *error*
    explains why. The second element (pair with count) matches what
    :func:`pcap_to_csv.find_dominant_conversation` returns so callers can
    inspect the packet counts if needed.
    """
    try:
        pair_with_count = find_dominant_quest_conversation(pcap_path)
    except Exception as exc:  # noqa: BLE001 - we surface the message in the UI
        return None, None, f"Could not detect conversation: {exc}"
    if pair_with_count is None or len(pair_with_count) == 0:
        # Fallback for files with data but no detectable IP conversations (e.g., non-IP traffic).
        # We return a dummy pair and count of 1 to signal that the file was processed,
        # allowing the UI to proceed without erroring out on 'None'.
        return None, (("0.0.0.0", "0.0.0.0"), 1), "No IP packets found in capture; using dummy filter."
    # Unpack (pair, count).
    pair = pair_with_count[0]
    _count = pair_with_count[1]
    ip_filter = set(pair)
    return ip_filter, pair_with_count, None
    """Compute the IP filter that keeps only the dominant Photon conversation.

    Returns a ``(ip_filter, pair_with_count, error)`` triple. ``ip_filter`` is
    ``None`` when no conversation could be found, in which case *error*
    explains why. The second element (pair with count) matches what
    :func:`pcap_to_csv.find_dominant_conversation` returns so callers can
    inspect the packet counts if needed.
    """
    try:
        pair_with_count = find_dominant_quest_conversation(pcap_path)
    except Exception as exc:  # noqa: BLE001 - we surface the message in the UI
        return None, None, f"Could not detect conversation: {exc}"
    if pair_with_count is None or len(pair_with_count) == 0:
        return None, None, "No IP packets found in capture."
    # Unpack (pair, count).
    pair = pair_with_count[0]
    _count = pair_with_count[1]
    ip_filter = set(pair)
    return ip_filter, pair_with_count, None


def _iter_files_recursive(folder_path: Path, suffixes: tuple[str, ...] | None = None) -> Iterable[Path]:
    """Yield files under *folder_path*, recursing into subfolders (captures
    are sometimes nested one or more levels deep). Directories whose name
    starts with ``_`` or ``.`` are skipped (internal/backup folders such as
    ``_corrupted_backup``)."""
    for path in sorted(folder_path.rglob("*")):
        if not path.is_file():
            continue
        if suffixes is not None and path.suffix.lower() not in suffixes:
            continue
        if any(part.startswith(("_", ".")) for part in path.relative_to(folder_path).parts[:-1]):
            continue
        yield path


def find_quest_capture_files(folder_path: Path) -> List[Path]:
    """List all potential Quest capture files (pcap/pcapng) under
    *folder_path*, including any subfolders.

    A file is considered a candidate if it has the correct extension AND its name
    suggests it's a network capture, not a profiler dump. This helps exclude
    files like *_profiler_stats*.pcap or similar non-network data dumps.
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return []

    # Check if the folder is associated with Quest data by checking for a known CSV pattern
    has_quest_context = any(
        "com.IMT_Atlantique" in csv_file.name
        for csv_file in _iter_files_recursive(folder_path, (".csv",))
    )

    if not has_quest_context:
        return []  # Not a Quest data directory based on CSV content

    # Filter pcap/pcapng files to exclude common profiler/stats dumps
    network_captures = [
        p for p in _iter_files_recursive(folder_path, QUEST_CAPTURE_EXTENSIONS)
        if not any(token in p.stem.lower() for token in ("profiler", "stats"))
    ]
    return sorted(network_captures)


def find_quest_capture_csv_outputs(folder_path: Path) -> List[Path]:
    """List Quest-derived CSV files under *folder_path*, including subfolders."""
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    return sorted(
        p for p in _iter_files_recursive(folder_path, (".csv",))
        if _is_quest_csv_output(p)
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

    The returned list excludes directories where the only pcap/pcapng files are profiler/stats dumps,
    which should not be converted as network captures.
    """
    if not data_root.exists() or not data_root.is_dir():
        return []

    quest_folders: List[Path] = []
    for folder in sorted(data_root.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        # Check if the directory contains any CSV file associated with Quest (the original heuristic)
        has_quest_context = any(
            "com.IMT_Atlantique" in csv_file.name
            for csv_file in _iter_files_recursive(folder, (".csv",))
        )

        if has_quest_context:
            # Filter pcap/pcapng files to exclude common profiler/stats dumps, then check if there are valid captures.
            network_captures = [
                p for p in _iter_files_recursive(folder, QUEST_CAPTURE_EXTENSIONS)
                if not any(token in p.stem.lower() for token in ("profiler", "stats"))
            ]

            # Only include the directory if it has at least one valid network capture (not just profiler dumps).
            if network_captures:
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
    photon_conversation_filter: bool = False,
    progress_callback: Callable[[Path], None] | None = None,
):
    """Convert every Quest pcap/pcapng capture in *folder_path* to CSV.

    The output structure matches the PC tool: each ``foo.pcap`` produces
    ``foo.pcap.csv`` next to it. The conversion itself is delegated to
    :func:`pcap_to_csv.convert_pcap_to_dataframe` so the CSV schema is
    identical.

    When *photon_conversation_filter* is True, captures whose filename
    is recognised as a Photon capture (see
    :func:`is_photon_capture_path`) are filtered to keep only the
    conversation (IP pair) that exchanges the most packets. This is
    useful when a Quest capture contains background traffic mixed with
    the Photon session: the resulting CSV is then a clean view of the
    game-related packets only.

    Returns a dictionary with the same shape as
    :func:`pcap_to_csv.convert_pcap_folder_to_csv` so the Streamlit UI
    can render the result uniformly. ``warnings`` now also carries
    informational messages about which conversation was kept (when
    filtering is applied successfully).
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
        if progress_callback is not None:
            progress_callback(capture)

        output_path = capture.with_suffix(f"{capture.suffix}.csv")
        if output_path.exists() and not overwrite:
            skipped.append((capture, output_path))
            continue

        ip_filter: Optional[set[str]] = None
        if photon_conversation_filter and is_photon_capture_path(capture):
            ip_filter, pair_with_count, conv_error = _photon_ip_filter_for(capture)
            if conv_error is not None:
                warnings.append(
                    (capture, f"Photon conversation filter skipped: {conv_error}")
                )
                ip_filter = None
            else:
                # `pair_with_count` is a tuple `(ip_pair, packet_count)` from 
                # :func:`pcap_to_csv.find_dominant_conversation`. Extract the pair.
                (pair, _count) = pair_with_count  # noqa: N806 - we don't need count here
                warnings.append(
                    (
                        capture,
                        f"Photon conversation filter active on IPs "
                        f"{pair[0]} <-> {pair[1]}.",
                    )
                )

        try:
            frame: pd.DataFrame = pcap_to_csv.convert_pcap_to_dataframe(
                capture, bucket_seconds=bucket_seconds, ip_filter=ip_filter
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


def cleanup_quest_captures_csv(
    folder_path: Path,
    progress_callback: Callable[[Path], None] | None = None,
):
    """Delete generated CSV files for Quest captures in *folder_path*.

    Mirrors :func:`pcap_to_csv.cleanup_pcap_folder_csv` but only targets
    CSVs that come from a Quest capture, never touching PC-derived ones.
    """
    deleted: List[Path] = []
    missing: List[Path] = []
    errors: List[Tuple[Path, str]] = []

    for output_path in find_quest_capture_csv_outputs(folder_path):
        if progress_callback is not None:
            progress_callback(output_path)
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
        "--photon-conversation-filter", action="store_true",
        help=(
            "For Photon captures, detect the conversation (IP pair) with the "
            "most packets and keep only those packets in the output CSV. "
            "Has no effect on non-Photon captures."
        ),
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


def _convert_single_file(
    input_path: Path,
    output_path: Path,
    bucket_seconds: float,
    photon_conversation_filter: bool = False,
) -> None:
    if not is_quest_capture_path(input_path):
        raise SystemExit(
            f"Input {input_path} does not look like a Quest capture "
            f"(expected suffix in {QUEST_CAPTURE_EXTENSIONS} and "
            f"'{QUEST_CAPTURE_TOKEN}' in the filename)."
        )

    ip_filter: Optional[set[str]] = None
    extra_note = ""
    if photon_conversation_filter and is_photon_capture_path(input_path):
        ip_filter, pair, error = _photon_ip_filter_for(input_path)
        if error is not None:
            print(f"~ {input_path.name}: Photon filter skipped ({error})")
            ip_filter = None
        else:
            # `pair` is non-None when `error` is None.
            pair = cast(Tuple[str, str], pair)
            extra_note = (
                f" (Photon conversation filter on {pair[0]} <-> {pair[1]})"
            )

    frame = pcap_to_csv.convert_pcap_to_dataframe(
        input_path, bucket_seconds=bucket_seconds, ip_filter=ip_filter
    )
    frame.to_csv(output_path, index=False)
    read_error = frame.attrs.get("read_error")
    suffix = f" (partial: {read_error})" if read_error else ""
    print(f"Wrote {len(frame)} bucket(s) to {output_path}{suffix}{extra_note}")


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
            photon_conversation_filter=args.photon_conversation_filter,
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
    _convert_single_file(
        args.input,
        output_path,
        args.bucket_seconds,
        photon_conversation_filter=args.photon_conversation_filter,
    )


if __name__ == "__main__":
    main()
