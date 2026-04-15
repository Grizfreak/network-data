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
    events = pd.read_csv(couple_of_files.event_file)
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

if __name__ == "__main__":
    main()