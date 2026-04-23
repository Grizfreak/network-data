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

def plot(data, events, debug=False, fig_size=(24, 8)):
    fig = plt.figure(figsize=fig_size)
    _maximize_figure(fig)
    if debug:
        print("Plotting...")
    # plot stats
    ax = fig.add_subplot(111)
    x_col, x_label, is_time_axis = get_x_axis_info(data)
    x_values = pd.to_numeric(data[x_col], errors="coerce")
    memory_mb = data["Total Used Memory (bytes)"] / (1024 * 1024)
    plot_data = pd.DataFrame({"x": x_values, "MemoryMB": pd.to_numeric(memory_mb, errors="coerce")})
    plot_data = plot_data.dropna(subset=["x", "MemoryMB"])
    ax.plot(plot_data["x"], plot_data["MemoryMB"], label="Total Used Memory (MB)")
    ax.set_xlabel(x_label)
    ax.set_ylabel("Total Used Memory (MB)")
    fig.suptitle("Total Used Memory over Time (MB)" if is_time_axis else "Total Used Memory over Frames (MB)")
    ax.ticklabel_format(style='plain', axis='x')
    ax.ticklabel_format(style='plain', axis='y', useOffset=False)
    if is_time_axis:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.1f}"))
    else:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:,.0f}'))

    # Draw vertical lines for each event occurrence, grouped by event type.
    if {"Frame", "Event"}.issubset(events.columns):
        unique_events = events["Event"].dropna().unique()
        colors = plt.cm.tab20(range(len(unique_events)))
        y_min, y_max = ax.get_ylim()

        for idx, event_name in enumerate(unique_events):
            event_frames = events.loc[events["Event"] == event_name, "Frame"]
            event_x = event_frames_to_x(event_frames, data, x_col)
            if event_x.empty:
                continue
            ax.vlines(
                event_x,
                ymin=y_min,
                ymax=y_max,
                colors=[colors[idx]],
                alpha=0.25,
                linewidth=0.8,
                label=str(event_name),
            )

            if event_name == "FinishedInstantiation" and "Value" in events.columns:
                finished_rows = events.loc[events["Event"] == event_name, ["Frame", "Value"]].dropna()
                finished_rows["Frame"] = event_frames_to_x(finished_rows["Frame"], data, x_col)
                for _, row in finished_rows.iterrows():
                    ax.text(
                        row["Frame"],
                        y_max,
                        str(int(row["Value"])),
                        rotation=90,
                        va="bottom",
                        ha="center",
                        fontsize=7,
                        color=colors[idx],
                    )

    fig.subplots_adjust(right=0.85)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    if debug:
        plt.show()
    return fig

def plot_quest(data, events, debug=False, fig_size=(24, 8)):
    def numeric_col(col_name, default=0.0):
        if col_name not in data.columns:
            return pd.Series(default, index=data.index, dtype="float64")
        return pd.to_numeric(data[col_name], errors="coerce")

    memory_mb = numeric_col("app_rss_MB")
    if memory_mb.isna().all():
        memory_mb = numeric_col("app_pss_MB")
    if memory_mb.isna().all():
        memory_mb = numeric_col("app_uss_MB")

    quest_data = pd.DataFrame(
        {
            "Frame": numeric_col("Time Stamp"),
            "Total Used Memory (bytes)": memory_mb * 1024.0 * 1024.0,
        }
    )

    return plot(quest_data, events, debug, fig_size)