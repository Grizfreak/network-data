import matplotlib.pyplot as plt
import pandas as pd


def _format_bytes(value, _):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    unit_index = 0

    while abs(size) >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size):,} {units[unit_index]}"

    return f"{size:,.1f} {units[unit_index]}"

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
        "Total Bytes Received (bytes)",
        "Total Bytes Sent (bytes)",
        "Object Spawned Bytes Received (bytes)",
        "Object Spawned Bytes Sent (bytes)",
        "Rpc Bytes Received (bytes)",
        "Rpc Bytes Sent (bytes)"
    ]

    for metric in metrics:
        if metric in data.columns:
            ax.plot(data["Frame"], data[metric], label=metric)
    ax.set_xlabel("Frame")
    ax.set_ylabel("Data Size")
    ax.set_title("RPC and Object Spawn Events over Frames")
    ax.ticklabel_format(style='plain', axis='x')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_format_bytes))

    # Draw vertical lines for each event occurrence, grouped by event type.
    if {"Frame", "Event"}.issubset(events.columns):
        unique_events = events["Event"].dropna().unique()
        colors = plt.cm.tab20(range(len(unique_events)))
        y_min, y_max = ax.get_ylim()

        for idx, event_name in enumerate(unique_events):
            event_frames = events.loc[events["Event"] == event_name, "Frame"].dropna()
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

        if "Value" in events.columns:
            finished_rows = events.loc[
                events["Event"] == "FinishedInstantiation", ["Frame", "Value"]
            ].copy()
            finished_rows["Frame"] = pd.to_numeric(finished_rows["Frame"], errors="coerce")
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