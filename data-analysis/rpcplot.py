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
    metrics = [
        "Rpc Received",
        "Rpc Sent",
        "Object Spawned Received",
        "Object Spawned Sent",
    ]
    x_col, x_label, is_time_axis = get_x_axis_info(data)
    x_values = pd.to_numeric(data[x_col], errors="coerce")

    for metric in metrics:
        if metric in data.columns:
            metric_values = pd.to_numeric(data[metric], errors="coerce")
            metric_data = pd.DataFrame({"x": x_values, "y": metric_values}).dropna(subset=["x", "y"])
            ax.plot(metric_data["x"], metric_data["y"], label=metric)
    ax.set_xlabel(x_label)
    ax.set_ylabel("Count")
    fig.suptitle("RPC and Object Spawn Events over Time" if is_time_axis else "RPC and Object Spawn Events over Frames")
    ax.ticklabel_format(style='plain', axis='x')
    if is_time_axis:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.1f}"))
    else:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))

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

        if "Value" in events.columns:
            finished_rows = events.loc[
                events["Event"] == "FinishedInstantiation", ["Frame", "Value"]
            ].copy()
            finished_rows["Frame"] = event_frames_to_x(finished_rows["Frame"], data, x_col)
            finished_rows["Value"] = pd.to_numeric(finished_rows["Value"], errors="coerce")
            finished_rows = finished_rows.dropna().sort_values("Frame")

            # Restore the previous inline value labels on the event lines.
            for _, row in finished_rows.iterrows():
                ax.text(
                    row["Frame"],
                    y_max,
                    str(int(row["Value"])),
                    rotation=90,
                    va="bottom",
                    ha="center",
                    fontsize=7,
                    color="orange",
                )

            changed_rows = finished_rows.loc[
                finished_rows["Value"].ne(finished_rows["Value"].shift())
            ]

            if not changed_rows.empty:
                top_ax = ax.secondary_xaxis("top")
                top_ax.set_xlabel("FinishedInstantiation Value")
                top_ax.set_xticks(changed_rows["Frame"].tolist())
                top_ax.set_xticklabels([f"{int(v)}" for v in changed_rows["Value"]], rotation=45, ha="left")
                top_ax.tick_params(axis="x", labelsize=8, pad=2)

    fig.subplots_adjust(right=0.85)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    if debug:
        plt.show()
    return fig