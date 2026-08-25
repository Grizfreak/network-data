# Data Dictionary

What each metric means, what raw CSV column(s) it's read from, and the units
involved. This is a rendered view of two files that are the actual source of
truth — edit those, not this table, when a metric changes:

- [`data-analysis/ccl/metrics_catalog.py`](../data-analysis/ccl/metrics_catalog.py)
  — canonical `(key, label, unit, lower_is_better, description)` per metric,
  used by the `ccl/` statistical pipelines.
- [`data-analysis/streamlit/metrics_engine.py`](../data-analysis/streamlit/metrics_engine.py)
  — the actual column-detection logic (candidate column names, unit
  conversions, PC/Quest fallbacks) used by both the dashboard and `ccl/`.

For the event-CSV schema (`Frame,Time,Event,Value`) and the benchmark event
vocabulary (`PhaseStarted`, `FinishedInstantiation`, ...), see
[reference.md#runtime-outputs](reference.md#runtime-outputs) — not repeated
here.

## Metrics

| Key | Label | Unit | Lower is better? | Description |
|---|---|---|:---:|---|
| `fps` | FPS | frames/s | no | Sustained frame rate |
| `cpu` | CPU (ms) | ms | yes | Per-frame CPU work (lower = more headroom) |
| `gpu` | GPU (ms) | ms | yes | Per-frame GPU work |
| `memory` | Memory (MB) | MB | yes | Resident set / working set |
| `network_ping` | Network Ping (ms) | ms | yes | Lightweight ping latency |
| `network_rtt` | Network RTT (ms) | ms | yes | Round-trip latency between peers |
| `network_upload` | Network Upload (bytes/s) | bytes/s | yes | Bytes sent per second |
| `network_download` | Network Download (bytes/s) | bytes/s | yes | Bytes received per second |
| `pcap_packets` | PCAP Packets/s | packets/s | yes | PCAP-derived packet rate |
| `pcap_bytes` | PCAP Bytes/s | bytes/s | yes | PCAP-derived byte rate |

Two label conventions exist on purpose (see `metrics_catalog.py`'s module
docstring): the unit-suffixed `long_label` above is what `analyze_data.py`
writes into the `metric` column of its CSV exports, and what
`render_base_conclusions.py` filters on by exact text; `short_label` (plain,
no unit) is what `load_analysis.py` uses for its own, separately-computed
exports. Both are shown together above since they refer to the same metric.

`fps`/`cpu`/`gpu`/`memory` are the four **base-engine metrics**
(`metrics_catalog.BASE_ENGINE_KEYS`) used to compare Godot / Unity base /
Unity GPU / Unity DOTS without any networking involved — the `network_*`
and `pcap_*` metrics only apply to networked runs.

## Raw column → metric mapping

Different capture sources (PC profiler, Quest profiler, PCAP export) name
columns differently for the same measurement. `metrics_engine.py` tries
each candidate in order and uses the first one present; where a divisor is
listed, the raw value is divided by it to reach the target unit.

### `fps` → FPS

Tried in order: `FrameTimeMs` (→ `1000 / value`), `average_frame_rate`,
`FPS`. If the result looks like it's actually a frame-time-in-ms value
mislabeled (mean/median > 1000), it re-derives from `FrameTimeMs` if
present.

### `cpu` → CPU (ms)

| Candidate column | Divisor | Notes |
|---|---|---|
| `CPU Total Frame Time (ns)` | 1,000,000 | preferred, PC |
| `CPU Main Thread Frame Time (ns)` | 1,000,000 | |
| `Main Thread (ns)` | 1,000,000 | |
| `FrameTimeMs` | 1 | |
| *(fallback)* `average_frame_rate` | — | `1000 / fps`, used when no frame-time column exists (typical Quest captures) |

`cpu_utilization_percentage` is intentionally **not** used — it's a sum
across cores (e.g. 600% on 6 cores), which wouldn't be comparable across
PC/Quest if mixed in with the millisecond-based columns above.

### `gpu` → GPU (ms)

| Candidate column | Divisor | Notes |
|---|---|---|
| `GPU Frame Time (ns)` | 1,000,000 | PC; values outside `(0, 1e9]` ns are dropped as bad samples |
| `app_gpu_time_microseconds` | 1,000 | Quest; **16-bit counter, clamps at 65,535 µs (65.535 ms)** — see caveat below |

### `memory` → Memory (MB)

Tried in order: `Total Used Memory (bytes)` (÷ 1024²), `app_rss_MB`
(already in MB).

### `network_ping` / `network_rtt` / `network_upload` / `network_download`

Candidate columns (first present wins), all gated on
`_has_network_columns()` returning true for the file first:

- **Ping**: `Ping (ns)`, `Ping_ms`, `RTT_ms`
- **RTT**: `RTT (ms)`, `RTT_ms`, `RTT (ms) - Calculated from RPC`, `Ping_ms`
- **Upload**: `Upload (bytes/sec)`, `NetOutBytesPerSec`, `TotalBytesSent`
  (cumulative, converted to a rate via `diff()`/`dt`), `Total Bytes Sent (bytes)`
  (same)
- **Download**: mirror of Upload — `Download (bytes/sec)`,
  `NetInBytesPerSec`, `TotalBytesReceived`, `Total Bytes Received (bytes)`

Latency series (`Ping`/`RTT`) are sanitized before use — see
"Known caveats" below.

### `pcap_packets` / `pcap_bytes`

From PCAP-derived CSVs (`pcap_to_csv.py` / `pcap_to_csv_quest.py`), gated
on `_has_pcap_columns()`:

- **Packets**: `PacketsPerSec` (rate) or `Packets`; cumulative variant:
  `CumulativePackets`
- **Bytes**: `BytesPerSec`, `Bytes`, or `BitsPerSec`; cumulative variant:
  `CumulativeBytes` or `CumulativeBits`

Per-second buckets are rates (non-monotonic); the `Cumulative*` columns are
monotonic totals — see
[`LECTURE.md`](data-analysis/LECTURE.md#notes-on-reproducibility-and-exercises)
for why both exist.

## Known caveats

- **Latency sentinels are filtered, not plotted as 0/-1.**
  `_sanitize_latency_series()` in `metrics_engine.py` drops: Photon's `-1`
  ("not yet measured"), Photon's `0` ("no measurement available" — treating
  real sub-ms LAN pings as noise is an accepted tradeoff), and any value
  above 30,000 ms (a unit-mislabel guard — some Quest base/DOTS/GPU exports
  store nanoseconds in a column literally named `RTT (ms)`).
- **Quest GPU (ms) clamps at 65.535 ms.** `app_gpu_time_microseconds` is a
  16-bit counter (max 65535 µs). During real stalls the true GPU time
  exceeds that and gets truncated instead of reported — confirmed
  correlated with genuine stalls (capped rows average ~2.6 FPS vs. ~29 FPS
  uncapped), not noise. Hits ~75% of Godot-on-Quest samples, ~40-49% of
  Photon Fusion, ~27-33% of Unity base. Nothing downstream filters or flags
  this, so median/p95/max Quest GPU figures for the worst-performing
  subsystems are understated lower bounds, not exact values. (See
  [`ccl/README.md`](data-analysis/ccl/README.md#known-data-caveats-worth-knowing-before-trusting-a-number)
  for the full list of pipeline-level caveats.)
- **Two independently hand-maintained lists can drift**: which raw columns
  imply a metric is "available" (`app.py::get_available_metrics()`) is
  computed by calling the real extractor above — but `metrics_catalog.py`
  and this document are hand-maintained separately from the candidate-column
  logic in `metrics_engine.py`. Adding a new raw column name to
  `metrics_engine.py` without updating this file means the mapping section
  above goes stale (the metric itself keeps working — this is a
  documentation gap, not a code one).
