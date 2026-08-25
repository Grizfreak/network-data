# C4 — Container Diagram

One level down from the [system context](c4-context.md): the containers
inside the suite and how they exchange data. "Container" here means a
separately buildable/runnable unit (a Unity/Godot project, a shared package,
a script or app) — not a Docker container.

Drawn as a plain Mermaid flowchart rather than `C4Container` for the same
reason as the [context diagram](c4-context.md) — Mermaid's C4 renderer
doesn't lay out this many nodes/relationships without overlapping labels.

```mermaid
flowchart TB
    operator(["🧑 Benchmark Operator"])

    subgraph suite["Unity Network Benchmark Suite"]
        direction TB

        subgraph clientsGroup["Benchmark Clients"]
            direction LR
            pkg["com.imt-atlantique.benchmark-base<br/>Unity package (C#) — shared phase manager,<br/>spawning, movement, CSV/profiler export"]
            base["Baseline variants<br/>Unity: base, base_GPU, base_DOTS<br/>no networking, performance floor"]
            netcode["Networked Unity variants<br/>Unity: ngo, fishNet, photonFusion,<br/>NetcodeEntities"]
            godot["Godot variants<br/>Godot_Benchmark,<br/>Godot_Network_Benchmark"]
        end

        exports[("Run exports<br/>CSV + JSON, written to<br/>persistentDataPath")]

        subgraph analysisGroup["Data Analysis Pipeline"]
            direction LR
            pcap["pcap_to_csv(.py / _quest.py)<br/>Buckets raw PCAP<br/>captures into CSV"]
            dataset[("data-analysis/data/<br/>Canonical dataset, read<br/>by both pipelines")]
            shared["data_loader.py /<br/>metrics_engine.py<br/>File discovery, pairing,<br/>classification, extraction"]
            streamlit["streamlit/app.py<br/>Interactive dashboard"]
            ccl["ccl/ pipelines<br/>analyze_data.py + load_analysis.py<br/>→ Markdown conclusions"]
        end
    end

    photon["☁️ Photon Cloud"]
    wireshark["🦈 Wireshark"]

    operator -- "builds & runs" --> base
    operator -- "builds & runs" --> netcode
    operator -- "builds & runs" --> godot

    base -- "uses (Packages/manifest.json<br/>file: dependency)" --> pkg
    netcode -- "uses (Packages/manifest.json<br/>file: dependency)" --> pkg
    netcode -- "networked sessions<br/>(photonFusion project only)" --> photon

    pkg -- writes --> exports
    godot -- "writes (independent CSV writer)" --> exports
    wireshark -- "raw .pcap/.pcapng" --> pcap

    operator -- "collects/copies run exports<br/>manually (no extraction script)" --> dataset
    exports -.-> operator
    pcap -- "writes bucketed traffic CSV" --> dataset

    dataset -- "read by" --> shared
    shared -- "imported by" --> streamlit
    shared -- "imported by" --> ccl
    operator -- browses --> streamlit
    operator -- "runs; reads generated .md" --> ccl
```

## Reading notes

- **No extraction script exists anymore** (an older `extract_data.py` is
  superseded, see [reference.md#data-analysis-workflow](../reference.md#data-analysis-workflow)) —
  the operator collects/copies run exports into `data-analysis/data/`
  themselves. The dashed `exports -.-> operator` arrow stands in for that
  manual step (opening/copying files), not an automated one.
- `com.imt-atlantique.benchmark-base` is the one container every Unity
  variant shares — see [reference.md](../reference.md) for
  its internal three-layer split (`base.model` / `base.core` /
  `base.profiling`), which is deliberately left out of this diagram (that's
  a component-level concern, not a container-level one).
- `data_loader.py` / `metrics_engine.py` are drawn once because both
  `streamlit/` and `ccl/` import them directly (`ccl/` does
  `sys.path.append(.../streamlit)`) rather than each having its own copy —
  see [`ccl/README.md`](../data-analysis/ccl/README.md) for why, and for
  how to extend classification/metrics so both consumers pick it up.
- Godot variants write CSVs independently of the Unity `benchmark-base`
  package (different engine, no shared code) — they're compatible only
  because they follow the same output shape and naming convention that
  `classify_subsystem()` relies on.
