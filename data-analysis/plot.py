import assemble
import matplotlib.pyplot as plt
import pandas as pd
import os
import argparse
import fpsplot
import threadplot
import memoryplot

THREAD_CLAMP_MAX_MS = 200
SAVE_DPI = 600
FIGURE_SIZE = (24, 8)

def plot(couple_of_files, debug=False) -> list[plt.Figure]:
    figs = []
    # parse events
    data = pd.read_csv(couple_of_files.event_file)
    # parse stats
    stats = pd.read_csv(couple_of_files.stat_file)
    # plot stats
    figs.append(fpsplot.plot(stats, data, debug, FIGURE_SIZE))
    figs.append(threadplot.plot(stats, data, debug, THREAD_CLAMP_MAX_MS, FIGURE_SIZE))
    figs.append(memoryplot.plot(stats, data, debug, FIGURE_SIZE))
    return figs

def save_plots(figures):
    path = "./results"
    # create a folder with current timestamp
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    folder_path = f"{path}/{timestamp}"
    os.makedirs(folder_path, exist_ok=True)
    for idx, fig in enumerate(figures):
        fig_path = f"{folder_path}/plot_{idx}.png"
        fig.savefig(fig_path, dpi=SAVE_DPI)
        print(f"Saved plot to {fig_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate benchmark plots")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show interactive plot windows instead of saving files",
    )
    args = parser.parse_args()

    latest_folder = assemble.get_latest_folder("./data")
    files = assemble.get_files_from_folder(latest_folder)
    figures = []
    for couple_of_files in files:
        print(couple_of_files)
        figures.extend(plot(couple_of_files, args.debug))
    if not args.debug:
        save_plots(figures)

if __name__ == "__main__":
    main()