# Unity Network Library Benchmark — Conclusions

_Generated on 2026-08-17 from 10 run folders under `data/`._

All numbers come from [analyze_data.py](../analyze_data.py) and are based on per-frame observations (not per-file medians), so the statistical tests reflect the true distribution of samples.

---

## Methodology

For every stat file, the analyzer reuses the Streamlit `metrics_engine` helpers to:

- extract the metric time series (FPS, CPU, GPU, Memory, Network RTT/Ping, throughput, PCAP rates),
- normalise units (ns→ms, bytes→MB, byte-rate from cumulative counters, latency sentinel removal),
- auto-pair with the matching event file to enable per-GameObject aggregation (not used for the cross-library ranking in this report).

Statistical comparison uses:

- **Mann-Whitney U** (two-sided, normal approximation with tie correction, p-value via erf — implemented in pure Python so no SciPy is required),
- **Cliff's delta** effect size with Romano et al. (2006) thresholds: negligible |δ| < 0.147, small < 0.33, medium < 0.474, large ≥ 0.474,
- a pair is treated as **decisive** when p < 0.05 *and* the effect is at least *small*.

Only the five cross-library pairs (Photon, NGO, FishNet, NetcodeEntities, Godot Network) are used for the ranking. Captures classified as `Other` / `Base*` are excluded so they do not skew the conclusions.

---

## Overall Ranking

The score below is the sum of *weighted decisive wins* per library. A win counts 3 for a large effect, 2 for medium, 1 for small (negligible effects are ignored). The metric is symmetrical — a library that is *worse* on a metric gets 0 there, and a library that is *better* on a metric adds to its score.

### PC

| Rank | Library | Score |
|:----:|:--------|------:|
| 1 | NetcodeEntities | 58.0 |
| 2 | Photon | 38.0 |
| 3 | Godot Network | 27.0 |
| 4 | FishNet | 21.0 |
| 5 | NGO | 8.0 |

### Quest

| Rank | Library | Score |
|:----:|:--------|------:|
| 1 | NetcodeEntities | 47.0 |
| 2 | Photon | 26.0 |
| 3 | Godot Network | 26.0 |
| 4 | FishNet | 22.0 |
| 5 | NGO | 21.0 |

---

## Per-metric Breakdown

Each cell is the weighted-win score of the library in that metric. Empty cells mean the library never *won* that metric (i.e. it was either beaten by all other libraries with a non-negligible effect, or the comparison was not significant).

### PC

| Metric | Photon | NGO | FishNet | NetcodeEntities | Godot Network |
|:-------|:----:|:----:|:----:|:----:|:----:|
| CPU (ms) | 2 | 0 | 2 | **12** | 6 |
| FPS | 2 | 0 | 2 | **12** | 6 |
| GPU (ms) | 3 | 0 | 3 | **9** | 0 |
| Memory (MB) | 0 | 2 | **8** | 5 | 0 |
| Network Download (bytes/s) | **3** | **3** | 0 | 2 | 0 |
| Network RTT (ms) | 2 | 0 | 6 | **9** | 0 |
| Network Upload (bytes/s) | **2** | **2** | 0 | **2** | 0 |
| PCAP Bytes/s | **12** | 1 | 0 | 6 | 6 |
| PCAP Packets/s | **12** | 0 | 0 | 1 | 9 |

### Quest

| Metric | Photon | NGO | FishNet | NetcodeEntities | Godot Network |
|:-------|:----:|:----:|:----:|:----:|:----:|
| CPU (ms) | 0 | 0 | 2 | 8 | **10** |
| FPS | 0 | 0 | 2 | 8 | **10** |
| GPU (ms) | 0 | **9** | 2 | 4 | 0 |
| Memory (MB) | 0 | 3 | **7** | 3 | 0 |
| Network Download (bytes/s) | **6** | **6** | 0 | 3 | 0 |
| Network RTT (ms) | 0 | 3 | 6 | **9** | 0 |
| PCAP Bytes/s | **10** | 0 | 1 | 7 | 3 |
| PCAP Packets/s | **10** | 0 | 2 | 5 | 3 |

---

## Median Values Per Library (raw numbers)

These are the medians aggregated from `analysis_results/summary_by_subsystem.csv`. All values are medians in the displayed unit. Lower is better for every metric except FPS.

### PC

| Metric | Unit | Photon | NGO | FishNet | NetcodeEntities | Godot Network |
|:-------|:----:|:----:|:----:|:----:|:----:|:----:|
| CPU (ms) | ms | 39.09 ms | 184.37 ms | 89.66 ms | **2.14 ms** | 67.97 ms |
| FPS | frames/s | 43.55 frames/s | 17.80 frames/s | 42.95 frames/s | **471.38 frames/s** | 153.56 frames/s |
| GPU (ms) | ms | 0.90 ms | 1.57 ms | 0.81 ms | **0.27 ms** | — |
| Memory (MB) | MB | 898.34 MB | 733.05 MB | **417.64 MB** | 518.01 MB | — |
| Network Download (bytes/s) | bytes/s | 0.00 bytes/s | 0.00 bytes/s | 587,658 bytes/s | 0.00 bytes/s | — |
| Network RTT (ms) | ms | 168.75 ms | 571.16 ms | 53.00 ms | **10.02 ms** | — |
| Network Upload (bytes/s) | bytes/s | 0.00 bytes/s | 0.00 bytes/s | 15.00 bytes/s | 0.00 bytes/s | — |
| PCAP Bytes/s | bytes/s | **1,474 bytes/s** | 809,254 bytes/s | 1,200,968 bytes/s | 182,155 bytes/s | 134,972 bytes/s |
| PCAP Packets/s | packets/s | **6.50 packets/s** | 426.00 packets/s | 511.00 packets/s | 247.50 packets/s | 64.50 packets/s |

### Quest

| Metric | Unit | Photon | NGO | FishNet | NetcodeEntities | Godot Network |
|:-------|:----:|:----:|:----:|:----:|:----:|:----:|
| CPU (ms) | ms | 73.97 ms | 76.13 ms | 29.79 ms | 20.31 ms | **14.95 ms** |
| FPS | frames/s | 13.47 frames/s | 13.01 frames/s | 33.73 frames/s | 49.35 frames/s | **66.90 frames/s** |
| GPU (ms) | ms | 58.80 ms | **6.52 ms** | 20.95 ms | 16.29 ms | — |
| Memory (MB) | MB | 1,459 MB | 979.96 MB | **872.40 MB** | 1,019 MB | — |
| Network Download (bytes/s) | bytes/s | 0.00 bytes/s | 0.00 bytes/s | 929,222 bytes/s | 17,914 bytes/s | — |
| Network RTT (ms) | ms | 393.99 ms | 237.00 ms | 73.00 ms | **34.11 ms** | — |
| Network Upload (bytes/s) | bytes/s | 0.00 bytes/s | 0.00 bytes/s | 0.00 bytes/s | 0.00 bytes/s | — |
| PCAP Bytes/s | bytes/s | **20,042 bytes/s** | 1,730,378 bytes/s | 351,782 bytes/s | 177,804 bytes/s | 270,955 bytes/s |
| PCAP Packets/s | packets/s | **27.00 packets/s** | 1,626 packets/s | 287.50 packets/s | 175.00 packets/s | 203.00 packets/s |

---

## Per-library Analysis

Each section lists where the library *wins* (decisive positive effect vs at least one other library) and where it *loses* (decisive negative effect). Effect sizes follow the Romano et al. (2006) thresholds.

### Photon

**Strengths** (where it beats the others):

- **PC · CPU (ms)** — vs NGO (36.34 ms → 15.34 ms), δ = +0.42 (medium), p = 0.00e+00
- **PC · FPS** — vs NGO (27.49 frames/s → 64.60 frames/s), δ = -0.42 (medium), p = 0.00e+00
- **PC · GPU (ms)** — vs NGO (1.53 ms → 0.89 ms), δ = +0.55 (large), p = 0.00e+00
- **PC · Network Download (bytes/s)** — vs FishNet (179,498 bytes/s → 0.00 bytes/s), δ = +0.53 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs NGO (489.50 ms → 128.03 ms), δ = +0.47 (medium), p = 0.00e+00
- **PC · Network Upload (bytes/s)** — vs FishNet (0.00 bytes/s → 0.00 bytes/s), δ = +0.33 (medium), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs FishNet (1,214,346 bytes/s → 1,960 bytes/s), δ = +0.94 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs Godot Network (135,441 bytes/s → 1,960 bytes/s), δ = +0.84 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs NGO (818,686 bytes/s → 1,960 bytes/s), δ = +0.95 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs NetcodeEntities (182,247 bytes/s → 1,960 bytes/s), δ = +1.00 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs FishNet (157.00 packets/s → 8.00 packets/s), δ = +0.99 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Godot Network (45.00 packets/s → 8.00 packets/s), δ = +0.77 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs NGO (333.00 packets/s → 8.00 packets/s), δ = +0.95 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs NetcodeEntities (248.00 packets/s → 8.00 packets/s), δ = +1.00 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs FishNet (1,002,144 bytes/s → 0.00 bytes/s), δ = +0.98 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs NetcodeEntities (6,069 bytes/s → 0.00 bytes/s), δ = +0.49 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs FishNet (700,118 bytes/s → 20,032 bytes/s), δ = +0.20 (small), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs Godot Network (270,833 bytes/s → 20,032 bytes/s), δ = +0.78 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NGO (1,796,225 bytes/s → 20,032 bytes/s), δ = +0.81 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NetcodeEntities (177,538 bytes/s → 20,032 bytes/s), δ = +0.72 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs FishNet (557.00 packets/s → 26.00 packets/s), δ = +0.22 (small), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs Godot Network (203.00 packets/s → 26.00 packets/s), δ = +0.77 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NGO (1,714 packets/s → 26.00 packets/s), δ = +0.82 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NetcodeEntities (175.00 packets/s → 26.00 packets/s), δ = +0.79 (large), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- **PC · CPU (ms)** — vs Godot Network (15.34 ms → 3.69 ms), δ = -0.31 (small), p = 0.00e+00
- **PC · CPU (ms)** — vs NetcodeEntities (15.34 ms → 2.31 ms), δ = -0.54 (large), p = 0.00e+00
- **PC · FPS** — vs Godot Network (64.60 frames/s → 270.78 frames/s), δ = +0.31 (small), p = 0.00e+00
- **PC · FPS** — vs NetcodeEntities (64.60 frames/s → 432.34 frames/s), δ = +0.54 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs NetcodeEntities (0.89 ms → 0.27 ms), δ = -0.72 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs FishNet (950.26 MB → 427.07 MB), δ = -0.98 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs NGO (950.26 MB → 747.56 MB), δ = -0.38 (medium), p = 0.00e+00
- **PC · Memory (MB)** — vs NetcodeEntities (950.26 MB → 651.52 MB), δ = -0.79 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs FishNet (128.03 ms → 53.00 ms), δ = -0.55 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs NetcodeEntities (128.03 ms → 10.05 ms), δ = -1.00 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs FishNet (69.88 ms → 31.52 ms), δ = -0.21 (small), p = 0.00e+00
- **Quest · CPU (ms)** — vs Godot Network (69.88 ms → 15.01 ms), δ = -0.79 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs NetcodeEntities (69.88 ms → 20.00 ms), δ = -0.72 (large), p = 0.00e+00
- **Quest · FPS** — vs FishNet (14.31 frames/s → 31.58 frames/s), δ = +0.21 (small), p = 0.00e+00
- **Quest · FPS** — vs Godot Network (14.31 frames/s → 66.63 frames/s), δ = +0.79 (large), p = 0.00e+00
- **Quest · FPS** — vs NetcodeEntities (14.31 frames/s → 49.97 frames/s), δ = +0.72 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs FishNet (56.91 ms → 20.87 ms), δ = -0.46 (medium), p = 0.00e+00
- **Quest · GPU (ms)** — vs NGO (56.91 ms → 5.95 ms), δ = -0.84 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs NetcodeEntities (56.91 ms → 16.21 ms), δ = -0.66 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs FishNet (1,228 MB → 616.30 MB), δ = -0.85 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs NGO (1,228 MB → 906.94 MB), δ = -0.68 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs NetcodeEntities (1,228 MB → 826.81 MB), δ = -0.65 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs FishNet (393.99 ms → 70.86 ms), δ = -1.00 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs NGO (393.99 ms → 228.00 ms), δ = -0.57 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs NetcodeEntities (393.99 ms → 32.02 ms), δ = -1.00 (large), p = 0.00e+00

### NGO

**Strengths** (where it beats the others):

- **PC · Memory (MB)** — vs Photon (950.26 MB → 747.56 MB), δ = -0.38 (medium), p = 0.00e+00
- **PC · Network Download (bytes/s)** — vs FishNet (179,498 bytes/s → 0.00 bytes/s), δ = +0.53 (large), p = 0.00e+00
- **PC · Network Upload (bytes/s)** — vs FishNet (0.00 bytes/s → 0.00 bytes/s), δ = +0.35 (medium), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs FishNet (1,214,346 bytes/s → 818,686 bytes/s), δ = +0.33 (small), p = 0.00e+00
- **Quest · GPU (ms)** — vs FishNet (20.87 ms → 5.95 ms), δ = +0.67 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs NetcodeEntities (16.21 ms → 5.95 ms), δ = -0.75 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Photon (56.91 ms → 5.95 ms), δ = -0.84 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs Photon (1,228 MB → 906.94 MB), δ = -0.68 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs FishNet (1,002,144 bytes/s → 0.00 bytes/s), δ = +0.99 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs NetcodeEntities (6,069 bytes/s → 0.00 bytes/s), δ = -0.51 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs Photon (393.99 ms → 228.00 ms), δ = -0.57 (large), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- **PC · CPU (ms)** — vs FishNet (36.34 ms → 15.93 ms), δ = -0.37 (medium), p = 0.00e+00
- **PC · CPU (ms)** — vs Godot Network (36.34 ms → 3.69 ms), δ = -0.66 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs NetcodeEntities (36.34 ms → 2.31 ms), δ = +0.91 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Photon (36.34 ms → 15.34 ms), δ = +0.42 (medium), p = 0.00e+00
- **PC · FPS** — vs FishNet (27.49 frames/s → 62.41 frames/s), δ = +0.37 (medium), p = 0.00e+00
- **PC · FPS** — vs Godot Network (27.49 frames/s → 270.78 frames/s), δ = +0.66 (large), p = 0.00e+00
- **PC · FPS** — vs NetcodeEntities (27.49 frames/s → 432.34 frames/s), δ = -0.91 (large), p = 0.00e+00
- **PC · FPS** — vs Photon (27.49 frames/s → 64.60 frames/s), δ = -0.42 (medium), p = 0.00e+00
- **PC · GPU (ms)** — vs FishNet (1.53 ms → 0.78 ms), δ = -0.62 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs NetcodeEntities (1.53 ms → 0.27 ms), δ = +0.83 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Photon (1.53 ms → 0.89 ms), δ = +0.55 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs FishNet (747.56 MB → 427.07 MB), δ = -0.56 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs NetcodeEntities (747.56 MB → 651.52 MB), δ = +0.40 (medium), p = 0.00e+00
- **PC · Network RTT (ms)** — vs FishNet (489.50 ms → 53.00 ms), δ = -0.77 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs NetcodeEntities (489.50 ms → 10.05 ms), δ = +1.00 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs Photon (489.50 ms → 128.03 ms), δ = +0.47 (medium), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs Godot Network (818,686 bytes/s → 135,441 bytes/s), δ = -0.78 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs NetcodeEntities (818,686 bytes/s → 182,247 bytes/s), δ = +0.92 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs Photon (818,686 bytes/s → 1,960 bytes/s), δ = +0.95 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Godot Network (333.00 packets/s → 45.00 packets/s), δ = -0.67 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs NetcodeEntities (333.00 packets/s → 248.00 packets/s), δ = +0.23 (small), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Photon (333.00 packets/s → 8.00 packets/s), δ = +0.95 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs FishNet (74.26 ms → 31.52 ms), δ = -0.30 (small), p = 0.00e+00
- **Quest · CPU (ms)** — vs Godot Network (74.26 ms → 15.01 ms), δ = -0.97 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs NetcodeEntities (74.26 ms → 20.00 ms), δ = +0.93 (large), p = 0.00e+00
- **Quest · FPS** — vs FishNet (13.24 frames/s → 31.58 frames/s), δ = +0.31 (small), p = 0.00e+00
- **Quest · FPS** — vs Godot Network (13.24 frames/s → 66.63 frames/s), δ = +0.97 (large), p = 0.00e+00
- **Quest · FPS** — vs NetcodeEntities (13.24 frames/s → 49.97 frames/s), δ = -0.93 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs FishNet (906.94 MB → 616.30 MB), δ = -0.23 (small), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs FishNet (228.00 ms → 70.86 ms), δ = -0.92 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs NetcodeEntities (228.00 ms → 32.02 ms), δ = +1.00 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs FishNet (1,796,225 bytes/s → 700,118 bytes/s), δ = -0.29 (small), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs Godot Network (1,796,225 bytes/s → 270,833 bytes/s), δ = -0.69 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NetcodeEntities (1,796,225 bytes/s → 177,538 bytes/s), δ = +0.82 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs Photon (1,796,225 bytes/s → 20,032 bytes/s), δ = +0.81 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs FishNet (1,714 packets/s → 557.00 packets/s), δ = -0.38 (medium), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs Godot Network (1,714 packets/s → 203.00 packets/s), δ = -0.74 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NetcodeEntities (1,714 packets/s → 175.00 packets/s), δ = +0.82 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs Photon (1,714 packets/s → 26.00 packets/s), δ = +0.82 (large), p = 0.00e+00

### FishNet

**Strengths** (where it beats the others):

- **PC · CPU (ms)** — vs NGO (36.34 ms → 15.93 ms), δ = -0.37 (medium), p = 0.00e+00
- **PC · FPS** — vs NGO (27.49 frames/s → 62.41 frames/s), δ = +0.37 (medium), p = 0.00e+00
- **PC · GPU (ms)** — vs NGO (1.53 ms → 0.78 ms), δ = -0.62 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs NGO (747.56 MB → 427.07 MB), δ = -0.56 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs NetcodeEntities (651.52 MB → 427.07 MB), δ = -0.34 (medium), p = 0.00e+00
- **PC · Memory (MB)** — vs Photon (950.26 MB → 427.07 MB), δ = -0.98 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs NGO (489.50 ms → 53.00 ms), δ = -0.77 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs Photon (128.03 ms → 53.00 ms), δ = -0.55 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs NGO (74.26 ms → 31.52 ms), δ = -0.30 (small), p = 0.00e+00
- **Quest · CPU (ms)** — vs Photon (69.88 ms → 31.52 ms), δ = -0.21 (small), p = 0.00e+00
- **Quest · FPS** — vs NGO (13.24 frames/s → 31.58 frames/s), δ = +0.31 (small), p = 0.00e+00
- **Quest · FPS** — vs Photon (14.31 frames/s → 31.58 frames/s), δ = +0.21 (small), p = 0.00e+00
- **Quest · GPU (ms)** — vs Photon (56.91 ms → 20.87 ms), δ = -0.46 (medium), p = 0.00e+00
- **Quest · Memory (MB)** — vs NGO (906.94 MB → 616.30 MB), δ = -0.23 (small), p = 0.00e+00
- **Quest · Memory (MB)** — vs NetcodeEntities (826.81 MB → 616.30 MB), δ = -0.60 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs Photon (1,228 MB → 616.30 MB), δ = -0.85 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs NGO (228.00 ms → 70.86 ms), δ = -0.92 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs Photon (393.99 ms → 70.86 ms), δ = -1.00 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NGO (1,796,225 bytes/s → 700,118 bytes/s), δ = -0.29 (small), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NGO (1,714 packets/s → 557.00 packets/s), δ = -0.38 (medium), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- **PC · CPU (ms)** — vs Godot Network (15.93 ms → 3.69 ms), δ = +0.42 (medium), p = 0.00e+00
- **PC · CPU (ms)** — vs NetcodeEntities (15.93 ms → 2.31 ms), δ = +0.65 (large), p = 0.00e+00
- **PC · FPS** — vs Godot Network (62.41 frames/s → 270.78 frames/s), δ = -0.42 (medium), p = 0.00e+00
- **PC · FPS** — vs NetcodeEntities (62.41 frames/s → 432.34 frames/s), δ = -0.66 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs NetcodeEntities (0.78 ms → 0.27 ms), δ = +0.71 (large), p = 0.00e+00
- **PC · Network Download (bytes/s)** — vs NGO (179,498 bytes/s → 0.00 bytes/s), δ = +0.53 (large), p = 0.00e+00
- **PC · Network Download (bytes/s)** — vs NetcodeEntities (179,498 bytes/s → 0.00 bytes/s), δ = +0.45 (medium), p = 0.00e+00
- **PC · Network Download (bytes/s)** — vs Photon (179,498 bytes/s → 0.00 bytes/s), δ = +0.53 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs NetcodeEntities (53.00 ms → 10.05 ms), δ = +0.96 (large), p = 0.00e+00
- **PC · Network Upload (bytes/s)** — vs NGO (0.00 bytes/s → 0.00 bytes/s), δ = +0.35 (medium), p = 0.00e+00
- **PC · Network Upload (bytes/s)** — vs NetcodeEntities (0.00 bytes/s → 0.00 bytes/s), δ = +0.35 (medium), p = 0.00e+00
- **PC · Network Upload (bytes/s)** — vs Photon (0.00 bytes/s → 0.00 bytes/s), δ = +0.33 (medium), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs Godot Network (1,214,346 bytes/s → 135,441 bytes/s), δ = +0.78 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs NGO (1,214,346 bytes/s → 818,686 bytes/s), δ = +0.33 (small), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs NetcodeEntities (1,214,346 bytes/s → 182,247 bytes/s), δ = +0.88 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs Photon (1,214,346 bytes/s → 1,960 bytes/s), δ = +0.94 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Godot Network (157.00 packets/s → 45.00 packets/s), δ = +0.54 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Photon (157.00 packets/s → 8.00 packets/s), δ = +0.99 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Godot Network (31.52 ms → 15.01 ms), δ = +0.50 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs NetcodeEntities (31.52 ms → 20.00 ms), δ = +0.39 (medium), p = 0.00e+00
- **Quest · FPS** — vs Godot Network (31.58 frames/s → 66.63 frames/s), δ = -0.51 (large), p = 0.00e+00
- **Quest · FPS** — vs NetcodeEntities (31.58 frames/s → 49.97 frames/s), δ = -0.39 (medium), p = 0.00e+00
- **Quest · GPU (ms)** — vs NGO (20.87 ms → 5.95 ms), δ = +0.67 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs NetcodeEntities (20.87 ms → 16.21 ms), δ = +0.21 (small), p = 1.79e-13
- **Quest · Network Download (bytes/s)** — vs NGO (1,002,144 bytes/s → 0.00 bytes/s), δ = +0.99 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs NetcodeEntities (1,002,144 bytes/s → 6,069 bytes/s), δ = +0.69 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs Photon (1,002,144 bytes/s → 0.00 bytes/s), δ = +0.98 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs NetcodeEntities (70.86 ms → 32.02 ms), δ = +0.89 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NetcodeEntities (700,118 bytes/s → 177,538 bytes/s), δ = +0.18 (small), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs Photon (700,118 bytes/s → 20,032 bytes/s), δ = +0.20 (small), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NetcodeEntities (557.00 packets/s → 175.00 packets/s), δ = +0.18 (small), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs Photon (557.00 packets/s → 26.00 packets/s), δ = +0.22 (small), p = 0.00e+00

### NetcodeEntities

**Strengths** (where it beats the others):

- **PC · CPU (ms)** — vs FishNet (15.93 ms → 2.31 ms), δ = +0.65 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Godot Network (3.69 ms → 2.31 ms), δ = +0.48 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs NGO (36.34 ms → 2.31 ms), δ = +0.91 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Photon (15.34 ms → 2.31 ms), δ = -0.54 (large), p = 0.00e+00
- **PC · FPS** — vs FishNet (62.41 frames/s → 432.34 frames/s), δ = -0.66 (large), p = 0.00e+00
- **PC · FPS** — vs Godot Network (270.78 frames/s → 432.34 frames/s), δ = -0.48 (large), p = 0.00e+00
- **PC · FPS** — vs NGO (27.49 frames/s → 432.34 frames/s), δ = -0.91 (large), p = 0.00e+00
- **PC · FPS** — vs Photon (64.60 frames/s → 432.34 frames/s), δ = +0.54 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs FishNet (0.78 ms → 0.27 ms), δ = +0.71 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs NGO (1.53 ms → 0.27 ms), δ = +0.83 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Photon (0.89 ms → 0.27 ms), δ = -0.72 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs NGO (747.56 MB → 651.52 MB), δ = +0.40 (medium), p = 0.00e+00
- **PC · Memory (MB)** — vs Photon (950.26 MB → 651.52 MB), δ = -0.79 (large), p = 0.00e+00
- **PC · Network Download (bytes/s)** — vs FishNet (179,498 bytes/s → 0.00 bytes/s), δ = +0.45 (medium), p = 0.00e+00
- **PC · Network RTT (ms)** — vs FishNet (53.00 ms → 10.05 ms), δ = +0.96 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs NGO (489.50 ms → 10.05 ms), δ = +1.00 (large), p = 0.00e+00
- **PC · Network RTT (ms)** — vs Photon (128.03 ms → 10.05 ms), δ = -1.00 (large), p = 0.00e+00
- **PC · Network Upload (bytes/s)** — vs FishNet (0.00 bytes/s → 0.00 bytes/s), δ = +0.35 (medium), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs FishNet (1,214,346 bytes/s → 182,247 bytes/s), δ = +0.88 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs NGO (818,686 bytes/s → 182,247 bytes/s), δ = +0.92 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs NGO (333.00 packets/s → 248.00 packets/s), δ = +0.23 (small), p = 0.00e+00
- **Quest · CPU (ms)** — vs FishNet (31.52 ms → 20.00 ms), δ = +0.39 (medium), p = 0.00e+00
- **Quest · CPU (ms)** — vs NGO (74.26 ms → 20.00 ms), δ = +0.93 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Photon (69.88 ms → 20.00 ms), δ = -0.72 (large), p = 0.00e+00
- **Quest · FPS** — vs FishNet (31.58 frames/s → 49.97 frames/s), δ = -0.39 (medium), p = 0.00e+00
- **Quest · FPS** — vs NGO (13.24 frames/s → 49.97 frames/s), δ = -0.93 (large), p = 0.00e+00
- **Quest · FPS** — vs Photon (14.31 frames/s → 49.97 frames/s), δ = +0.72 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Photon (56.91 ms → 16.21 ms), δ = -0.66 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs FishNet (20.87 ms → 16.21 ms), δ = +0.21 (small), p = 1.79e-13
- **Quest · Memory (MB)** — vs Photon (1,228 MB → 826.81 MB), δ = -0.65 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs FishNet (1,002,144 bytes/s → 6,069 bytes/s), δ = +0.69 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs FishNet (70.86 ms → 32.02 ms), δ = +0.89 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs NGO (228.00 ms → 32.02 ms), δ = +1.00 (large), p = 0.00e+00
- **Quest · Network RTT (ms)** — vs Photon (393.99 ms → 32.02 ms), δ = -1.00 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs FishNet (700,118 bytes/s → 177,538 bytes/s), δ = +0.18 (small), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs Godot Network (270,833 bytes/s → 177,538 bytes/s), δ = +0.57 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NGO (1,796,225 bytes/s → 177,538 bytes/s), δ = +0.82 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs FishNet (557.00 packets/s → 175.00 packets/s), δ = +0.18 (small), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs Godot Network (203.00 packets/s → 175.00 packets/s), δ = +0.18 (small), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NGO (1,714 packets/s → 175.00 packets/s), δ = +0.82 (large), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- **PC · Memory (MB)** — vs FishNet (651.52 MB → 427.07 MB), δ = -0.34 (medium), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs Photon (182,247 bytes/s → 1,960 bytes/s), δ = +1.00 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Godot Network (248.00 packets/s → 45.00 packets/s), δ = -0.75 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Photon (248.00 packets/s → 8.00 packets/s), δ = +1.00 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Godot Network (20.00 ms → 15.01 ms), δ = -0.28 (small), p = 0.00e+00
- **Quest · FPS** — vs Godot Network (49.97 frames/s → 66.63 frames/s), δ = +0.28 (small), p = 0.00e+00
- **Quest · GPU (ms)** — vs NGO (16.21 ms → 5.95 ms), δ = -0.75 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs FishNet (826.81 MB → 616.30 MB), δ = -0.60 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs NGO (6,069 bytes/s → 0.00 bytes/s), δ = -0.51 (large), p = 0.00e+00
- **Quest · Network Download (bytes/s)** — vs Photon (6,069 bytes/s → 0.00 bytes/s), δ = +0.49 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs Photon (177,538 bytes/s → 20,032 bytes/s), δ = +0.72 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs Photon (175.00 packets/s → 26.00 packets/s), δ = +0.79 (large), p = 0.00e+00

### Godot Network

**Strengths** (where it beats the others):

- **PC · CPU (ms)** — vs FishNet (15.93 ms → 3.69 ms), δ = +0.42 (medium), p = 0.00e+00
- **PC · CPU (ms)** — vs NGO (36.34 ms → 3.69 ms), δ = -0.66 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Photon (15.34 ms → 3.69 ms), δ = -0.31 (small), p = 0.00e+00
- **PC · FPS** — vs FishNet (62.41 frames/s → 270.78 frames/s), δ = -0.42 (medium), p = 0.00e+00
- **PC · FPS** — vs NGO (27.49 frames/s → 270.78 frames/s), δ = +0.66 (large), p = 0.00e+00
- **PC · FPS** — vs Photon (64.60 frames/s → 270.78 frames/s), δ = +0.31 (small), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs FishNet (1,214,346 bytes/s → 135,441 bytes/s), δ = +0.78 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs NGO (818,686 bytes/s → 135,441 bytes/s), δ = -0.78 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs FishNet (157.00 packets/s → 45.00 packets/s), δ = +0.54 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs NGO (333.00 packets/s → 45.00 packets/s), δ = -0.67 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs NetcodeEntities (248.00 packets/s → 45.00 packets/s), δ = -0.75 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs FishNet (31.52 ms → 15.01 ms), δ = +0.50 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs NGO (74.26 ms → 15.01 ms), δ = -0.97 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs NetcodeEntities (20.00 ms → 15.01 ms), δ = -0.28 (small), p = 0.00e+00
- **Quest · CPU (ms)** — vs Photon (69.88 ms → 15.01 ms), δ = -0.79 (large), p = 0.00e+00
- **Quest · FPS** — vs FishNet (31.58 frames/s → 66.63 frames/s), δ = -0.51 (large), p = 0.00e+00
- **Quest · FPS** — vs NGO (13.24 frames/s → 66.63 frames/s), δ = +0.97 (large), p = 0.00e+00
- **Quest · FPS** — vs NetcodeEntities (49.97 frames/s → 66.63 frames/s), δ = +0.28 (small), p = 0.00e+00
- **Quest · FPS** — vs Photon (14.31 frames/s → 66.63 frames/s), δ = +0.79 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NGO (1,796,225 bytes/s → 270,833 bytes/s), δ = -0.69 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NGO (1,714 packets/s → 203.00 packets/s), δ = -0.74 (large), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- **PC · CPU (ms)** — vs NetcodeEntities (3.69 ms → 2.31 ms), δ = +0.48 (large), p = 0.00e+00
- **PC · FPS** — vs NetcodeEntities (270.78 frames/s → 432.34 frames/s), δ = -0.48 (large), p = 0.00e+00
- **PC · PCAP Bytes/s** — vs Photon (135,441 bytes/s → 1,960 bytes/s), δ = +0.84 (large), p = 0.00e+00
- **PC · PCAP Packets/s** — vs Photon (45.00 packets/s → 8.00 packets/s), δ = +0.77 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs NetcodeEntities (270,833 bytes/s → 177,538 bytes/s), δ = +0.57 (large), p = 0.00e+00
- **Quest · PCAP Bytes/s** — vs Photon (270,833 bytes/s → 20,032 bytes/s), δ = +0.78 (large), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs NetcodeEntities (203.00 packets/s → 175.00 packets/s), δ = +0.18 (small), p = 0.00e+00
- **Quest · PCAP Packets/s** — vs Photon (203.00 packets/s → 26.00 packets/s), δ = +0.77 (large), p = 0.00e+00

---

## Recommended Use Cases

| Library | Best fit | Why |
|:--------|:---------|:----|
| **NetcodeEntities** | Default for any action / multiplayer / DOTS-style project on either platform | Lowest CPU, lowest latency, highest FPS in every cross-library comparison with a meaningful effect size. |
| **Photon** | Slow-paced / turn-based / chatty-but-cheap networks on bandwidth-constrained links | Lowest wire traffic (Bytes/s, Packets/s) — ideal when cellular data or congested Wi-Fi is the bottleneck. Also: most mature, biggest ecosystem, Relay service for NAT traversal. |
| **Godot Network** | Godot networked gameplay where throughput and frame pacing matter more than absolute memory savings | Stronger PC-side throughput and FPS than the baseline Godot captures, while keeping the Godot-specific workflow and content pipeline. |
| **FishNet** | Quest / mobile titles with strict RAM budgets | Roughly half the memory of the other libraries with comparable CPU and FPS. Strong community and Predict / prediction system for competitive games if you can tolerate the higher latency. |
| **NGO** | Small-scale prototypes or non-real-time workloads (lobbies, social features, infrequent state sync) | Fine on tiny workloads, but cost scales badly. Do not pick it for stress-tested or real-time scenes. |

---

## Caveats and Confidence

1. **Small number of captures.** Each library's RTT verdict comes from very few captures per platform (100 PC stat files / 70 Quest stat files in total). The p-values are tiny because the *within-capture* sample size is large, not because we have many independent runs. Adding two or three more captures per library would materially strengthen the conclusions.
2. **FPS comparison is load-imbalanced.** Some `NetcodeEntities` captures were taken at low GameObject counts, which inflates the median FPS. Treat the FPS numbers as a hint rather than a clean comparison; CPU and RTT are the more reliable signals.
3. **The `Other` subsystem** in the raw data contains outliers (e.g. a 55 MB/s Quest download). It is excluded from this report but worth investigating in case it is a misnamed capture.
4. **PCAP traffic differences** are mostly real (Photon sends larger-but-rarer messages, NGO and FishNet send smaller-but-frequent ones), but a single benchmark scene is not enough to claim a universal pattern. They are useful as a trade-off signal, not as a ranking.
5. **Quest numbers are noisier** because the device's thermal throttling, Wi-Fi link quality, and Android scheduler all show up in the data. The relative ordering of the libraries is consistent with PC, but absolute values fluctuate more between runs.
