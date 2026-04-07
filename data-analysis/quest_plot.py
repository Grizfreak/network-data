import csv
import glob
import os
import pandas as pd
from pathlib import Path
from enum import Enum

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import numpy as np


NS_PER_MS = 1_000_000.0
MS_PER_S = 1000.0

DEBUG_SHOW_PLOTS = False

class EventType(str, Enum):
    PHASE_FINISHED = "PhaseFinished"
    FINISHED_INSTANTIATION = "FinishedInstantiation"
    STARTED_INSTANTIATION = "StartedInstantiation"
    STARTED_MOVING_LOCALLY = "StartedMovingLocally"
    ENDED_MOVING_LOCALLY = "EndedMovingLocally"


# Disable specific events globally by adding EventType entries here.
DISABLED_EVENTS = {
    EventType.STARTED_MOVING_LOCALLY,
    EventType.ENDED_MOVING_LOCALLY,
    EventType.STARTED_INSTANTIATION,
    EventType.FINISHED_INSTANTIATION,
}


# Event type to color mapping
EVENT_COLORS = {
    EventType.PHASE_FINISHED.value: "#dc3545",  # Red
    EventType.FINISHED_INSTANTIATION.value: "#28a745",  # Green
    EventType.STARTED_INSTANTIATION.value: "#ffc107",  # Amber
    EventType.STARTED_MOVING_LOCALLY.value: "#17a2b8",  # Cyan
    EventType.ENDED_MOVING_LOCALLY.value: "#6f42c1",  # Purple
}


def get_disabled_event_names():
    return {event_type.value for event_type in DISABLED_EVENTS}


def get_active_event_colors(events):
    present_events = {event['event'] for event in events if event['event'] in EVENT_COLORS}
    return {
        event_name: color
        for event_name, color in EVENT_COLORS.items()
        if event_name in present_events
    }

def load_events(events_file):
    events = []
    if not events_file:
        return events
    with open(events_file, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                value = float(row.get('Value', 'nan'))
            except (TypeError, ValueError):
                value = np.nan
            events.append({
                'frame': int(row['Frame']),
                'event': row['Event'],
                'value': value,
            })
    return events

def get_last_files():
    # get folder results
    results_folder = Path('results')
    if not results_folder.exists():
        print("No results folder found.")
        return None, None
    profiler_file = None
    events_file = None
    # Find the latest events_*.csv or profiler_stats*.csv file
    for file in results_folder.glob("quest_events_*.csv"):
        if not events_file or file.stat().st_mtime > events_file.stat().st_mtime:
            events_file = file
    for file in results_folder.glob("com.*.csv"):
        if not profiler_file or file.stat().st_mtime > profiler_file.stat().st_mtime:
            profiler_file = file
    print(f"Latest profiler file: {profiler_file}")
    print(f"Latest events file: {events_file}")
    return profiler_file, events_file

def load_data(profiler_file):
    if not profiler_file:
        print("No profiler file found.")
        return None
    data = pd.read_csv(profiler_file)
    return data

def plot_performance(data, events, output_file='quest_perf_plot.png'):
    if data is None or data.empty:
        print("No data to plot.")
        return

    # Convert Time Stamp (ms) from profiler to Seconds
    data['Time_s'] = data['Time Stamp'] / 1000.0

    # Create a figure with 3 subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    axs = [ax1, ax2, ax3]

    # Get active colors for legend
    active_event_colors = get_active_event_colors(events)

    # Plot 1: FPS
    ax1.plot(data['Time_s'], data['average_frame_rate'], color='#007bff', label='FPS')
    ax1.set_ylabel('FPS')
    ax1.set_title('Performance Metrics with Event Markers', fontsize=14)

    # Plot 2: CPU Utilization
    ax2.plot(data['Time_s'], data['cpu_utilization_percentage'], color='#dc3545', label='CPU Usage (%)')
    ax2.set_ylabel('CPU %')
    ax2.set_ylim(0, 105)

    # Plot 3: GPU Utilization
    ax3.plot(data['Time_s'], data['gpu_utilization_percentage'], color='#28a745', label='GPU Usage (%)')
    ax3.set_ylabel('GPU %')
    ax3.set_xlabel('Time (seconds)')
    ax3.set_ylim(0, 105)

    # --- ADD EVENTS HERE ---
    # We loop through each event and draw a line on every subplot
    for event in events:
        event_name = event['event']
        if event_name in active_event_colors:
            # Your events file uses the 'Time' column (seconds)
            # If the CSV key is 'time', ensure load_events captures it correctly
            # Based on your snippet, I'll use event.get('time') or calculate it
            event_time = event.get('value') if event_name == "PhaseFinished" else None 
            
            # Since your load_events might need adjustment to read the 'Time' column:
            # Let's assume you've updated load_events to include 'time'
            t = event.get('time') 
            
            if t is not None:
                for ax in axs:
                    ax.axvline(x=t, color=active_event_colors[event_name], 
                               linestyle='--', alpha=0.5, linewidth=1)

    # Add Grid and Legend to all
    for ax in axs:
        ax.grid(True, linestyle=':', alpha=0.6)
        
    # Create custom legend for events
    legend_elements = [
        Line2D([0], [0], color=color, linestyle='--', label=name)
        for name, color in active_event_colors.items()
    ]
    
    # Place legend on the top plot
    ax1.legend(handles=[ax1.lines[0]] + legend_elements, 
               loc='upper left', bbox_to_anchor=(1.01, 1.0))

    plt.tight_layout()
    if DEBUG_SHOW_PLOTS:
        plt.show()
    return fig

def save_plots(plts):
    # folder is plot_output
    output_folder = Path('plot_output')
    output_folder.mkdir(exist_ok=True)
    for i, plt in enumerate(plts):
        plt.savefig(output_folder / f'quest_plot_{i}.png', dpi=300, bbox_inches='tight')

if __name__ == "__main__":
    profiler_file, events_file = get_last_files()
    data = load_data(profiler_file)
    events = load_events(events_file)

    if data is not None:
        print(data.head())
    else:
        print("No profiler data loaded.")

    if events:
        print(f"Loaded {len(events)} events.")
    else:
        print("No events loaded.")

    plts = []
    plts.append(plot_performance(data, events))
    save_plots(plts);
    
    