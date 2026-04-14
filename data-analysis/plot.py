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
import threadplot
import pingplot

THREAD_CLAMP_MAX_MS = 200
SAVE_DPI = 600
FIGURE_SIZE = (24, 8)

class FigsAndName:
    def __init__(self):
        self.figs = []
        self.name = ""

def plot(couple_of_files, debug=False) -> FigsAndName:
    figs = FigsAndName()
    base_name = os.path.basename(couple_of_files.stat_file).split("_")[0]
    if base_name == "profiler":
        figs.name = "base"
    else:
        figs.name = base_name + "_" + os.path.basename(couple_of_files.stat_file).split("_")[1]
    # parse events
    events = pd.read_csv(couple_of_files.event_file)
    # parse stats
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

def save_plots(figures):
    print(len(figures))
    for figs_and_name in figures:
        print(len(figs_and_name.figs))
    path = "./results"
    # create a folder with current timestamp
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    folder_path = f"{path}/{timestamp}"
    os.makedirs(folder_path, exist_ok=True)
    for figs_and_name in figures:
        for idx, fig in enumerate(figs_and_name.figs):
            fig.savefig(f"{folder_path}/{figs_and_name.name}_{fig.get_suptitle().replace(' ', '_')}.png", dpi=SAVE_DPI)

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
    figures = list()
    for couple_of_files in files:
        print(couple_of_files)
        figures.append(plot(couple_of_files, args.debug))
    if not args.debug:
        save_plots(figures)

if __name__ == "__main__":
    main()