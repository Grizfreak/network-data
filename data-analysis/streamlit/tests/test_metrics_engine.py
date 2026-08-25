"""Tests for metrics_engine.py::get_available_metrics().

This function used to live in app.py as a hand-maintained, second list of
"which columns imply metric X is available" -- independent of (and drifted
from) the column checks metric_series_from_stats() actually performs. These
tests pin the specific real bugs that drift caused, now fixed by having
get_available_metrics() call the real extractor instead of duplicating its
column knowledge:

- "PCAP - Cumulative Packets"/"PCAP - Cumulative Bytes" were hardcoded
  labels that didn't match any real key in metric_options (the real keys
  are "PCAP - Packets/Bytes per GameObject (delta)"), so those metrics
  always showed as unavailable regardless of data.
- Memory/CPU/RTT falsely reported available for columns the extractor
  never actually reads (app_pss_MB/app_uss_MB, cpu_utilization_percentage,
  Ping (ns)).
- Upload/Download falsely reported UNavailable for cumulative-counter
  columns the extractor DOES support via a fallback.

Run with: python -m unittest discover -s streamlit/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from metrics_engine import get_available_metrics  # noqa: E402


METRIC_OPTIONS = {
    "FPS": "fps",
    "Memory (MB)": "memory",
    "CPU (ms)": "cpu",
    "GPU (ms)": "gpu",
    "PCAP - Packets/sec": "pcap_packets",
    "PCAP - Bytes/sec": "pcap_bytes",
    "PCAP - Packets per GameObject (delta)": "pcap_cumulative_packets",
    "PCAP - Bytes per GameObject (delta)": "pcap_cumulative_bytes",
    "Network - RTT (ms) - Calculated from RPC": "network_rtt_rpc",
    "Network - RTT (ms)": "network_rtt",
    "Network - Upload (bytes/sec)": "network_upload",
    "Network - Download (bytes/sec)": "network_download",
}


def _df(**columns):
    n = 5
    data = {"Frame": list(range(n))}
    for name, value in columns.items():
        data[name] = [value] * n
    return pd.DataFrame(data)


class GetAvailableMetricsTests(unittest.TestCase):
    def test_cumulative_packets_and_bytes_are_reported_available(self):
        # Regression: these two used to be hardcoded under labels that
        # didn't match metric_options at all.
        df = _df(CumulativePackets=100, CumulativeBytes=2048)
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertIn("PCAP - Packets per GameObject (delta)", available)
        self.assertIn("PCAP - Bytes per GameObject (delta)", available)

    def test_memory_requires_a_column_the_extractor_actually_reads(self):
        # app_pss_MB/app_uss_MB were checked by the old hand-maintained
        # list but _memory_series_from_stats() never reads them -- a file
        # with only those columns must NOT report Memory as available.
        df = _df(app_pss_MB=512.0)
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertNotIn("Memory (MB)", available)

        df_real = _df(app_rss_MB=512.0)
        available_real = get_available_metrics([("stats.csv", df_real)], METRIC_OPTIONS)
        self.assertIn("Memory (MB)", available_real)

    def test_cpu_utilization_percentage_alone_does_not_count(self):
        # metric_series_from_stats() explicitly ignores this column for
        # `cpu` (it's a cross-core sum, e.g. 600% on 6 cores) -- the old
        # list still checked for it, which could report CPU available for
        # a file that would then fail to actually plot anything.
        df = _df(cpu_utilization_percentage=150.0)
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertNotIn("CPU (ms)", available)

    def test_ping_ns_alone_does_not_count_as_rtt(self):
        # "Ping (ns)" only feeds the (unexposed in metric_options)
        # network_ping metric, not network_rtt.
        df = _df(**{"Ping (ns)": 5_000_000.0})
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertNotIn("Network - RTT (ms)", available)

    def test_upload_cumulative_counter_fallback_is_detected(self):
        # Regression: the old list only checked "Upload (bytes/sec)" /
        # "NetOutBytesPerSec", missing the cumulative-counter columns
        # metric_series_from_stats() supports via _bytes_per_sec_from_cumulative.
        df = pd.DataFrame(
            {
                "Frame": [0, 1, 2, 3, 4],
                "TotalBytesSent": [0, 100, 250, 400, 600],
            }
        )
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertIn("Network - Upload (bytes/sec)", available)

    def test_download_cumulative_counter_fallback_is_detected(self):
        df = pd.DataFrame(
            {
                "Frame": [0, 1, 2, 3, 4],
                "Total Bytes Received (bytes)": [0, 200, 500, 900, 1400],
            }
        )
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertIn("Network - Download (bytes/sec)", available)

    def test_no_matching_columns_reports_no_metrics(self):
        df = pd.DataFrame({"Frame": [0, 1, 2], "SomeUnrelatedColumn": [1, 2, 3]})
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertEqual(available, [])

    def test_fps_and_gpu_still_detected_as_before(self):
        df = _df(FPS=72.0, **{"GPU Frame Time (ns)": 8_000_000.0})
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertIn("FPS", available)
        self.assertIn("GPU (ms)", available)

    def test_result_order_matches_metric_options_order(self):
        df = _df(FPS=72.0, **{"GPU Frame Time (ns)": 8_000_000.0})
        available = get_available_metrics([("stats.csv", df)], METRIC_OPTIONS)
        self.assertEqual(available, ["FPS", "GPU (ms)"])


if __name__ == "__main__":
    unittest.main()
