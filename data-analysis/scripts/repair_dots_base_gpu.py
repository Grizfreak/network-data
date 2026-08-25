"""
Second-pass repair for the DOTS / Base-GPU / Base (bare) profiler_stats
files that were mis-repaired by scripts/repair_glued_csv.py.

Root cause of the mis-repair: that script assumed each bucket's true
token count equals the header's column count (14 for these files: 4
fixed + 6 profiler stats + 4 network columns). For NGO/FishNet/Photon/
NetcodeEntities that assumption is correct (verified monotonic). For
DOTS/Base-GPU/Base specifically it's wrong -- empirically, each bucket
is actually 20 tokens: the declared 14 columns plus 6 extra trailing
tokens (an echo of the next bucket's Main Thread / CPU* / GPU / Memory
values, from whatever duplicate-sampling bug affected these particular
scenes). Rechunking at 14 desynchronised every row after the first.

This script re-flattens the *currently on-disk* (already comma-correct,
just wrongly grouped) file -- no information was lost in the first
pass, only mis-grouped -- and re-chunks at the empirically-verified
correct size of 20, keeping only the first `len(header)` tokens of each
chunk (the 6 trailing echo tokens are discarded). A trailing partial
bucket (fewer than 20 leftover tokens) is dropped.

Usage:
    python scripts/repair_dots_base_gpu.py            # dry run
    python scripts/repair_dots_base_gpu.py --apply     # write + swap,
                                                        # backing up the
                                                        # current (mis-
                                                        # repaired) file to
                                                        # data/_corrupted_backup2/
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
BACKUP_ROOT = DATA_ROOT / "_corrupted_backup2"
TRUE_BUCKET_SIZE = 20


def find_candidate_files() -> list[Path]:
    patterns = [
        "dots_profiler_stats*.csv",
        "gpu_profiler_stats*.csv",
        "profiler_stats-*.csv",
    ]
    files: set[Path] = set()
    for pattern in patterns:
        files.update(DATA_ROOT.glob(f"*/{pattern}"))
    return sorted(f for f in files if "_repaired" not in f.stem)


def _is_monotonic(times: list[float]) -> bool:
    return all(times[i] >= times[i - 1] for i in range(1, len(times)))


def repair_file(path: Path, apply: bool) -> tuple[bool, str]:
    with path.open("r", newline="") as fh:
        raw = fh.read()
    lines = raw.splitlines()
    if not lines:
        return False, "SKIP (empty file)"

    header_line = lines[0]
    header = header_line.split(",")
    field_count = len(header)

    if field_count != 14:
        return False, f"skip (fields={field_count}, not a network-stats-wired baseline file)"

    if not any(lines[1:]):
        return False, "skip (no data rows)"

    # Some of these files were never actually mis-grouped (their true
    # bucket size already matches the header's 14 columns) -- check the
    # file as currently written before assuming it needs the size-20 fix.
    current_times = []
    for line in lines[1:]:
        if not line:
            continue
        try:
            current_times.append(float(line.split(",", 1)[0]))
        except ValueError:
            current_times = None
            break
    if current_times and _is_monotonic(current_times):
        return False, f"skip (already monotonic as-is, rows={len(current_times)})"

    body = "\n".join(lines[1:])
    tokens = body.replace("\n", ",").split(",")
    if tokens and tokens[-1] == "":
        tokens.pop()

    n = len(tokens)
    remainder = n % TRUE_BUCKET_SIZE
    usable = n - remainder
    num_rows = usable // TRUE_BUCKET_SIZE

    rows = []
    times = []
    for i in range(num_rows):
        chunk = tokens[i * TRUE_BUCKET_SIZE : i * TRUE_BUCKET_SIZE + field_count]
        rows.append(",".join(chunk))
        try:
            times.append(float(chunk[0]))
        except ValueError:
            return False, "FAILED (non-numeric Time value after re-chunking)"

    if not _is_monotonic(times):
        return False, f"FAILED (still non-monotonic after re-chunking at size {TRUE_BUCKET_SIZE})"

    status = f"OK rows={num_rows} (dropped {remainder} trailing tokens)"

    if apply:
        out_path = path.with_name(path.stem + "_repaired2" + path.suffix)
        with out_path.open("w", newline="\n") as fh:
            fh.write(header_line + "\n")
            for row in rows:
                fh.write(row + "\n")
        status += f" -> wrote {out_path.name}"

    return True, status


def swap_in(path: Path) -> str:
    repaired_path = path.with_name(path.stem + "_repaired2" + path.suffix)
    if not repaired_path.exists():
        return "SKIP (no repaired copy found)"

    rel_dir = path.parent.relative_to(DATA_ROOT)
    backup_dir = BACKUP_ROOT / rel_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / path.name

    shutil.move(str(path), str(backup_path))
    shutil.move(str(repaired_path), str(path))
    return f"swapped (mis-repaired copy backed up to {backup_path.relative_to(DATA_ROOT.parent)})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--swap", action="store_true", help="Implies --apply.")
    args = parser.parse_args()
    apply = args.apply or args.swap

    files = find_candidate_files()
    fixed: list[Path] = []
    for path in files:
        rel = path.relative_to(DATA_ROOT.parent)
        try:
            ok, msg = repair_file(path, apply)
        except Exception as exc:  # noqa: BLE001
            ok, msg = False, f"FAILED ({exc})"
        print(f"{rel}: {msg}")
        if ok:
            fixed.append(path)

    print(f"\n{len(fixed)} file(s) fixed out of {len(files)} scanned.")

    if args.swap:
        print("\nSwapping...")
        for path in fixed:
            rel = path.relative_to(DATA_ROOT.parent)
            print(f"{rel}: {swap_in(path)}")


if __name__ == "__main__":
    main()
