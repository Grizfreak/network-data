"""Convert a pcap or pcapng capture into a bucketed CSV time series.

The output is meant to be loaded by the existing CSV plotting pipeline.
It records both bucket index and elapsed time so the same file can be graphed
on a frame-like axis or a real time axis.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from scapy.all import PcapNgReader, PcapReader  # type: ignore[attr-defined]
from scapy.layers.inet import ICMP, TCP, UDP
from scapy.packet import Packet


@dataclass
class BucketStats:
    packets: int = 0
    bytes: int = 0
    tcp_packets: int = 0
    udp_packets: int = 0
    icmp_packets: int = 0
    other_packets: int = 0


def _iter_packets(path: Path) -> Iterable[Packet]:
    for reader_cls in (PcapReader, PcapNgReader):
        try:
            with reader_cls(str(path)) as reader:
                for packet in reader:
                    yield packet
            return
        except Exception:
            continue
    raise RuntimeError(f"Unable to read capture: {path}")


def _packet_kind(packet: Packet) -> str:
    if packet.haslayer(TCP):
        return "tcp"
    if packet.haslayer(UDP):
        return "udp"
    if packet.haslayer(ICMP):
        return "icmp"
    return "other"


def _detect_capture_format(pcap_path: Path) -> str:
    with pcap_path.open("rb") as handle:
        header = handle.read(4)

    if header == b"\x0a\x0d\x0d\x0a":
        return "pcapng"

    if header in {
        b"\xd4\xc3\xb2\xa1",
        b"\xa1\xb2\xc3\xd4",
        b"\x4d\x3c\xb2\xa1",
        b"\xa1\xb2\x3c\x4d",
    }:
        return "pcap"

    return "unknown"


def _build_empty_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "Frame",
            "Time (s)",
            "Packets",
            "Bytes",
            "TCPPackets",
            "UDPPackets",
            "ICMPPackets",
            "OtherPackets",
            "PacketsPerSec",
            "BytesPerSec",
            "BitsPerSec",
            "CumulativePackets",
            "CumulativeBytes",
            "CumulativeBits",
        ]
    )


def _finalize_buckets(buckets: dict[int, BucketStats], bucket_seconds: float) -> pd.DataFrame:
    if not buckets:
        return _build_empty_dataframe()

    rows = []
    cumulative_packets = 0
    cumulative_bytes = 0
    for bucket_index in sorted(buckets):
        stats = buckets[bucket_index]
        start_s = bucket_index * bucket_seconds
        cumulative_packets += stats.packets
        cumulative_bytes += stats.bytes
        rows.append(
            {
                "Frame": bucket_index,
                "Time (s)": start_s,
                "Packets": stats.packets,
                "Bytes": stats.bytes,
                "TCPPackets": stats.tcp_packets,
                "UDPPackets": stats.udp_packets,
                "ICMPPackets": stats.icmp_packets,
                "OtherPackets": stats.other_packets,
                "PacketsPerSec": stats.packets / bucket_seconds,
                "BytesPerSec": stats.bytes / bucket_seconds,
                "BitsPerSec": (stats.bytes * 8.0) / bucket_seconds,
                "CumulativePackets": cumulative_packets,
                "CumulativeBytes": cumulative_bytes,
                "CumulativeBits": cumulative_bytes * 8.0,
            }
        )

    return pd.DataFrame(rows)


def _ingest_packet(packet: Packet, buckets: dict[int, BucketStats], bucket_seconds: float, start_time: float) -> None:
    elapsed = max(float(packet.time) - start_time, 0.0)
    bucket_index = int(elapsed // bucket_seconds)
    stats = buckets[bucket_index]
    stats.packets += 1
    stats.bytes += len(packet)

    kind = _packet_kind(packet)
    if kind == "tcp":
        stats.tcp_packets += 1
    elif kind == "udp":
        stats.udp_packets += 1
    elif kind == "icmp":
        stats.icmp_packets += 1
    else:
        stats.other_packets += 1


def convert_pcap_to_dataframe(pcap_path: Path, bucket_seconds: float = 1.0) -> pd.DataFrame:
    if bucket_seconds <= 0:
        raise ValueError("bucket_seconds must be greater than 0")

    buckets: dict[int, BucketStats] = defaultdict(BucketStats)
    start_time: float | None = None
    capture_error: Exception | None = None

    capture_format = _detect_capture_format(pcap_path)
    if capture_format == "pcapng":
        reader_classes = (PcapNgReader,)
    elif capture_format == "pcap":
        reader_classes = (PcapReader,)
    else:
        reader_classes = (PcapReader, PcapNgReader)

    for reader_cls in reader_classes:
        try:
            with reader_cls(str(pcap_path)) as reader:
                for packet in reader:
                    if start_time is None:
                        start_time = float(packet.time)
                    _ingest_packet(packet, buckets, bucket_seconds, start_time)
            frame = _finalize_buckets(buckets, bucket_seconds)
            if capture_error is not None:
                frame.attrs["read_error"] = f"{type(capture_error).__name__}: {capture_error}"
            return frame
        except Exception as exc:
            if start_time is not None and buckets:
                frame = _finalize_buckets(buckets, bucket_seconds)
                frame.attrs["read_error"] = f"{type(exc).__name__}: {exc}"
                frame.attrs["partial"] = True
                return frame
            capture_error = exc

    raise RuntimeError(f"Unable to read capture: {pcap_path}") from capture_error


def convert_pcap_folder_to_csv(folder_path: Path, bucket_seconds: float = 1.0, overwrite: bool = False):
    """Convert every pcap/pcapng file in a folder to CSV."""
    converted = []
    skipped = []
    errors = []
    warnings = []

    for pcap_path in sorted(folder_path.iterdir()):
        if not pcap_path.is_file():
            continue
        if pcap_path.suffix.lower() not in {".pcap", ".pcapng"}:
            continue

        output_path = pcap_path.with_suffix(f"{pcap_path.suffix}.csv")
        if output_path.exists() and not overwrite:
            skipped.append((pcap_path, output_path))
            continue

        try:
            frame = convert_pcap_to_dataframe(pcap_path, bucket_seconds=bucket_seconds)
            frame.to_csv(output_path, index=False)
            read_error = frame.attrs.get("read_error")
            converted.append((pcap_path, output_path, len(frame)))
            if read_error:
                warnings.append((pcap_path, f"Partial conversion completed: {read_error}"))
        except Exception as exc:
            errors.append((pcap_path, str(exc)))

    return {
        "converted": converted,
        "skipped": skipped,
        "warnings": warnings,
        "errors": errors,
    }


def iter_pcap_folder_outputs(folder_path: Path):
    """Yield generated CSV paths for pcap and pcapng files in a folder."""
    for pcap_path in sorted(folder_path.iterdir()):
        if not pcap_path.is_file():
            continue
        if pcap_path.suffix.lower() not in {".pcap", ".pcapng"}:
            continue
        yield pcap_path.with_suffix(f"{pcap_path.suffix}.csv")


def cleanup_pcap_folder_csv(folder_path: Path):
    """Delete generated CSV files for pcap/pcapng captures in a folder."""
    deleted = []
    missing = []
    errors = []

    for output_path in iter_pcap_folder_outputs(folder_path):
        if not output_path.exists():
            missing.append(output_path)
            continue
        try:
            output_path.unlink()
            deleted.append(output_path)
        except Exception as exc:
            errors.append((output_path, str(exc)))

    return {
        "deleted": deleted,
        "missing": missing,
        "errors": errors,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a pcap or pcapng capture into a bucketed CSV summary.")
    parser.add_argument("input", type=Path, help="Input .pcap or .pcapng file")
    parser.add_argument("-o", "--output", type=Path, help="Output CSV path")
    parser.add_argument("--bucket-seconds", type=float, default=1.0, help="Aggregation bucket size in seconds")
    return parser


def find_pc_capture_files(folder_path: Path) -> List[Path]:
    """List all potential PC capture files (pcap/pcapng) directly under *folder_path*.

    A file is considered a candidate if it has the correct extension.
    This function assumes that any pcap/pcapng file found in this folder
    is relevant for conversion, similar to how Quest captures are handled.
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return []

    # Return all pcap/pcapng files as candidates, checking extensions case-insensitively
    return sorted(
        p for p in folder_path.iterdir()
        if p.is_file() and p.suffix.lower() in (".pcap", ".pcapng")
    )


def main() -> None:
    args = build_arg_parser().parse_args()
    output_path = args.output or args.input.with_suffix(".csv")
    frame = convert_pcap_to_dataframe(args.input, bucket_seconds=args.bucket_seconds)
    frame.to_csv(output_path, index=False)
    read_error = frame.attrs.get("read_error")
    if read_error:
        print(f"Wrote {len(frame)} bucket(s) to {output_path} (partial: {read_error})")
    else:
        print(f"Wrote {len(frame)} bucket(s) to {output_path}")



if __name__ == "__main__":
    main()