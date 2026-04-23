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
    if base_name.startswith("dots_profiler_stats-"):
        return "dots"
    if base_name.startswith("gpu_profiler_stats-"):
        return "gpu"
    if base_name.startswith("profiler_stats-") or "BenchmarkBase" in base_name:
        return "base"
    if base_name.startswith("ngo_client_profiler_stats-") or "BenchmarkNGO" in base_name:
        return "ngo"
    if base_name.startswith("ngo_server_profiler_stats-"):
        return "ngo_server"
    return os.path.splitext(base_name)[0]


def plot_fps_comparison(couple_of_files, debug=False, fig_size=FIGURE_SIZE):
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
    for couple in couple_of_files:
        if couple.stat_file is None:
            continue

        label = _comparison_label(couple.stat_file)
        if label not in {"base", "dots", "gpu"}:
            continue

        data = pd.read_csv(couple.stat_file, low_memory=False)
        events = pd.read_csv(couple.event_file, low_memory=False)
        plot_data = _fps_per_gameobject_series(data, events)
        style = styles.get(label, {})
        markevery = max(len(plot_data) // 25, 1)

        ax.plot(
            plot_data["GameObjects"],
            plot_data["AverageFPS"],
            label=label,
            linewidth=2,
            markersize=4,
            markevery=markevery,
            **style,
        )
        plotted_labels.append(label)

    if not plotted_labels:
        raise ValueError("No compatible FPS series found for comparison plot")

    ax.set_xlabel("GameObjects")
    ax.set_ylabel("FPS")
    fig.suptitle("FPS comparison across systems per GameObject")
    ax.ticklabel_format(style='plain', axis='x')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
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
    fig.suptitle(f"{metric_title} comparison across systems per GameObject")
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
        if "com.IMT_Atlantique.Benchmark" in couple_of_files.stat_file:
            figs.name = base_name + "_quest"
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
    args = parser.parse_args()

    latest_folder = assemble.get_latest_folder("./data")
    files = assemble.get_files_from_folder(latest_folder)
    path = "./results"
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    folder_path = f"{path}/{timestamp}"
    os.makedirs(folder_path, exist_ok=True)

    for couple_of_files in files:
        print(couple_of_files)
        figs_and_name = plot(couple_of_files, args.debug)
        if not args.debug:
            save_figs(figs_and_name, folder_path)

    if args.compare_fps:
        comparison_fig = plot_fps_comparison(files, args.debug, FIGURE_SIZE)
        if not args.debug:
            comparison_fig.savefig(
                f"{folder_path}/fps_comparison_FPS_comparison_across_systems.png",
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

if __name__ == "__main__":
    main()