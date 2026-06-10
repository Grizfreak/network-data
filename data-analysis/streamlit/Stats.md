# 📈 Metrics Engine Documentation

## Overview and Purpose

The Metrics Engine is a robust data analysis layer responsible for ingesting raw, fragmented profiling data from various benchmark sources (e.g., internal simulations, PCAP network captures, performance logs). Its primary function is to **standardize, normalize, and aggregate** these disparate metrics into consistent time-series plots suitable for comparison and visualization within the user interface.

The system ensures that regardless of how raw data was captured (whether it used milliseconds or microseconds, or if a metric name changed slightly), the user sees a predictable set of normalized metrics on the plot.

---

## 🖥️ I. Data Metrics and Measured Features

The engine handles five primary categories of performance measurement:

### A. System Performance & Timing
These metrics measure the efficiency of the underlying hardware/software pipeline.

| Feature | Code Keys Used | Description | Primary Unit(s) | Normalization Made |
| :--- | :--- | :--- | :--- | :--- |
| **Frame Rate (FPS)** | `fps` | Measures the Frames Per Second, indicating visual fluidity. | Frames/second | Derived from Frame Time ($\text{FPS} = 1000 / \text{FrameTimeMs}$). |
| **CPU Load** | `cpu` | The amount of processing time consumed by the CPU thread(s). | Milliseconds (ms) | Handles multiple source columns and converts various units (nanoseconds $\rightarrow$ milliseconds) to ensure consistency. |
| **GPU Load** | `gpu` | The rendering time taken by the Graphics Processing Unit (GPU). | Milliseconds (ms) | Standardizes disparate GPU time metrics (e.g., microseconds, nanoseconds) into a single MS unit. |
| **Memory Usage** | `memory` | Total allocated or used physical memory (RAM). | Megabytes (MB) | Normalizes byte counts ($\text{Bytes} \rightarrow \text{Megabytes}$). |

### B. Network Metrics (Latency & Reliability)
These metrics assess the quality and latency of connections between simulated clients/servers.

| Feature | Code Keys Used | Description | Primary Unit(s) | Normalization Made |
| :--- | :--- | :--- | :--- | :--- |
| **Ping** | `network_ping` | Round-trip time measurement, typically used for quick latency checks. | Milliseconds (ms) | Handles conversion between nanoseconds ($\text{ns}$) and milliseconds ($\text{ms}$). |
| **Round Trip Time (RTT)** | `network_rtt` | General measure of the total delay experienced by data packets. | Milliseconds (ms) | Supports multiple RTT calculation methods found in raw logs. |

### C. Network Metrics (Throughput & Load)
These metrics quantify how much data is being moved and transmitted. They are highly sensitive to different capture modes.

| Feature | Code Keys Used | Description | Primary Unit(s) | Distinction/Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Download Throughput** | `network_download` | The rate of data received by a client (Ingress). | Bytes/second, Bits/second | Supports multiple source columns (`TotalBytesReceived`, `NetInBytesPerSec`). |
| **Upload Throughput** | `network_upload` | The rate of data sent from the client to the server (Egress). | Bytes/second, Bits/second | Supports multiple source columns for outgoing traffic. |
| **Packets Transferred** | `pcap_packets`, `pcap_cumulative_packets` | Measures the count of individual packets exchanged over time. | Packets/sec or Count | Differentiates between *rate* (per second) and *total cumulative count*. |

---

## 💡 II. Plot Mechanics and Visualization Enhancements

The engine provides three distinct modes of data presentation, each optimized for a different type of analysis:

### A. Standard Time Series Mode
**Goal:** To observe how any metric changes smoothly over the duration of the benchmark run.
*   **X-Axis:** Always represents time (Seconds) or discrete frames.
*   **Functionality:** Simple data extraction and unit conversion. If a source file has `Time Stamp` and another has `Frame`, they are mapped correctly to maintain visual continuity regardless of the underlying capture mechanism.

### B. Per-GameObject Scaling Mode (The Simulation View)
This is the most complex view, designed for performance analysis in simulated multiplayer environments (e.g., stress testing a system with 100+ entities).
*   **Concept:** Instead of plotting load vs. time, this plots load vs. the **number of active GameObjects**.
*   **X-Axis:** Represented by the count of GameObjects (the "palier").
*   **Data Source:** It relies on special **Event Files** (`FinishedInstantiation`) which act as markers, simulating when a new GameObject was added to the scene.

### C. Key Optimizations and Aggregation Techniques

To ensure these plots are accurate and visually readable, the following data processing additions have been implemented:

1.  **Median Filtering for Burstiness Reduction:**
    *   Network traffic (like `pcap_packets`) is notoriously "bursty"—a few rapid packets followed by silence. If we used the raw average or last sample, the graph would be jagged and misleading.
    *   **Optimization:** When calculating load per segment (the space between two GameObject additions), the system calculates the **median** value of all samples in that segment. This de-noises the plot while accurately reflecting the *typical* traffic load at that scale.

2.  **Delta Calculation for Cumulative Metrics:**
    *   For cumulative counters (e.g., `Total Bytes Transferred`), a simple median of the large absolute numbers is meaningless when comparing two adjacent segments.
    *   **Optimization:** The engine calculates the **delta (difference)** between the current segment's median value and the previous segment's median value. This gives the true measure of *incremental cost* or "Bytes added by adding these GameObjects."

3.  **Fallback Mechanisms:**
    *   To prevent analysis failure, the system includes fallbacks:
        *   If an ideal time column is missing (`Time` vs `Frame`), it attempts to derive the X-axis from available adjacent columns.
        *   If a specific performance metric (like CPU Time) fails initial parsing, it checks secondary columns in the benchmark output that measure the same concept, maximizing data retention.

---

## ✨ Summary of Viewing Enhancements for Users

| Enhancement | User Benefit | Technical Mechanism |
| :--- | :--- | :--- |
| **Consistent Units** | Eliminates confusion when comparing metrics from different benchmarks (e.g., seeing both $\text{ns}$ and $\text{ms}$). | Automated unit conversion logic applied across all relevant metric functions. |
| **GameObject Scaling View** | Allows direct performance analysis: "How much load does 500 GameObjects cost?" without having to run a specific simulation size. | Mapping the loaded data (Time/Frame) onto `FinishedInstantiation` event markers, using the GameObject count as the X-axis. |
| **Smoothed Load Curves** | Provides clear trends and averages by mitigating the visual noise of bursty network traffic. | Use of the **median** within calculation windows. |
| **Clear Cost Delta** | Accurately measures the *impact* of adding new system complexity (e.g., a new type of GameObject). | Calculating $(\text{Current Value} - \text{Previous Value})$ for cumulative metrics. |