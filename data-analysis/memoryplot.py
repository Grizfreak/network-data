import matplotlib.pyplot as plt
import pandas as pd

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
    memory_mb = data["Total Used Memory (bytes)"] / (1024 * 1024)
    ax.plot(data["Frame"], memory_mb, label="Total Used Memory (MB)")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Total Used Memory (MB)")
    fig.suptitle("Total Used Memory over Frames (MB)")
    ax.ticklabel_format(style='plain', axis='x')
    ax.ticklabel_format(style='plain', axis='y', useOffset=False)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:,.0f}'))

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

            if event_name == "FinishedInstantiation" and "Value" in events.columns:
                finished_rows = events.loc[events["Event"] == event_name, ["Frame", "Value"]].dropna()
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