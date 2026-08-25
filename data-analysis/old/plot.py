import assemble
import matplotlib.pyplot as plt
import pandas as pd
import os
import argparse
import fpsplot
import threadplot
import memoryplot
import networkdataplot
import fpsPerGameObjectplot
import rpcplot
import pingplot

THREAD_CLAMP_MAX_MS = 200
SAVE_DPI = 600
FIGURE_SIZE = (24, 8)

class FigsAndName:
    def __init__(self):
        self.figs = []
        self.name = ""


def _fps_series_from_stats(data):
    frame_column = None
    if "Frame" in data.columns:
        frame_column = "Frame"
    elif "Time Stamp" in data.columns:
        frame_column = "Time Stamp"
    else:
        raise ValueError("Missing Frame or Time Stamp column for FPS comparison")

    fps_column = None
    if "FPS" in data.columns:
        fps_column = "FPS"
    elif "average_frame_rate" in data.columns:
        fps_column = "average_frame_rate"
    else:
        raise ValueError("Missing FPS column for FPS comparison")

    plot_data = data[[frame_column, fps_column]].copy()
    plot_data.columns = ["Frame", "FPS"]
    plot_data["Frame"] = pd.to_numeric(plot_data["Frame"], errors="coerce")
    plot_data["FPS"] = pd.to_numeric(plot_data["FPS"], errors="coerce")
    return plot_data.dropna(subset=["Frame", "FPS"])


def _frame_series(data):
    if "Frame" in data.columns:
        return pd.to_numeric(data["Frame"], errors="coerce")
    if "Time Stamp" in data.columns:
        return pd.to_numeric(data["Time Stamp"], errors="coerce")
    raise ValueError("Missing Frame or Time Stamp column")


def _metric_series_from_stats(data, metric_key):
    frame = _frame_series(data)
    if metric_key == "cpu":
        candidates = [
            ("CPU Total Frame Time (ns)", 1_000_000.0),
            ("CPU Main Thread Frame Time (ns)", 1_000_000.0),
            ("Main Thread (ns)", 1_000_000.0),
            ("FrameTimeMs", 1.0),
        ]
        output_column = "CPU (ms)"
    elif metric_key == "gpu":
        candidates = [
            ("GPU Frame Time (ns)", 1_000_000.0),
            ("app_gpu_time_microseconds", 1000.0),
        ]
        output_column = "GPU (ms)"
    else:
        raise ValueError(f"Unsupported metric key: {metric_key}")

    metric_series = None
    for column, divisor in candidates:
        if column not in data.columns:
            continue
        candidate = pd.to_numeric(data[column], errors="coerce")
        if candidate.isna().all():
            continue
        metric_series = candidate / divisor
        break

    if metric_series is None:
        raise ValueError(f"Missing required columns for {metric_key} comparison")

    plot_data = pd.DataFrame({"Frame": frame, output_column: metric_series})
    return plot_data.dropna(subset=["Frame", output_column]), output_column


def _normalize_series_to_first_value(plot_data, x_column="GameObjects", y_column="AverageFPS"):
    normalized = plot_data[[x_column, y_column]].copy()
    normalized[x_column] = pd.to_numeric(normalized[x_column], errors="coerce")
    normalized[y_column] = pd.to_numeric(normalized[y_column], errors="coerce")
    normalized = normalized.dropna(subset=[x_column, y_column]).sort_values(x_column).reset_index(drop=True)

    if normalized.empty:
        return normalized

    first_value = normalized[x_column].iloc[0]
    normalized[x_column] = normalized[x_column] - first_value
    return normalized


def _fps_per_gameobject_series(data, events):
    plot_data = _fps_series_from_stats(data)

    if not {"Frame", "Event", "Value"}.issubset(events.columns):
        raise ValueError("Missing event columns needed for GameObject comparison")

    finished_rows = events.loc[
        events["Event"] == "FinishedInstantiation", ["Frame", "Value"]
    ].copy()
    finished_rows["Frame"] = pd.to_numeric(finished_rows["Frame"], errors="coerce")
    finished_rows["Value"] = pd.to_numeric(finished_rows["Value"], errors="coerce")
    finished_rows = finished_rows.dropna().sort_values("Frame").reset_index(drop=True)

    segment_points = []
    if not finished_rows.empty:
        first_frame = finished_rows.iloc[0]["Frame"]
        initial_segment = plot_data.loc[plot_data["Frame"] <= first_frame, "FPS"]
        if not initial_segment.empty:
            segment_points.append((0, initial_segment.iloc[-1]))

    previous_frame = None
    for _, row in finished_rows.iterrows():
        current_frame = row["Frame"]
        current_value = row["Value"]
        if previous_frame is None:
            segment = plot_data.loc[plot_data["Frame"] <= current_frame, "FPS"]
        else:
            segment = plot_data.loc[
                (plot_data["Frame"] > previous_frame) & (plot_data["Frame"] <= current_frame),
                "FPS",
            ]

        if not segment.empty:
            segment_points.append((current_value, segment.mean()))
        previous_frame = current_frame

    if not segment_points:
        raise ValueError("No FinishedInstantiation segments found for GameObject comparison")

    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", "AverageFPS"])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data["AverageFPS"] = pd.to_numeric(segment_data["AverageFPS"], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", "AverageFPS"])


def _quest_fps_per_gameobject_series(data, events):
    quest_data = pd.DataFrame(
        {
            "Frame": pd.to_numeric(data.get("Time Stamp"), errors="coerce"),
            "FPS": pd.to_numeric(data.get("average_frame_rate"), errors="coerce"),
        }
    ).dropna(subset=["Frame", "FPS"])

    quest_events = events.copy()
    if "Time" in quest_events.columns:
        quest_events["Frame"] = pd.to_numeric(quest_events["Time"], errors="coerce") * 1000.0

    return _fps_per_gameobject_series(quest_data, quest_events)


def _memory_mb_series_from_stats(data):
    frame = _frame_series(data)

    if "Total Used Memory (bytes)" in data.columns:
        memory_mb = pd.to_numeric(data["Total Used Memory (bytes)"], errors="coerce") / (1024.0 * 1024.0)
    elif "app_rss_MB" in data.columns:
        memory_mb = pd.to_numeric(data["app_rss_MB"], errors="coerce")
    elif "app_pss_MB" in data.columns:
        memory_mb = pd.to_numeric(data["app_pss_MB"], errors="coerce")
    elif "app_uss_MB" in data.columns:
        memory_mb = pd.to_numeric(data["app_uss_MB"], errors="coerce")
    else:
        raise ValueError("Missing memory columns for memory comparison")

    plot_data = pd.DataFrame({"Frame": frame, "MemoryMB": memory_mb})
    return plot_data.dropna(subset=["Frame", "MemoryMB"])


def _memory_per_gameobject_series(data, events):
    memory_data = _memory_mb_series_from_stats(data)

    if not {"Frame", "Event", "Value"}.issubset(events.columns):
        raise ValueError("Missing event columns needed for GameObject comparison")

    finished_rows = events.loc[
        events["Event"] == "FinishedInstantiation", ["Frame", "Value"]
    ].copy()
    finished_rows["Frame"] = pd.to_numeric(finished_rows["Frame"], errors="coerce")
    finished_rows["Value"] = pd.to_numeric(finished_rows["Value"], errors="coerce")
    finished_rows = finished_rows.dropna().sort_values("Frame").reset_index(drop=True)

    segment_points = []
    if not finished_rows.empty:
        first_frame = finished_rows.iloc[0]["Frame"]
        initial_segment = memory_data.loc[memory_data["Frame"] <= first_frame, "MemoryMB"]
        if not initial_segment.empty:
            segment_points.append((0, initial_segment.iloc[-1]))

    previous_frame = None
    for _, row in finished_rows.iterrows():
        current_frame = row["Frame"]
        current_value = row["Value"]
        if previous_frame is None:
            segment = memory_data.loc[memory_data["Frame"] <= current_frame, "MemoryMB"]
        else:
            segment = memory_data.loc[
                (memory_data["Frame"] > previous_frame) & (memory_data["Frame"] <= current_frame),
                "MemoryMB",
            ]

        if not segment.empty:
            segment_points.append((current_value, segment.mean()))
        previous_frame = current_frame

    if not segment_points:
        raise ValueError("No FinishedInstantiation segments found for memory comparison")

    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", "AverageMemoryMB"])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data["AverageMemoryMB"] = pd.to_numeric(segment_data["AverageMemoryMB"], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", "AverageMemoryMB"]).reset_index(drop=True)


def _metric_per_gameobject_series(data, events, metric_key):
    metric_data, metric_column = _metric_series_from_stats(data, metric_key)

    if not {"Frame", "Event", "Value"}.issubset(events.columns):
        raise ValueError("Missing event columns needed for GameObject comparison")

    finished_rows = events.loc[
        events["Event"] == "FinishedInstantiation", ["Frame", "Value"]
    ].copy()
    finished_rows["Frame"] = pd.to_numeric(finished_rows["Frame"], errors="coerce")
    finished_rows["Value"] = pd.to_numeric(finished_rows["Value"], errors="coerce")
    finished_rows = finished_rows.dropna().sort_values("Frame").reset_index(drop=True)

    segment_points = []
    previous_frame = None
    for _, row in finished_rows.iterrows():
        current_frame = row["Frame"]
        current_value = row["Value"]
        if previous_frame is None:
            segment = metric_data.loc[metric_data["Frame"] <= current_frame, metric_column]
        else:
            segment = metric_data.loc[
                (metric_data["Frame"] > previous_frame) & (metric_data["Frame"] <= current_frame),
                metric_column,
            ]

        if not segment.empty:
            segment_points.append((current_value, segment.mean()))
        previous_frame = current_frame

    if not segment_points:
        raise ValueError(f"No FinishedInstantiation segments found for {metric_key} comparison")

    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", metric_column])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data[metric_column] = pd.to_numeric(segment_data[metric_column], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", metric_column]), metric_column


def _comparison_label(stat_file):
    base_name = os.path.basename(stat_file)
    print(f"Determining label for file: {base_name}")
    # Check quest-specific patterns FIRST before generic BenchmarkBase
    if "com.IMT_Atlantique.base_DOTS" in base_name:
        return "dots_quest"
    if "com.IMT_Atlantique.base_GPU" in base_name:
        return "gpu_quest"
    if "com.IMT_Atlantique.BenchmarkBase" in base_name:
        return "base_quest"
    if "com.IMT_Atlantique.BenchmarkNGO" in base_name:
        return "ngo_quest"
    # Desktop patterns
    if base_name.startswith("dots_profiler_stats-"):
        return "dots"
    if base_name.startswith("gpu_profiler_stats-"):
        return "gpu"
    if base_name.startswith("profiler_stats-"):
        return "base"
    if base_name.startswith("ngo_client_profiler_stats-"):
        return "ngo"
    if base_name.startswith("ngo_server_profiler_stats-"):
        return "ngo_server"
    if base_name.startswith("photon_client_profiler_stats-"):
        return "photon_client"
    if base_name.startswith("photon_server_profiler_stats-"):
        return "photon_server"
    return os.path.splitext(base_name)[0]


FPS_COMPARISON_GROUPS = [
    (
        "everything",
        "FPS comparison across systems per GameObject pool",
        {
            "base",
            "dots",
            "gpu",
            "base_quest",
            "dots_quest",
            "gpu_quest",
            "ngo",
            "ngo_server",
            "photon_client",
            "photon_server",
        },
    ),
    (
        "base_dots_gpu",
        "FPS comparison: base, dots, gpu",
        {"base", "dots", "gpu"},
    ),
    (
        "ngo_photon_all",
        "FPS comparison: ngo and photon systems",
        {"ngo", "ngo_server", "photon_client", "photon_server"},
    ),
    (
        "ngo_photon_client",
        "FPS comparison: ngo and photon_client",
        {"ngo", "photon_client"},
    ),
    (
        "ngo_server_photon_server",
        "FPS comparison: ngo_server and photon_server",
        {"ngo_server", "photon_server"},
    ),
]


def plot_fps_comparison(couple_of_files, debug=False, fig_size=FIGURE_SIZE, allowed_labels=None, title=None):
    fig = plt.figure(figsize=fig_size)
    manager = plt.get_current_fig_manager()
    try:
        manager.window.state("zoomed")
    except Exception:
        try:
            manager.full_screen_toggle()
        except Exception:
            pass

    ax = fig.add_subplot(111)
    styles = {
        "base": {"color": "#1f77b4", "marker": "o", "linestyle": "-"},
        "dots": {"color": "#2ca02c", "marker": "s", "linestyle": "-"},
        "gpu": {"color": "#d62728", "marker": "^", "linestyle": "-"},
        "base_quest": {"color": "#1f77b4", "marker": "o", "linestyle": "--"},
        "dots_quest": {"color": "#2ca02c", "marker": "s", "linestyle": "--"},
        "gpu_quest": {"color": "#d62728", "marker": "^", "linestyle": "--"},
        "ngo": {"color": "#9467bd", "marker": "D"},
        "ngo_server": {"color": "#ff7f0e", "marker": "v"},
        "photon_client": {"color": "#8c564b", "marker": "P"},
        "photon_server": {"color": "#17becf", "marker": "X"},
    }

    if allowed_labels is None:
        allowed_labels = {
            "base",
            "dots",
            "gpu",
            "base_quest",
            "dots_quest",
            "gpu_quest",
            "ngo",
            "ngo_server",
            "photon_client",
            "photon_server",
        }

    plotted_labels = []
    for couple in couple_of_files:
        if couple.stat_file is None:
            continue

        label = _comparison_label(couple.stat_file)
        if label not in allowed_labels:
            continue

        data = pd.read_csv(couple.stat_file, low_memory=False)
        events = pd.read_csv(couple.event_file, low_memory=False)
        if label.endswith("_quest"):
            plot_data = _quest_fps_per_gameobject_series(data, events)
        else:
            plot_data = _fps_per_gameobject_series(data, events)

        plot_data = _normalize_series_to_first_value(plot_data)
        style = styles.get(label, {})
        markevery = max(len(plot_data) // 25, 1)

        ax.plot(
            plot_data["GameObjects"],
            plot_data["AverageFPS"],
            label=label,
            linewidth=2,
            markersize=4,
            markevery=markevery,
            **{k: v for k, v in style.items() if k != "linestyle"},
            linestyle=style.get("linestyle", "-"),
        )
        plotted_labels.append(label)

    if not plotted_labels:
        raise ValueError("No compatible FPS series found for comparison plot")

    ax.axhline(y=72, color="red", linestyle="--", linewidth=1.2, label="72 FPS limit")
    ax.set_xlabel("GameObjects")
    ax.set_ylabel("FPS")
    fig.suptitle(title or "FPS comparison across systems per GameObject pool")
    ax.ticklabel_format(style='plain', axis='x')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)

    if debug:
        plt.show()
    return fig


def plot_memory_comparison(couple_of_files, debug=False, fig_size=FIGURE_SIZE):
    fig = plt.figure(figsize=fig_size)
    manager = plt.get_current_fig_manager()
    try:
        manager.window.state("zoomed")
    except Exception:
        try:
            manager.full_screen_toggle()
        except Exception:
            pass

    ax = fig.add_subplot(111)
    styles = {
        "base": {"color": "#1f77b4", "marker": "o", "linestyle": "-"},
        "dots": {"color": "#2ca02c", "marker": "s", "linestyle": "-"},
        "gpu": {"color": "#d62728", "marker": "^", "linestyle": "-"},
        "base_quest": {"color": "#1f77b4", "marker": "o", "linestyle": "--"},
        "dots_quest": {"color": "#2ca02c", "marker": "s", "linestyle": "--"},
        "gpu_quest": {"color": "#d62728", "marker": "^", "linestyle": "--"},
        "ngo": {"color": "#9467bd", "marker": "D", "linestyle": "-"},
        "ngo_quest": {"color": "#9467bd", "marker": "D", "linestyle": "--"},
        "ngo_server": {"color": "#ff7f0e", "marker": "v", "linestyle": "-"},
    }

    plotted_labels = []
    supported_labels = {
        "base",
        "dots",
        "gpu",
        "base_quest",
        "dots_quest",
        "gpu_quest",
        "ngo",
        "ngo_quest",
        "ngo_server",
    }
    for couple in couple_of_files:
        if couple.stat_file is None:
            continue

        label = _comparison_label(couple.stat_file)
        if label not in supported_labels:
            continue

        try:
            data = pd.read_csv(couple.stat_file, low_memory=False)
            plot_data = _memory_mb_series_from_stats(data)
            plot_data = plot_data.sort_values("Frame").reset_index(drop=True)
            if plot_data.empty:
                continue

            first_frame = plot_data["Frame"].iloc[0]
            plot_data["RelativeFrame"] = plot_data["Frame"] - first_frame
            style = styles.get(label, {})
            markevery = max(len(plot_data) // 200, 1)

            ax.plot(
                plot_data["RelativeFrame"],
                plot_data["MemoryMB"],
                label=label,
                linewidth=1.8,
                **{k: v for k, v in style.items() if k != "linestyle"},
                linestyle=style.get("linestyle", "-"),
            )
            plotted_labels.append(label)
        except Exception as e:
            print(f"Skipping memory comparison for {label}: {e}")

    if not plotted_labels:
        raise ValueError("No compatible memory series found for comparison plot")

    ax.set_xlabel("Frame offset from first sample")
    ax.set_ylabel("Memory Used (MB)")
    fig.suptitle("Memory used comparison across systems per frame")
    ax.ticklabel_format(style='plain', axis='x')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:,.0f}'))
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)

    if debug:
        plt.show()
    return fig


def plot_metric_comparison(couple_of_files, metric_key, debug=False, fig_size=FIGURE_SIZE):
    fig = plt.figure(figsize=fig_size)
    manager = plt.get_current_fig_manager()
    try:
        manager.window.state("zoomed")
    except Exception:
        try:
            manager.full_screen_toggle()
        except Exception:
            pass

    ax = fig.add_subplot(111)
    styles = {
        "base": {"color": "#1f77b4", "marker": "o"},
        "dots": {"color": "#2ca02c", "marker": "s"},
        "gpu": {"color": "#d62728", "marker": "^"},
        "ngo": {"color": "#9467bd", "marker": "D"},
        "ngo_server": {"color": "#ff7f0e", "marker": "v"},
    }

    plotted_labels = []
    y_label = None
    for couple in couple_of_files:
        if couple.stat_file is None:
            continue

        label = _comparison_label(couple.stat_file)
        if label not in {"base", "dots", "gpu"}:
            continue

        data = pd.read_csv(couple.stat_file, low_memory=False)
        events = pd.read_csv(couple.event_file, low_memory=False)
        plot_data, metric_column = _metric_per_gameobject_series(data, events, metric_key)
        y_label = metric_column
        style = styles.get(label, {})
        markevery = max(len(plot_data) // 25, 1)

        ax.plot(
            plot_data["GameObjects"],
            plot_data[metric_column],
            label=label,
            linewidth=2,
            markersize=4,
            markevery=markevery,
            **style,
        )
        plotted_labels.append(label)

    if not plotted_labels:
        raise ValueError(f"No compatible {metric_key} series found for comparison plot")

    metric_title = metric_key.upper()
    ax.set_xlabel("GameObjects")
    ax.set_ylabel(y_label if y_label is not None else metric_title)
    if metric_key in ("cpu", "gpu"):
        # 1000 ms / 72 FPS ≈ 13.89 ms — the frame-time budget required to
        # sustain a 72 FPS refresh rate (Quest 3 / Pico 4 default).
        ax.axhline(y=14, color="red", linestyle="--", linewidth=1.2, label="14 ms (~72 FPS budget)")
    fig.suptitle(f"{metric_title} comparison across systems per GameObject pool")
    ax.ticklabel_format(style='plain', axis='x')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)

    if debug:
        plt.show()
    return fig

def plot(couple_of_files, debug=False) -> FigsAndName:
    figs = FigsAndName()
    base_name = os.path.basename(couple_of_files.stat_file).split("_")[0]
    print(f"Base name: {base_name}")
    if base_name.startswith("com.IMT"):
        if "BenchmarkBase" in couple_of_files.stat_file:
            print("Identified as base benchmark")
            base_name = "profiler"
        elif "BenchmarkNGO" in couple_of_files.stat_file:
            print("Identified as NGO benchmark")
            base_name = "ngo_client"
    if base_name == "profiler":
        figs.name = "base"
        if "com.IMT_Atlantique.Benchmark" in couple_of_files.stat_file:
            figs.name = "base_quest"
    else:
        print(f"Using base name for labeling: {couple_of_files.stat_file}")
        if "com.IMT_Atlantique.Benchmark" in couple_of_files.stat_file:
            figs.name = base_name + "_quest"
        elif "com.IMT_Atlantique.base_DOTS" in couple_of_files.stat_file:
            figs.name = "dots_quest"
        elif "com.IMT_Atlantique.base_GPU" in couple_of_files.stat_file:
            figs.name = "gpu_quest"
        else :
            figs.name = base_name + "_" + os.path.basename(couple_of_files.stat_file).split("_")[1]
    # parse events
    try:
        events = pd.read_csv(couple_of_files.event_file)
    except pd.errors.EmptyDataError:
        print(f"Event file is empty or malformed: {couple_of_files.event_file}")
        events = pd.DataFrame(columns=["Frame", "Event", "Value"])
    # parse stats
    if "com.IMT" not in couple_of_files.stat_file:
        data = pd.read_csv(couple_of_files.stat_file)
        # plot stats
        figs.figs.append(fpsplot.plot(data, events, debug, FIGURE_SIZE))
        figs.figs.append(threadplot.plot(data, events, debug, THREAD_CLAMP_MAX_MS, FIGURE_SIZE))
        figs.figs.append(memoryplot.plot(data, events, debug, FIGURE_SIZE))
        figs.figs.append(fpsPerGameObjectplot.plot(data, events, debug, FIGURE_SIZE))
        if "Object Spawned Bytes Received (bytes)" in data.columns:
            figs.figs.append(networkdataplot.plot(data, events, debug, FIGURE_SIZE))
            figs.figs.append(rpcplot.plot(data, events, debug, FIGURE_SIZE))
            figs.figs.append(threadplot.plot(data, events, debug, THREAD_CLAMP_MAX_MS, FIGURE_SIZE))
            figs.figs.append(pingplot.plot(data, events, debug, FIGURE_SIZE))
        else:
            print("No network data found, skipping network plots.")
        return figs
    else :
        data = pd.read_csv(couple_of_files.stat_file)
        # Quest plots use Time Stamp (ms) as x-axis; align event markers to that same time base.
        quest_events = events.copy()
        if "Time" in quest_events.columns:
            quest_events["Frame"] = pd.to_numeric(quest_events["Time"], errors="coerce") * 1000.0
        figs.figs.append(fpsplot.plot_quest(data, quest_events, debug, FIGURE_SIZE))
        figs.figs.append(threadplot.plot_quest(data, quest_events, debug, THREAD_CLAMP_MAX_MS, FIGURE_SIZE))
        figs.figs.append(memoryplot.plot_quest(data, quest_events, debug, FIGURE_SIZE))
        figs.figs.append(fpsPerGameObjectplot.plot_quest(data, quest_events, debug, FIGURE_SIZE))
        return figs

def save_figs(figs_and_name, folder_path):
    print(len(figs_and_name.figs))
    for fig in figs_and_name.figs:
        fig.savefig(f"{folder_path}/{figs_and_name.name}_{fig.get_suptitle().replace(' ', '_')}.png", dpi=SAVE_DPI)
        plt.close(fig)


def _resolve_data_folder(data_folder):
    if data_folder is None:
        data_folder = "./data"

    if not os.path.isdir(data_folder):
        raise FileNotFoundError(f"Data folder does not exist: {data_folder}")

    direct_files = [name for name in os.listdir(data_folder) if os.path.isfile(os.path.join(data_folder, name))]
    if direct_files:
        return data_folder

    latest_folder = assemble.get_latest_folder(data_folder)
    if latest_folder is None:
        raise FileNotFoundError(f"No data files or subfolders found in: {data_folder}")
    return latest_folder

def main():
    parser = argparse.ArgumentParser(description="Generate benchmark plots")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show interactive plot windows instead of saving files",
    )
    parser.add_argument(
        "--compare-fps",
        action="store_true",
        help="Add one FPS comparison graph that overlays base, dots, gpu, and related systems",
    )
    parser.add_argument(
        "--compare-cpu-gpu",
        action="store_true",
        help="Add CPU and GPU comparison graphs that overlay base, dots, and gpu per GameObject",
    )
    parser.add_argument(
        "--compare-memory",
        action="store_true",
        help="Add one memory comparison graph that overlays all compatible systems per GameObject",
    )
    parser.add_argument(
        "--data-folder",
        default="./data",
        help="Folder containing benchmark data, or a folder with dated subfolders to pick the latest from",
    )
    args = parser.parse_args()

    latest_folder = _resolve_data_folder(args.data_folder)
    files = assemble.get_files_from_folder(latest_folder)
    path = "./results"
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    folder_path = f"{path}/{timestamp}"
    os.makedirs(folder_path, exist_ok=True)

    for couple_of_files in files:
        print(couple_of_files)
        figs_and_name = plot(couple_of_files, args.debug)
        if not args.debug:
            # Create a subfolder for this couple
            couple_folder = os.path.join(folder_path, figs_and_name.name)
            os.makedirs(couple_folder, exist_ok=True)
            save_figs(figs_and_name, couple_folder)

    if args.compare_fps:
        for comparison_name, comparison_title, allowed_labels in FPS_COMPARISON_GROUPS:
            comparison_fig = plot_fps_comparison(
                files,
                args.debug,
                FIGURE_SIZE,
                allowed_labels=allowed_labels,
                title=comparison_title,
            )
            if not args.debug:
                comparison_fig.savefig(
                    f"{folder_path}/fps_comparison_{comparison_name}.png",
                    dpi=SAVE_DPI,
                )
                plt.close(comparison_fig)

    if args.compare_cpu_gpu:
        cpu_fig = plot_metric_comparison(files, "cpu", args.debug, FIGURE_SIZE)
        gpu_fig = plot_metric_comparison(files, "gpu", args.debug, FIGURE_SIZE)
        if not args.debug:
            cpu_fig.savefig(
                f"{folder_path}/cpu_comparison_CPU_comparison_across_systems_per_GameObject.png",
                dpi=SAVE_DPI,
            )
            gpu_fig.savefig(
                f"{folder_path}/gpu_comparison_GPU_comparison_across_systems_per_GameObject.png",
                dpi=SAVE_DPI,
            )
            plt.close(cpu_fig)
            plt.close(gpu_fig)

    if args.compare_memory:
        memory_fig = plot_memory_comparison(files, args.debug, FIGURE_SIZE)
        if not args.debug:
            memory_fig.savefig(
                f"{folder_path}/memory_comparison_Memory_used_comparison_across_systems_per_GameObject.png",
                dpi=SAVE_DPI,
            )
            plt.close(memory_fig)

if __name__ == "__main__":
    main()