# Unity Base Engine Benchmark — Conclusions

_Generated on 2026-08-17 from the base-engine subset of the analysis outputs in `analysis_results`._

This report keeps only the non-network engine metrics (FPS, CPU, GPU, Memory). Network and PCAP metrics are excluded because this pass is specifically for the base-engine comparison.

---

## Methodology

For each stat file, the report reuses the previously computed per-frame observations and compares only the base-engine libraries: Godot, Unity base, Unity GPU, and Unity DOTS. The ranking uses the six pairwise comparisons among those four systems.

Statistical comparison uses:

- **Mann-Whitney U** (two-sided, normal approximation with tie correction, p-value via erf),
- **Cliff's delta** effect size with Romano et al. (2006) thresholds: negligible |δ| < 0.147, small < 0.33, medium < 0.474, large ≥ 0.474,
- a pair is treated as **decisive** when p < 0.05 *and* the effect is at least *small*.

The report ignores network and PCAP metrics entirely, so the conclusions are driven only by FPS, CPU, GPU, and Memory.

---

## Overall Ranking

The score below is the sum of *weighted decisive wins* per library. A win counts 3 for a large effect, 2 for medium, 1 for small (negligible effects are ignored).

### PC

| Rank | Library | Score |
|:----:|:--------|------:|
| 1 | Unity GPU | 29.0 |
| 2 | Unity base | 9.0 |
| 3 | Unity DOTS | 7.0 |
| 4 | Godot | 0.0 |

### Quest

| Rank | Library | Score |
|:----:|:--------|------:|
| 1 | Unity GPU | 27.0 |
| 2 | Unity DOTS | 18.0 |
| 3 | Unity base | 4.0 |
| 4 | Godot | 0.0 |

---

## Per-metric Breakdown

Each cell is the weighted-win score of the library in that metric. Empty cells mean the library never won that metric with a decisive effect.

### PC

| Metric | Godot | Unity base | Unity GPU | Unity DOTS |
|:-------|:----:|:----:|:----:|:----:|
| CPU (ms) | 0 | 3 | **9** | 3 |
| FPS | 0 | 3 | **9** | 3 |
| GPU (ms) | 0 | 0 | **6** | 1 |
| Memory (MB) | 0 | 3 | **5** | 0 |

### Quest

| Metric | Godot | Unity base | Unity GPU | Unity DOTS |
|:-------|:----:|:----:|:----:|:----:|
| CPU (ms) | 0 | 1 | **6** | **6** |
| FPS | 0 | 1 | **6** | **6** |
| GPU (ms) | 0 | 0 | **9** | 6 |
| Memory (MB) | 0 | 2 | **6** | 0 |

---

## Median Values Per Library (summary medians)

These are the summary medians aggregated per subsystem from `summary_by_subsystem.csv` (that file already collapses multiple captures into one representative value per platform and library). All values are medians in the displayed unit. Lower is better for every metric except FPS.

### PC

| Metric | Unit | Godot | Unity base | Unity GPU | Unity DOTS |
|:-------|:----:|:----:|:----:|:----:|:----:|
| CPU (ms) | ms | 65.14 ms | 5.52 ms | **0.72 ms** | 5.14 ms |
| FPS | frames/s | 15.35 frames/s | 183.89 frames/s | **1,393 frames/s** | 194.77 frames/s |
| GPU (ms) | ms | — | 0.69 ms | **0.16 ms** | 0.47 ms |
| Memory (MB) | MB | — | 370.22 MB | **350.50 MB** | 597.49 MB |

### Quest

| Metric | Unit | Godot | Unity base | Unity GPU | Unity DOTS |
|:-------|:----:|:----:|:----:|:----:|:----:|
| CPU (ms) | ms | 132.46 ms | 49.39 ms | 13.79 ms | **13.79 ms** |
| FPS | frames/s | 7.55 frames/s | 20.35 frames/s | **72.50 frames/s** | 72.49 frames/s |
| GPU (ms) | ms | 39.17 ms | 38.32 ms | **2.36 ms** | 4.00 ms |
| Memory (MB) | MB | 674.50 MB | 609.17 MB | **514.16 MB** | 717.91 MB |

---

## Per-library Analysis (pairwise-test medians)

Each section lists where the library wins (decisive positive effect vs at least one other library) and where it loses. The medians shown here come from the pairwise statistical-comparison rows in `statistical_comparisons.csv`, so they can differ from the summary table above because that table uses `median_of_medians` across captures. Effect sizes follow the Romano et al. (2006) thresholds.

### Godot

**Strengths** (where it beats the others):

- _(none)_

**Weaknesses** (where it loses to the others):

- **PC · CPU (ms)** — vs Unity base (66.26 ms → 5.41 ms), δ = -0.52 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Unity GPU (66.26 ms → 0.72 ms), δ = -0.83 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Unity DOTS (66.26 ms → 5.15 ms), δ = -0.54 (large), p = 0.00e+00
- **PC · FPS** — vs Unity base (15.09 frames/s → 184.71 frames/s), δ = +0.52 (large), p = 0.00e+00
- **PC · FPS** — vs Unity GPU (15.09 frames/s → 1,385 frames/s), δ = +0.83 (large), p = 0.00e+00
- **PC · FPS** — vs Unity DOTS (15.09 frames/s → 193.99 frames/s), δ = +0.54 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Unity base (132.95 ms → 50.00 ms), δ = -0.20 (small), p = 0.00e+00
- **Quest · CPU (ms)** — vs Unity GPU (132.95 ms → 13.89 ms), δ = -0.91 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Unity DOTS (132.95 ms → 13.89 ms), δ = -0.92 (large), p = 0.00e+00
- **Quest · FPS** — vs Unity base (7.52 frames/s → 19.99 frames/s), δ = +0.20 (small), p = 0.00e+00
- **Quest · FPS** — vs Unity GPU (7.52 frames/s → 72.00 frames/s), δ = +0.91 (large), p = 0.00e+00
- **Quest · FPS** — vs Unity DOTS (7.52 frames/s → 72.00 frames/s), δ = +0.91 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity GPU (45.82 ms → 2.38 ms), δ = -1.00 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity DOTS (45.82 ms → 4.00 ms), δ = -0.96 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs Unity GPU (660.00 MB → 286.35 MB), δ = -0.25 (small), p = 0.00e+00

### Unity base

**Strengths** (where it beats the others):

- **PC · CPU (ms)** — vs Godot (66.26 ms → 5.41 ms), δ = -0.52 (large), p = 0.00e+00
- **PC · FPS** — vs Godot (15.09 frames/s → 184.71 frames/s), δ = +0.52 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs Unity DOTS (599.13 MB → 380.24 MB), δ = -1.00 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Godot (132.95 ms → 50.00 ms), δ = -0.20 (small), p = 0.00e+00
- **Quest · FPS** — vs Godot (7.52 frames/s → 19.99 frames/s), δ = +0.20 (small), p = 0.00e+00
- **Quest · Memory (MB)** — vs Unity DOTS (698.00 MB → 392.22 MB), δ = -0.33 (medium), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- **PC · CPU (ms)** — vs Unity GPU (5.41 ms → 0.72 ms), δ = +0.91 (large), p = 0.00e+00
- **PC · FPS** — vs Unity GPU (184.71 frames/s → 1,385 frames/s), δ = -0.91 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Unity GPU (0.65 ms → 0.16 ms), δ = +0.77 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Unity DOTS (0.65 ms → 0.48 ms), δ = +0.28 (small), p = 0.00e+00
- **PC · Memory (MB)** — vs Unity GPU (380.24 MB → 350.72 MB), δ = +0.35 (medium), p = 0.00e+00
- **Quest · CPU (ms)** — vs Unity GPU (50.00 ms → 13.89 ms), δ = +0.83 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Unity DOTS (50.00 ms → 13.89 ms), δ = +0.83 (large), p = 0.00e+00
- **Quest · FPS** — vs Unity GPU (19.99 frames/s → 72.00 frames/s), δ = -0.84 (large), p = 0.00e+00
- **Quest · FPS** — vs Unity DOTS (19.99 frames/s → 72.00 frames/s), δ = -0.84 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity GPU (38.79 ms → 2.38 ms), δ = +0.84 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity DOTS (38.79 ms → 4.00 ms), δ = +0.80 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs Unity GPU (392.22 MB → 286.35 MB), δ = +0.34 (medium), p = 0.00e+00

### Unity GPU

**Strengths** (where it beats the others):

- **PC · CPU (ms)** — vs Unity base (5.41 ms → 0.72 ms), δ = +0.91 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Unity DOTS (5.15 ms → 0.72 ms), δ = -0.95 (large), p = 0.00e+00
- **PC · CPU (ms)** — vs Godot (66.26 ms → 0.72 ms), δ = -0.83 (large), p = 0.00e+00
- **PC · FPS** — vs Unity base (184.71 frames/s → 1,385 frames/s), δ = -0.91 (large), p = 0.00e+00
- **PC · FPS** — vs Unity DOTS (193.99 frames/s → 1,385 frames/s), δ = +0.95 (large), p = 0.00e+00
- **PC · FPS** — vs Godot (15.09 frames/s → 1,385 frames/s), δ = +0.83 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Unity base (0.65 ms → 0.16 ms), δ = +0.77 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Unity DOTS (0.48 ms → 0.16 ms), δ = -0.70 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs Unity base (380.24 MB → 350.72 MB), δ = +0.35 (medium), p = 0.00e+00
- **PC · Memory (MB)** — vs Unity DOTS (599.13 MB → 350.72 MB), δ = -1.00 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Unity base (50.00 ms → 13.89 ms), δ = +0.83 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Godot (132.95 ms → 13.89 ms), δ = -0.91 (large), p = 0.00e+00
- **Quest · FPS** — vs Unity base (19.99 frames/s → 72.00 frames/s), δ = -0.84 (large), p = 0.00e+00
- **Quest · FPS** — vs Godot (7.52 frames/s → 72.00 frames/s), δ = +0.91 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity base (38.79 ms → 2.38 ms), δ = +0.84 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity DOTS (4.00 ms → 2.38 ms), δ = -0.53 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Godot (45.82 ms → 2.38 ms), δ = -1.00 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs Unity base (392.22 MB → 286.35 MB), δ = +0.34 (medium), p = 0.00e+00
- **Quest · Memory (MB)** — vs Unity DOTS (698.00 MB → 286.35 MB), δ = -0.52 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs Godot (660.00 MB → 286.35 MB), δ = -0.25 (small), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- _(none)_

### Unity DOTS

**Strengths** (where it beats the others):

- **PC · CPU (ms)** — vs Godot (66.26 ms → 5.15 ms), δ = -0.54 (large), p = 0.00e+00
- **PC · FPS** — vs Godot (15.09 frames/s → 193.99 frames/s), δ = +0.54 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Unity base (0.65 ms → 0.48 ms), δ = +0.28 (small), p = 0.00e+00
- **Quest · CPU (ms)** — vs Unity base (50.00 ms → 13.89 ms), δ = +0.83 (large), p = 0.00e+00
- **Quest · CPU (ms)** — vs Godot (132.95 ms → 13.89 ms), δ = -0.92 (large), p = 0.00e+00
- **Quest · FPS** — vs Unity base (19.99 frames/s → 72.00 frames/s), δ = -0.84 (large), p = 0.00e+00
- **Quest · FPS** — vs Godot (7.52 frames/s → 72.00 frames/s), δ = +0.91 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity base (38.79 ms → 4.00 ms), δ = +0.80 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Godot (45.82 ms → 4.00 ms), δ = -0.96 (large), p = 0.00e+00

**Weaknesses** (where it loses to the others):

- **PC · CPU (ms)** — vs Unity GPU (5.15 ms → 0.72 ms), δ = -0.95 (large), p = 0.00e+00
- **PC · FPS** — vs Unity GPU (193.99 frames/s → 1,385 frames/s), δ = +0.95 (large), p = 0.00e+00
- **PC · GPU (ms)** — vs Unity GPU (0.48 ms → 0.16 ms), δ = -0.70 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs Unity base (599.13 MB → 380.24 MB), δ = -1.00 (large), p = 0.00e+00
- **PC · Memory (MB)** — vs Unity GPU (599.13 MB → 350.72 MB), δ = -1.00 (large), p = 0.00e+00
- **Quest · GPU (ms)** — vs Unity GPU (4.00 ms → 2.38 ms), δ = -0.53 (large), p = 0.00e+00
- **Quest · Memory (MB)** — vs Unity base (698.00 MB → 392.22 MB), δ = -0.33 (medium), p = 0.00e+00
- **Quest · Memory (MB)** — vs Unity GPU (698.00 MB → 286.35 MB), δ = -0.52 (large), p = 0.00e+00

---

## Takeaways

- On PC, **Unity GPU** has the strongest weighted decisive-win score in this base-engine subset.
- On Quest, **Unity GPU** has the strongest weighted decisive-win score in this base-engine subset.
- The four-library comparison is strictly non-network: any network or PCAP metric was excluded from the ranking and the narrative.

---

## Caveats and Confidence

1. **Small number of captures.** Each library's verdict comes from a limited set of captures per platform (20 PC stat files / 44 Quest stat files in the filtered base subset).
2. **FPS comparison is load-sensitive.** Some captures were taken under different scene loads, so FPS is a useful signal but should still be read alongside CPU and GPU.
3. **Quest numbers are noisier.** Device thermal throttling, Wi-Fi quality, and Android scheduling all influence the Quest traces.
