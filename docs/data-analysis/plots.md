# Plot Catalog

Every plot the pipeline actually produces, and what it shows. There are
exactly two producers — confirmed by grepping the codebase for plotting
calls (`px.`, `plt.`, `savefig`), not assumed from filenames:

- **`streamlit/plotting.py`** — one interactive template
  (`create_standard_plot()` / `build_metric_figures()`), instantiated once
  per metric you select in the dashboard. Nothing is saved to disk unless
  you use Plotly's own camera-icon "download PNG" on a given chart.
- **`ccl/generate_paper_figures.py`** — three static, named figures saved
  to `analysis_results/figures/` as PNG + PDF pairs.

Anything under `data-analysis/old/` (`fpsplot.py`, `memoryplot.py`,
`networkdataplot.py`, `pingplot.py`, `rpcplot.py`, `threadplot.py`) is a
retired matplotlib toolchain, superseded by the two producers above — not
listed here since it isn't part of the current pipeline.

## Streamlit dashboard — one chart per selected metric

One shared line-chart template, applied identically to whichever of the 12
metrics you pick in "Select Metrics to Display" (see
[data-dictionary.md](../data-dictionary.md) for what each metric actually
measures and which raw CSV column it comes from). What varies per-chart is
just the metric plotted — the mechanics are the same for all of them:

| Aspect | Behavior |
|---|---|
| X-axis | `Frame` (or `Time`, if "Time" x-axis mode is selected) per-frame, **or** `GameObjects` in per-GameObject ("palier") mode — one point per instantiation milestone instead of per captured frame. The two "... per GameObject (delta)" PCAP metrics only produce a chart at all in per-GameObject mode — they have no per-frame/time form. |
| Y-axis | The selected metric's value, in the unit from data-dictionary.md. |
| Lines | One line per run/subsystem selected via the Line Filter, colored by `label`. |
| Averaging | With "average across runs" on, every run sharing the same (platform, subsystem, role) collapses into one line labeled `"{platform} · {subsystem} {role} (avg of N runs)"` — the mean only. Min/max spread is computed (`average_series_across_runs()`) but **not currently drawn** as a shaded band on this chart (unlike `fig1-cpu-vs-load`'s IQR band below, which is a separate, static figure). |
| Reference line | `fps` charts get a dashed 72 FPS line (Quest 3/Pico 4 target refresh rate). `cpu`/`gpu` charts get a dashed 14 ms line (the frame-time budget for 72 FPS). No other metric gets a reference line. |
| Title | `"{metric} per GameObject pool"` in per-GameObject mode, `"{metric} vs {x-axis}"` otherwise. |

The 12 selectable metrics ([app.py](../../data-analysis/streamlit/app.py)'s
`metric_options` dict is the actual source of truth — this table follows its
labels, which don't all match [data-dictionary.md](../data-dictionary.md)'s
metric keys one-to-one, see the callout below the table):

| Metric | What the chart shows |
|---|---|
| FPS | Sustained frame rate against load — the 72 FPS line marks the VR comfort threshold. |
| CPU (ms) | Per-frame CPU cost against load — the 14 ms line marks the budget for 72 FPS. |
| GPU (ms) | Per-frame GPU cost against load — same 14 ms budget line. Quest values are understated above ~65 ms, see [data-dictionary.md's caveats](../data-dictionary.md#known-caveats). |
| Memory (MB) | Resident memory growth against load. |
| PCAP - Packets/sec | Packet rate from a raw capture (independent of what the engine self-reports), against Frame/Time — **or**, with per-GameObject aggregation on, the *median instantaneous rate* during each GameObjects palier. Answers "how intense was traffic while there were X objects." |
| PCAP - Bytes/sec | Same as above, for byte rate. |
| PCAP - Packets per GameObject (delta) | Only meaningful with per-GameObject aggregation on: the **difference in the cumulative packet counter** between the previous palier and this one — the actual count of packets sent while that batch of objects came in. Not derived from Packets/sec above — a per-segment delta of a *rate* would be meaningless (rates fluctuate bucket to bucket), so this reads `CumulativePackets` directly and diffs it. See [metrics_engine.py:584-595](../../data-analysis/streamlit/metrics_engine.py#L584-L595) for why the two aren't computed from each other. |
| PCAP - Bytes per GameObject (delta) | Same as above, for bytes. |
| Network - RTT (ms) - Calculated from RPC | Round-trip latency computed from RPC timestamps rather than the transport's own reporting (networked variants only; not every library exposes this). |
| Network - RTT (ms) | Round-trip latency as reported by the transport (networked variants only). |
| Network - Upload (bytes/sec) | Client/server upload throughput (networked variants only). |
| Network - Download (bytes/sec) | Client/server download throughput (networked variants only). |

> **Note:** this list is the dashboard's actual `metric_options` (`app.py`),
> not the [data-dictionary.md](../data-dictionary.md) metric list — the two
> overlap but aren't identical. The dashboard doesn't expose a
> `network_ping` selector even though data-dictionary.md documents one
> (`metrics_engine.py` can compute it, `app.py` just doesn't wire it into
> the multiselect), and it exposes 4 PCAP variants + a
> RPC-calculated-RTT variant that data-dictionary.md's table collapses down
> to `pcap_packets`/`pcap_bytes`/`network_rtt`. If you're looking for what a
> raw CSV column means, data-dictionary.md is still the source of truth —
> this table is about what shows up as a choice in the dashboard.

## `ccl/generate_paper_figures.py` — 3 static figures

Read [`data-analysis/ccl/README.md`'s "generate_paper_figures.py" section](ccl/README.md#generate_paper_figurespy)
for the previews; summarized here:

| File | What it shows |
|---|---|
| `fig1-cpu-vs-load.png` | CPU time vs. load, 2 panels (PC / Quest), **with an IQR shaded band** (median ± interquartile range across runs) and a log y-axis — the one plot in the whole pipeline that visualizes run-to-run spread directly on the chart. |
| `fig2-capacity.png` | Client/server entity-count ceilings per subsystem, as grouped bars — "how far did each system get before falling over," not a metric-over-time view. |
| `fig3-forest.png` | Forest plot of Cliff's delta (effect size) vs. each subsystem's baseline at a fixed load (20,000 entities) — answers "how much better/worse, with what confidence," not "what does the curve look like." |

These three are built from Pipeline B's (`load_analysis.py`) load-based CSV
exports, not from the raw per-frame data the Streamlit charts read — see
[ADR 0004](../architecture/decisions/0004-dual-analysis-pipelines.md) for
why the two pipelines exist and don't share output.

## A stale doc worth knowing about

[`NETWORK_PLOTS_ASSOCIATION_EXPLAINED.md`](NETWORK_PLOTS_ASSOCIATION_EXPLAINED.md)
describes network metrics as being combined into "a unified 3-subplot
visualization" — that's no longer how the code works. Current
`metrics_engine.py` extracts one metric at a time
(`metric_series_from_stats()` returns one series per call) and
`plotting.py` gives each selected metric its own separate figure (the
template above), not a combined subplot grid. The document's lower-level
walkthrough of column-name detection is still broadly accurate; only the
"3-subplot" framing at the top is outdated. Not fixed here since it wasn't
part of this catalog's scope — flagging it so it doesn't get taken at face
value.
