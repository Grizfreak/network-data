import matplotlib.pyplot as plt
import pandas as pd
from xaxis_utils import event_frames_to_x, get_x_axis_info

def _maximize_figure(fig):
    manager = plt.get_current_fig_manager()
    try:
        manager.window.state("zoomed")
        return
    except Exception:
        pass

    try:
        manager.full_screen_toggle()
    except Exception:
        pass

def plot(data, events, debug=False, clamp_max_ms=None, fig_size=(24, 8)):
    fig = plt.figure(figsize=fig_size)
    _maximize_figure(fig)
    if debug:
        print("Plotting...")
    ax = fig.add_subplot(111)
    x_col, x_label, is_time_axis = get_x_axis_info(data)
    y_cols = [
        "FrameTimeMs",
        "Main Thread (ns)",
        "CPU Main Thread Frame Time (ns)",
        "CPU Render Thread Frame Time (ns)",
        "CPU Total Frame Time (ns)",
        "GPU Frame Time (ns)",
    ]
    ns_cols = [
        "Main Thread (ns)",
        "CPU Main Thread Frame Time (ns)",
        "CPU Render Thread Frame Time (ns)",
        "CPU Total Frame Time (ns)",
        "GPU Frame Time (ns)",
    ]

    missing_cols = [col for col in [x_col, *y_cols] if col not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in stats file: {', '.join(missing_cols)}")

    plot_data = data[[x_col, *y_cols]].apply(pd.to_numeric, errors="coerce").dropna(subset=[x_col])

    for col in ns_cols:
        plot_data[col] = plot_data[col] / 1_000_000

    if clamp_max_ms is not None:
        for col in y_cols:
            plot_data[col] = plot_data[col].clip(upper=clamp_max_ms)

    for col in y_cols:
        label = col.replace(" (ns)", " (ms)")
        ax.plot(plot_data[x_col], plot_data[col], label=label)

    ax.set_xlabel(x_label)
    ax.set_ylabel("Time (ms)")
    title = "Thread and GPU Frame Times over Time (ms)" if is_time_axis else "Thread and GPU Frame Times (ms)"
    if clamp_max_ms is not None:
        title += f" - Clamped at {clamp_max_ms} ms"

    fig.suptitle(title)
    ax.ticklabel_format(style='plain', axis='x', useOffset=False)
    ax.ticklabel_format(style='plain', axis='y', useOffset=False)
    if is_time_axis:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.1f}"))
    else:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:,.0f}"))

    # Draw vertical lines for each event occurrence, grouped by event type.
    if {"Frame", "Event"}.issubset(events.columns):
        event_data = events[["Frame", "Event"]].copy()
        event_data["Frame"] = event_frames_to_x(event_data["Frame"], data, x_col)
        event_data = event_data.dropna(subset=["Frame", "Event"])

        unique_events = event_data["Event"].dropna().unique()
        colors = plt.cm.tab20(range(len(unique_events)))
        y_min, y_max = ax.get_ylim()

        for idx, event_name in enumerate(unique_events):
            event_frames = event_data.loc[event_data["Event"] == event_name, "Frame"]
            if event_frames.empty:
                continue
            ax.vlines(
                event_frames,
                ymin=y_min,
                ymax=y_max,
                colors=[colors[idx]],
                alpha=0.25,
                linewidth=0.8,
                label=str(event_name),
            )

    fig.subplots_adjust(right=0.8)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    if debug:
        plt.show()
    return fig

def plot_quest(data, events, debug=False, clamp_max_ms=None, fig_size=(24, 8)):
    def numeric_col(col_name, default=0.0):
        if col_name not in data.columns:
            return pd.Series(default, index=data.index, dtype="float64")
        return pd.to_numeric(data[col_name], errors="coerce")

    fps = numeric_col("average_frame_rate")
    frame_time_ms = 1000.0 / fps.where(fps > 0)
    frame_time_ns = frame_time_ms * 1_000_000

    quest_data = pd.DataFrame(
        {
            "Frame": numeric_col("Time Stamp"),
            "FrameTimeMs": frame_time_ms,
            "Main Thread (ns)": frame_time_ns,
            "CPU Main Thread Frame Time (ns)": frame_time_ns,
            "CPU Render Thread Frame Time (ns)": numeric_col("timewarp_gpu_time_microseconds") * 1000.0,
            "CPU Total Frame Time (ns)": frame_time_ns,
            "GPU Frame Time (ns)": numeric_col("app_gpu_time_microseconds") * 1000.0,
        }
    )

    return plot(quest_data, events, debug, clamp_max_ms, fig_size)