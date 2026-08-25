# C4 — System Context

Who/what interacts with the benchmark suite as a whole. See the
[architecture overview](README.md) for the accompanying prose and the
[container diagram](c4-container.md) for the next level down.

Drawn as a plain Mermaid flowchart rather than `C4Context` — Mermaid's
built-in C4 renderer lays out relationship labels poorly on anything but
the simplest diagrams (overlapping text, illegible boundary titles); a
flowchart with the same C4 read (person / internal system boundary /
external system) renders reliably instead.

```mermaid
flowchart TB
    operator(["🧑 Benchmark Operator<br/>Runs builds on PC/Quest, collects results"])

    subgraph suite["Unity Network Benchmark Suite"]
        direction LR
        clients["Benchmark Clients<br/>Unity + Godot, one project per<br/>engine/networking combination"]
        analysis["Data Analysis Pipeline<br/>Python: CSV extraction,<br/>statistics, dashboard"]
        clients -- "CSV + profiler exports<br/>(files, not a live link)" --> analysis
    end

    photon["☁️ Photon Cloud<br/>Relay/matchmaking —<br/>Photon Fusion variant only"]
    wireshark["🦈 Wireshark / PCAP capture<br/>External packet capture for<br/>raw traffic analysis"]
    quest["🥽 Meta Quest device<br/>Standalone Android/XR target<br/>for a subset of runs"]

    operator -- "builds, deploys, runs" --> clients
    operator -- "runs scripts, browses dashboard" --> analysis
    clients -- "networked sessions<br/>(Photon Fusion variant only)" --> photon
    clients -- "deploys to / runs on" --> quest
    wireshark -- "captures traffic during a run" --> clients
    wireshark -- "PCAP files, via pcap_to_csv*.py" --> analysis
```

## Notes

- The suite has no live/online components: clients write local files, the
  operator moves them into `data-analysis/data/`, and analysis runs offline.
  The `clients` → `analysis` arrow is "produces files consumed by," not a
  runtime dependency.
- Photon Cloud is the only external network service in scope; all other
  networking libraries (NGO, FishNet, NetcodeEntities, Godot's multiplayer)
  run peer-to-peer/local-server without an external dependency.
