# Network Plots Association System - Architecture Explanation

> This document lives under `docs/`; the code it describes
> (`metrics_engine.py`, `app.py`) is in
> [`data-analysis/streamlit/`](../../data-analysis/streamlit/).

## Overview
The network plots association system links multiple network metrics (Ping, Bytes Received/Sent, RPC Messages Received/Sent) into a unified 3-subplot visualization. The key concept is **label-based association**: all network sub-metrics from the same data source are grouped together using a unique label identifier.

---

## Step-by-Step Data Flow

### 1. **Metric Extraction Layer** (`metrics_engine.py`)

#### Stage 1a: Network Metric Detection
```python
def _has_network_columns(df: pd.DataFrame) -> bool:
    """Check if the DataFrame has any network-related columns."""
    network_cols = {
        "Ping (ns)", "Ping_ms",
        "Total Bytes Received (bytes)", "TotalBytesReceived",
        "Total Bytes Sent (bytes)", "TotalBytesSent",
        "Rpc Received", "PacketsIn",
        "Rpc Sent", "PacketsOut",
        # ... other network columns
    }
    return any(col in df.columns for col in network_cols)
```

**Purpose**: Determines if a CSV file contains network data (NGO/Photon) or hardware-only data (DOTS/GPU). This prevents errors when trying to extract network metrics from files that don't have them.

#### Stage 1b: Individual Metric Extraction
Each network metric is extracted separately in `metric_series_from_stats()`:

```python
if metric_key == "network_ping":
    if not _has_network_columns(df):
        return None, None
    if "Ping (ns)" in df.columns:
        series = pd.to_numeric(df["Ping (ns)"], errors="coerce") / 1000000.0
    elif "Ping_ms" in df.columns:
        series = pd.to_numeric(df["Ping_ms"], errors="coerce")
    else:
        return None, None
    plot_data = pd.DataFrame({"Frame": frame, "Ping (ms)": series})
    return plot_data.dropna().reset_index(drop=True), "Ping (ms)"
```

**Key Points**:
- **Flexible Column Detection**: Supports different naming conventions (NGO vs Photon):
  - NGO: `Ping (ns)` → converted to `Ping (ms)` (divide by 1,000,000)
  - Photon: `Ping_ms` → kept as is
  - NGO: `Total Bytes Received (bytes)` vs `Rpc Received`
  - Photon: `TotalBytesReceived` vs `PacketsIn`
  
- **Output Format**: Returns a tuple of `(DataFrame, column_name)`
  - DataFrame has "Frame" column (x-axis) and metric column (y-axis)
  - Column name identifies the metric (e.g., `"Ping (ms)"`, `"Bytes Received"`)

---

### 2. **Dataset Building Layer** (`build_datasets()`)

This layer calls `metric_series_from_stats()` for each metric and wraps results with **label information**:

```python
# Inside build_datasets() for each stat file
label = _format_label(sname)  # e.g., "PC - NGO Client" or "Quest - Photon Server"

series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname)
if series is not None:
    series["label"] = label  # ADD LABEL - THIS IS THE ASSOCIATION KEY
    series["_ycol"] = ycol    # Store the metric column name
    datasets.append((label, series))
```

**Association Mechanism**:
- Every data row in the DataFrame gets a `"label"` column containing the source identifier
- The `"_ycol"` column stores the metric column name for later retrieval
- The label is the **key** that associates all related sub-metrics together

---

### 3. **Multi-Metric Collection Layer** (`app.py`)

When "Network Data" is selected, the system collects all 5 network sub-metrics:

```python
if metric_key == "network_all":
    network_keys = [
        "network_ping",
        "network_bytes_recv",
        "network_bytes_sent",
        "network_rpc_recv",
        "network_rpc_sent"
    ]
    net_datasets = {}  # Dictionary: metric_key → list of (label, DataFrame) tuples
    
    for nk in network_keys:
        dsets, warns = build_datasets(
            stats_files=stats_files,
            events_files=events_files,
            user_pairings=user_pairings,
            selected_metric_key=nk,  # Extract ONE metric type
            selected_metric_label=nk,
            per_gameobject=per_gameobject,
        )
        if dsets:
            net_datasets[nk] = dsets  # Store: {"network_ping": [...], "network_bytes_recv": [...], ...}
```

**Data Structure After This Step**:
```
net_datasets = {
    "network_ping": [
        ("PC - NGO Client", DataFrame with columns: Frame, Ping (ms), label, _ycol),
        ("Quest - Photon Server", DataFrame ...),
    ],
    "network_bytes_recv": [
        ("PC - NGO Client", DataFrame with columns: Frame, Bytes Received, label, _ycol),
        ("Quest - Photon Server", DataFrame ...),
    ],
    # ... more metric types
}
```

---

### 4. **Label Aggregation** (Still in `app.py`)

Extract unique labels across ALL network metrics:

```python
# Collect unique labels
all_labels = set()
for k in net_datasets:                    # Iterate: network_ping, network_bytes_recv, ...
    for t in net_datasets[k]:            # Iterate: (label, DataFrame) tuples
        all_labels.add(t[0])              # Extract label: "PC - NGO Client", "Quest - Photon Server"

labels = sorted(list(all_labels))
# Result: ["PC - NGO Client", "Quest - Photon Server"]
```

**Purpose**: This creates a master list of unique data sources that have network data. All these sources will be plotted together.

---

### 5. **Network Plot Creation** (`create_network_plot()`)

The plotting function uses **label-based filtering** to associate metrics:

```python
def create_network_plot(net_datasets, selected_labels, per_gameobject, xcol):
    fig = make_subplots(rows=3, cols=1, ...)
    colors = px.colors.qualitative.Plotly
    
    for i, label in enumerate(selected_labels):        # For each data source
        color = colors[i % len(colors)]                # Assign a unique color per source
        
        # ============ ASSOCIATION POINT 1: PING ============
        if "network_ping" in net_datasets:
            series_list = [d for d in net_datasets["network_ping"] 
                          if d[0] == label]            # FILTER BY LABEL
            if series_list:
                df = series_list[0][1]                 # Get the DataFrame
                y_col = df["_ycol"].iloc[0]            # Get metric column name
                fig.add_trace(
                    go.Scatter(x=df[xcol], y=df[y_col], 
                              line=dict(color=color),
                              name=f"{label} Ping",
                              legendgroup=label),      # Group by label in legend
                    row=1, col=1
                )
        
        # ============ ASSOCIATION POINT 2: BANDWIDTH ============
        for k, l_suffix, l_dash in [
            ("network_bytes_recv", "Recv", "solid"),
            ("network_bytes_sent", "Sent", "dash")
        ]:
            if k in net_datasets:
                series_list = [d for d in net_datasets[k] 
                              if d[0] == label]        # FILTER BY LABEL
                if series_list:
                    df = series_list[0][1]
                    y_col = df["_ycol"].iloc[0]
                    fig.add_trace(
                        go.Scatter(x=df[xcol], y=df[y_col],
                                  line=dict(color=color, dash=l_dash),
                                  name=f"{label} Bytes {l_suffix}",
                                  legendgroup=label),
                        row=2, col=1
                    )
        
        # ============ ASSOCIATION POINT 3: MESSAGES ============
        for k, l_suffix, l_dash in [
            ("network_rpc_recv", "Recv", "solid"),
            ("network_rpc_sent", "Sent", "dash")
        ]:
            if k in net_datasets:
                series_list = [d for d in net_datasets[k] 
                              if d[0] == label]        # FILTER BY LABEL
                if series_list:
                    df = series_list[0][1]
                    y_col = df["_ycol"].iloc[0]
                    fig.add_trace(
                        go.Scatter(x=df[xcol], y=df[y_col],
                                  line=dict(color=color, dash=l_dash),
                                  name=f"{label} Msgs {l_suffix}",
                                  legendgroup=label),
                        row=3, col=1
                    )
```

---

## Association Mechanism Summary

### The Core Concept: **Label-Based Filtering**

```
┌─────────────────────────────────────────────────────────────────┐
│ FOR EACH DATA SOURCE LABEL (e.g., "PC - NGO Client")            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─ Network Ping     ─────────────────────────────────────┐     │
│  │ Filter: net_datasets["network_ping"] WHERE label match │     │
│  │ Plot in Row 1 with assigned color                      │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌─ Network Bytes    ─────────────────────────────────────┐     │
│  │ Filter: net_datasets["network_bytes_recv"] WHERE label │     │
│  │ Filter: net_datasets["network_bytes_sent"] WHERE label │     │
│  │ Plot in Row 2 with same color (different line styles) │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌─ Network Messages ─────────────────────────────────────┐     │
│  │ Filter: net_datasets["network_rpc_recv"] WHERE label   │     │
│  │ Filter: net_datasets["network_rpc_sent"] WHERE label   │     │
│  │ Plot in Row 3 with same color (different line styles) │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
│  All traces grouped with legendgroup=label for legend grouping   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

RESULT: All metrics from same source share:
  - Same color (visual cohesion)
  - Same legend group (can be toggled together)
  - Same x-axis (if shared_xaxes=True)
```

---

## Why This Design?

### 1. **Flexibility**
- Supports multiple data sources (PC + Quest) simultaneously
- Each source gets unique color and legend grouping
- Easy to toggle sources on/off in legend

### 2. **Scalability**
- Can add new network metrics without changing the association logic
- Just add new `if k in net_datasets:` block with same pattern

### 3. **Consistency**
- Same association key (label) used across all 5 metrics
- No need to manually maintain metric relationships
- Automatic alignment of traces on same subplot

### 4. **Maintainability**
- Single label string controls all associations for a source
- Easy to debug: search for label value to find all related traces
- Clear separation of concerns (extraction vs. plotting)

---

## Example: Real Data Flow

**Scenario**: NGO Client (PC) and Photon Server (Quest)

```
INPUT FILES:
- [PC] ngo_client_profiler_stats-2026.05.07-10.53.csv
- [Quest] photon_server_profiler_stats-2026.05.07-14.06.csv

STEP 1: Extract all 5 network metrics separately
build_datasets(..., metric_key="network_ping") →
  [("PC - NGO Client", df_ping_ngo), ("Quest - Photon Server", df_ping_photon)]

build_datasets(..., metric_key="network_bytes_recv") →
  [("PC - NGO Client", df_bytes_recv_ngo), ("Quest - Photon Server", df_bytes_recv_photon)]

... (repeat for network_bytes_sent, network_rpc_recv, network_rpc_sent)

STEP 2: Organize into nested dictionary
net_datasets = {
    "network_ping": [...],
    "network_bytes_recv": [...],
    "network_bytes_sent": [...],
    "network_rpc_recv": [...],
    "network_rpc_sent": [...]
}

STEP 3: Extract unique labels
labels = ["PC - NGO Client", "Quest - Photon Server"]

STEP 4: For each label, filter and plot across all metrics
For "PC - NGO Client":
  - Plot Ping data from net_datasets["network_ping"][0]         → Row 1 (Blue)
  - Plot Bytes Recv from net_datasets["network_bytes_recv"][0]  → Row 2 (Blue, solid)
  - Plot Bytes Sent from net_datasets["network_bytes_sent"][0]  → Row 2 (Blue, dashed)
  - Plot RPC Recv from net_datasets["network_rpc_recv"][0]      → Row 3 (Blue, solid)
  - Plot RPC Sent from net_datasets["network_rpc_sent"][0]      → Row 3 (Blue, dashed)

For "Quest - Photon Server":
  - Plot Ping data from net_datasets["network_ping"][1]         → Row 1 (Red)
  - Plot Bytes Recv from net_datasets["network_bytes_recv"][1]  → Row 2 (Red, solid)
  - Plot Bytes Sent from net_datasets["network_bytes_sent"][1]  → Row 2 (Red, dashed)
  - Plot RPC Recv from net_datasets["network_rpc_recv"][1]      → Row 3 (Red, solid)
  - Plot RPC Sent from net_datasets["network_rpc_sent"][1]      → Row 3 (Red, dashed)

RESULT: 3 subplots, each with 2 data sources, each source has all network metrics
```

---

## Key Takeaways

| Component | Role | Association Method |
|-----------|------|-------------------|
| **Extraction** | Extract individual metrics | Column name flexibility (NGO vs Photon) |
| **Wrapping** | Add label to DataFrame | `series["label"] = label` |
| **Collection** | Organize by metric type | Nested dictionary: `{metric_key: [(label, df), ...]}` |
| **Filtering** | Link metrics to source | `[d for d in net_datasets[k] if d[0] == label]` |
| **Visualization** | Plot and group | Color assignment + `legendgroup=label` |

The **label** is the single source of truth that associates all metrics from the same data source across all 3 subplots.
