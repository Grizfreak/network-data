"""Single source of truth for the metrics this pipeline knows about.

Previously this (key, label, unit, ...) information was hand-duplicated
across four files -- `analyze_data.py`, `load_analysis.py`,
`render_conclusions.py`, and `render_base_conclusions.py` -- with two
different label conventions in play:

- a unit-suffixed "long" label (e.g. "CPU (ms)"), used by `analyze_data.py`
  as the `metric` column text in its CSV exports, and therefore also by
  `render_base_conclusions.py` which filters those exports by that same
  text;
- a plain "short" label (e.g. "CPU"), used by `load_analysis.py` for its
  own, separately-computed load-based CSV exports.

Both conventions are kept here, explicitly, rather than derived from one
another by string surgery -- that keeps each consumer's existing output
byte-for-byte unchanged while removing the duplicated bookkeeping.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    key: str
    long_label: str
    short_label: str
    unit: str
    lower_is_better: bool
    description: str


METRICS: list[MetricSpec] = [
    MetricSpec("fps", "FPS", "FPS", "frames/s", False, "sustained frame rate"),
    MetricSpec("cpu", "CPU (ms)", "CPU", "ms", True, "per-frame CPU work (lower = more headroom)"),
    MetricSpec("gpu", "GPU (ms)", "GPU", "ms", True, "per-frame GPU work"),
    MetricSpec("memory", "Memory (MB)", "Memory", "MB", True, "resident set / working set"),
    MetricSpec("network_ping", "Network Ping (ms)", "Network Ping", "ms", True, "lightweight ping latency"),
    MetricSpec("network_rtt", "Network RTT (ms)", "Network RTT", "ms", True, "round-trip latency between peers"),
    MetricSpec("network_upload", "Network Upload (bytes/s)", "Network Upload", "bytes/s", True, "bytes sent per second"),
    MetricSpec("network_download", "Network Download (bytes/s)", "Network Download", "bytes/s", True, "bytes received per second"),
    MetricSpec("pcap_packets", "PCAP Packets/s", "PCAP Packets/s", "packets/s", True, "PCAP-derived packet rate"),
    MetricSpec("pcap_bytes", "PCAP Bytes/s", "PCAP Bytes/s", "bytes/s", True, "PCAP-derived byte rate"),
]

# The four non-network engine metrics used by the base-engine report
# (Godot / Unity base / Unity GPU / Unity DOTS comparison).
BASE_ENGINE_KEYS = {"fps", "cpu", "gpu", "memory"}
