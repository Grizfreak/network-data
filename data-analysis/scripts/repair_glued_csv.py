"""
Repair CSVs corrupted by the ProfilerStatsToCSVExporter newline bug
(fixed in ProfilerStatsToCSVExporter.cs on 2026-08-12).

Root cause: when includeNetworkStats was true, WriteBucketRow() wrote a
newline right after the last profiler-stat column instead of after the
network columns (RTT/RTT-RPC/Upload/Download), and never terminated the
network columns with a newline at all. Every bucket's network values
therefore got glued onto the front of the next bucket's row with no
newline in between, shifting all downstream columns.

The data itself was never lost or reordered -- only the newline
placement was wrong. Every bucket still writes exactly `field_count`
(the header's column count) comma-separated tokens in the correct
order. So repair is: strip all embedded newlines from the body, re-split
purely on commas, and re-chunk into groups of `field_count` tokens.

Corrupted files are detected automatically (any *profiler_stats*.csv
under data/ where more than one data row's comma count doesn't match
the header) rather than from a hardcoded filename list, so this also
catches files captured with the buggy exporter before it was rebuilt,
regardless of date/subsystem.

Usage:
    python scripts/repair_glued_csv.py                  # dry run, scan + report
    python scripts/repair_glued_csv.py --apply           # write <name>_repaired.csv
    python scripts/repair_glued_csv.py --apply --swap    # also move the corrupted
                                                           # original into
                                                           # data/_corrupted_backup/
                                                           # and rename the repaired
                                                           # copy back to the
                                                           # original filename
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
BACKUP_ROOT = DATA_ROOT / "_corrupted_backup"


def find_candidate_files() -> list[Path]:
    files = sorted(DATA_ROOT.glob("*/*profiler_stats*.csv"))
    # Skip anything already produced by a previous repair run.
    return [f for f in files if "_repaired" not in f.stem]


def is_corrupted(lines: list[str], field_count: int) -> bool:
    data_lines = lines[1:]
    if not data_lines:
        return False
    mismatched = sum(1 for l in data_lines if len(l.split(",")) != field_count)
    # A single truncated last row (process killed mid-write) is normal and
    # harmless; the glued-newline bug misaligns most/all rows in the file.
    return mismatched > 1


def repair_file(path: Path, apply: bool) -> tuple[bool, str]:
    with path.open("r", newline="") as fh:
        raw = fh.read()

    lines = raw.splitlines()
    if not lines:
        return False, "SKIP (empty file)"

    header_line = lines[0]
    field_count = len(header_line.split(","))

    if not is_corrupted(lines, field_count):
        return False, f"clean (fields={field_count})"

    body = "\n".join(lines[1:])
    tokens = body.replace("\n", ",").split(",")
    if tokens and tokens[-1] == "":
        tokens.pop()

    remainder = len(tokens) % field_count
    dropped = 0
    if remainder != 0:
        dropped = remainder
        tokens = tokens[: len(tokens) - remainder]

    num_rows = len(tokens) // field_count
    rows = [
        ",".join(tokens[i * field_count : (i + 1) * field_count])
        for i in range(num_rows)
    ]

    status = (
        f"CORRUPTED -> repaired rows={num_rows} fields={field_count}"
        f"{f' (dropped {dropped} trailing tokens = partial bucket)' if dropped else ''}"
    )

    if apply:
        out_path = path.with_name(path.stem + "_repaired" + path.suffix)
        with out_path.open("w", newline="\n") as fh:
            fh.write(header_line + "\n")
            for row in rows:
                fh.write(row + "\n")
        status += f" -> wrote {out_path.name}"

    return True, status


def swap_in(path: Path) -> str:
    repaired_path = path.with_name(path.stem + "_repaired" + path.suffix)
    if not repaired_path.exists():
        return "SKIP (no repaired copy found)"

    rel_dir = path.parent.relative_to(DATA_ROOT)
    backup_dir = BACKUP_ROOT / rel_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / path.name

    shutil.move(str(path), str(backup_path))
    shutil.move(str(repaired_path), str(path))
    return f"swapped (original backed up to {backup_path.relative_to(DATA_ROOT.parent)})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write repaired copies (<name>_repaired.csv) for detected-corrupted files.",
    )
    parser.add_argument(
        "--swap",
        action="store_true",
        help="After repairing, move corrupted originals to data/_corrupted_backup/ "
        "and rename the repaired copies back to the original filenames. Implies --apply.",
    )
    args = parser.parse_args()
    apply = args.apply or args.swap

    files = find_candidate_files()
    if not files:
        print("No profiler_stats files found.")
        return

    corrupted_paths: list[Path] = []
    for path in files:
        rel = path.relative_to(DATA_ROOT.parent)
        try:
            corrupted, result = repair_file(path, apply)
        except Exception as exc:  # noqa: BLE001
            corrupted, result = False, f"FAILED ({exc})"
        print(f"{rel}: {result}")
        if corrupted:
            corrupted_paths.append(path)

    print(f"\n{len(corrupted_paths)} corrupted file(s) out of {len(files)} scanned.")

    if args.swap:
        print("\nSwapping repaired files into place...")
        for path in corrupted_paths:
            rel = path.relative_to(DATA_ROOT.parent)
            print(f"{rel}: {swap_in(path)}")


if __name__ == "__main__":
    main()
