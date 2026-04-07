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

DEBUG_SHOW_PLOTS = True

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
    for file in results_folder.glob("events_*.csv"):
        if not events_file or file.stat().st_mtime > events_file.stat().st_mtime:
            events_file = file
    for file in results_folder.glob("profiler_stats*.csv"):
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

def ema(signal, alpha=0.1):
    result = np.zeros_like(signal)
    result[0] = signal[0]
    for i in range(1, len(signal)):
        result[i] = alpha * signal[i] + (1 - alpha) * result[i - 1]
    return result


def moving_average(signal, window=30):
    kernel = np.ones(window) / window
    return np.convolve(signal, kernel, mode='same')

def plot_FPS_over_time(data, events):
    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    active_event_colors = get_active_event_colors(events)

    # Use the correct column from your CSV
    frame_time_ms = data['FrameTimeMs'].to_numpy()
    time_axis = np.cumsum(frame_time_ms) / 1000.0  # Seconds

    # Raw FPS Calculation
    # Avoid division by zero if there's a corrupted frame
    fps_raw = 1000.0 / np.where(frame_time_ms > 0, frame_time_ms, 1e-6)

    # 1. Better Smoothing: Use a larger alpha (0.05 to 0.1) or a rolling window
    # EMA with alpha 0.001 is too slow; 0.05 is much more responsive.
    frame_time_smooth = ema(frame_time_ms, alpha=0.05)
    fps_smooth = 1000.0 / frame_time_smooth

    # 2. Plotting
    ax.plot(time_axis, fps_raw, color='blue', alpha=0.15, linewidth=0.5, label='Raw FPS')
    ax.plot(time_axis, fps_smooth, color='blue', linewidth=2, label='Smoothed FPS (EMA 0.05)')
    
    # 3. Handle Spikes: Set a reasonable Y-limit based on data
    # This prevents one 500ms spike from squishing the whole graph to the bottom
    ax.set_ylim(0, max(fps_smooth.max() * 1.2, 120)) 

    ax.set_title('Performance: FPS over Time', fontsize=14)
    ax.set_ylabel('Frames Per Second')
    ax.set_xlabel('Time (s)')
    ax.grid(True, linestyle=':', alpha=0.7)

    # Event Markers
    frame_to_time = dict(zip(data['Frame'], time_axis))
    for event in events:
        if event['event'] in active_event_colors:
            event_time = frame_to_time.get(event['frame'])
            if event_time is not None:
                ax.axvline(x=event_time, color=active_event_colors[event['event']], 
                           linestyle='--', alpha=0.8)

    # Legend Fix (handles standard lines + custom event elements)
    legend_elements = [
        Line2D([0], [0], color=color, linestyle='--', label=event)
        for event, color in active_event_colors.items()
    ]
    ax.legend(handles=[ax.lines[1]] + legend_elements, loc='upper left', 
              bbox_to_anchor=(1.01, 1.0))

    fig.tight_layout()
    if DEBUG_SHOW_PLOTS:
        plt.show()
    return fig

def plot_FrameTimes_over_time(data, events):
    # take CPU frame time and GPU frame time
    fig, (ax) = plt.subplots(1, 1, figsize=(12, 6))
    active_event_colors = get_active_event_colors(events)
    cpu_main_thread_frame_time_ms = data['CPU Main Thread Frame Time (ns)'].to_numpy() / NS_PER_MS
    cpu_render_thread_frame_time_ms = data['CPU Render Thread Frame Time (ns)'].to_numpy() / NS_PER_MS
    cpu_frame_time_ms = data['CPU Total Frame Time (ns)'].to_numpy() / NS_PER_MS
    gpu_frame_time_ms = data['GPU Frame Time (ns)'].to_numpy() / NS_PER_MS
    cpu_frame_time_ms = np.clip(cpu_frame_time_ms, 0, 1300)  # Clip to 100ms for better visualization

    time_axis = np.cumsum(data['FrameTimeMs'].to_numpy() / 1000.0)
    # Define the columns we want to plot
    metrics = {
        'CPU Main Thread Frame Time (ns)': ('red', 'Main Thread'),
        'CPU Render Thread Frame Time (ns)': ('green', 'Render Thread'),
        'CPU Total Frame Time (ns)': ('blue', 'Total CPU'),
        'GPU Frame Time (ns)': ('orange', 'GPU')
    }

    # Window size for smoothing (e.g., average over 50 frames)
    window = 50 

    for col, (color, label) in metrics.items():
        # 1. Convert to ms
        raw_values = data[col].to_numpy() / 1000000.0 # NS_PER_MS
        series = pd.Series(raw_values)
        
        # 2. Calculate Median (The 'True' trend, ignores the 500ms spikes)
        median_smooth = series.rolling(window=window, center=True).median()
        
        # 3. Calculate 95th Percentile (The 'Jitter' or 'Worst Case')
        p95 = series.rolling(window=window, center=True).quantile(0.95)

        # Plot the Trend
        ax.plot(time_axis, median_smooth, color=color, linewidth=1.5, label=f'{label} (Median)')
        
        # Fill the area between median and p95 to show instability/noise
        ax.fill_between(time_axis, median_smooth, p95, color=color, alpha=0.1)

    ax.set_ylim(-5, 100) # Clipping the view so we can actually see the drift
    ax.set_title('Smoothed Frame Times (Median + 95th Percentile Shadow)')
    ax.set_ylabel('Frame Time (ms)')
    ax.set_xlabel('Time (s)')
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
        # Add event markers
    frame_to_time = dict(zip(data['Frame'], time_axis))
    for event in events:
        if event['event'] in active_event_colors:
            event_time = frame_to_time.get(event['frame'], None)
            if event_time is not None:
                ax.axvline(x=event_time, color=active_event_colors[event['event']], linestyle='--', alpha=0.7, label=event['event'])
    # Create legend for events
    legend_elements = [
    Line2D([0], [0],
           color=color,        # line color
           linestyle='--',      # makes it a line
           markersize=8,
           label=event)
        for event, color in active_event_colors.items()
    ]
    ax.legend(handles=[ax.lines[0], ax.lines[1], ax.lines[2], ax.lines[3]] + legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
    fig.tight_layout()
    if DEBUG_SHOW_PLOTS:
        plt.show()
    return fig;

def plot_FrameTimes_over_time_OnlyPhase1(data, events):
    # same as plot_FrameTimes_over_time but only for first phase (between first phase start and first phase end)
    fig, (ax) = plt.subplots(1, 1, figsize=(12, 6))
    active_event_colors = get_active_event_colors(events)
    time_axis = np.cumsum(data['FrameTimeMs'].to_numpy() / 1000.0)
    frame_to_time = dict(zip(data['Frame'], time_axis))
    
    # Define metrics to process
    metrics = {
        'CPU Main Thread Frame Time (ns)': ('red', 'Main'),
        'CPU Render Thread Frame Time (ns)': ('green', 'Render'),
        'CPU Total Frame Time (ns)': ('blue', 'Total CPU'),
        'GPU Frame Time (ns)': ('orange', 'GPU')
    }
    p_start, p_end = None, None
    for event in events:
        if event['event'] == "PhaseFinished":
            t = frame_to_time.get(event['frame'])
            if p_start is None: p_start = t
            elif p_end is None and t > p_start: p_end = t; break
    if p_start is not None and p_end is not None:
        mask = (time_axis >= p_start) & (time_axis <= p_end)
        t_masked = time_axis[mask]
        
        # 2. Plotting with Smoothing
        window = 100 # Adjust window size to your liking
        
        for col, (color, label) in metrics.items():
            # Convert to ms and mask
            vals = data[col].to_numpy()[mask] / 1e6 
            series = pd.Series(vals)
            
            # Calculate Trend (Median) and Jitter (90th percentile)
            median_val = series.rolling(window=window, center=True).median()
            p90_val = series.rolling(window=window, center=True).quantile(0.90)
            
            # Plot the clean trend line
            line, = ax.plot(t_masked, median_val, color=color, linewidth=1.5, label=f'{label} Median')
            # Plot a subtle shadow for the jitter
            ax.fill_between(t_masked, median_val, p90_val, color=color, alpha=0.15)

        # 3. CRITICAL: Set Y-Limit to see the actual drift
        # Even if spikes hit 500, we want to see the 0-60ms range clearly
        ax.set_ylim(-2, 60) 

        ax.set_title('Phase 1 Performance Drift (Median + 90th Percentile Shadow)')
        ax.set_ylabel('Frame Time (ms)')
        ax.set_xlabel('Time (s)')
        ax.grid(True, alpha=0.3)
        # Add event markers
        for event in events:
            if event['event'] in active_event_colors:
                event_time = frame_to_time.get(event['frame'], None)
                if event_time is not None and p_start <= event_time <= p_end:
                    ax.axvline(x=event_time, color=active_event_colors[event['event']], linestyle='--', alpha=0.7, label=event['event'])
        # Create legend for events
        legend_elements = [Line2D([0], [0], color=color, linestyle='--', markersize=8, label=event) for event, color in active_event_colors.items()]
        ax.legend(handles=[ax.lines[0], ax.lines[1], ax.lines[2], ax.lines[3]] + legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
        fig.tight_layout()
        if DEBUG_SHOW_PLOTS:
            plt.show()
        return fig;

def plot_memory_over_time(data, events):
    # Total Used Memory (bytes)
    fig, (ax) = plt.subplots(1, 1, figsize=(12, 6))
    active_event_colors = get_active_event_colors(events)
    memory_bytes = data['Total Used Memory (bytes)'].to_numpy() / (1024 * 1024)  # Convert to MB
    time_axis = np.cumsum(data['FrameTimeMs'].to_numpy() / 1000.0)
    frame_to_time = dict(zip(data['Frame'], time_axis))
    for event in events:
        if event['event'] in active_event_colors:
            event_time = frame_to_time.get(event['frame'], None)
            if event_time is not None:
                ax.axvline(x=event_time, color=active_event_colors[event['event']], linestyle='--', alpha=0.7, label=event['event'])
    ax.plot(time_axis, memory_bytes, color='purple', label='Total Used Memory (MB)')
    ax.set_title('Memory Usage over Time')
    ax.set_ylabel('Memory (MB)')
    ax.set_xlabel('Time (s)')
    ax.grid(True)
    # Create legend for events
    legend_elements = [Line2D([0], [0], color=color, linestyle='--', markersize=8, label=event) for event, color in active_event_colors.items()]
    ax.legend(handles=[ax.lines[0]] + legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
    fig.tight_layout()
    if DEBUG_SHOW_PLOTS:
        plt.show()
    return fig;

def save_plots(plts):
    # folder is plot_output
    output_folder = Path('plot_output')
    output_folder.mkdir(exist_ok=True)
    for i, plt in enumerate(plts):
        plt.savefig(output_folder / f'plot_{i}.png', dpi=300, bbox_inches='tight')

def plot_data_over_gameObjects(data, events, marker_events=None):
    # get the game objects number from events with event "FinishedInstantiation" and value is the number of game objects
    # plot the frameTime dependinf on the number of game objects
    fig, (ax) = plt.subplots(1, 1, figsize=(12, 6))
    if marker_events is None:
        marker_events = events
    active_event_colors = get_active_event_colors(marker_events)
    game_objects = []
    frame_times = []
    gpu_frame_times = []
    cpu_main_thread_frame_times = []
    cpu_render_thread_frame_times = []
    for event in events:
        if event['event'] == EventType.FINISHED_INSTANTIATION.value:
            frame_time = data.loc[data['Frame'] == event['frame'], 'CPU Total Frame Time (ns)'].values
            gpu_frame_time = data.loc[data['Frame'] == event['frame'], 'GPU Frame Time (ns)'].values
            cpu_main_thread_frame_time = data.loc[data['Frame'] == event['frame'], 'CPU Main Thread Frame Time (ns)'].values
            cpu_render_thread_frame_time = data.loc[data['Frame'] == event['frame'], 'CPU Render Thread Frame Time (ns)'].values
            if len(frame_time) > 0:
                game_objects.append(event['value'])
                frame_times.append(frame_time[0] / NS_PER_MS)  # Convert to ms
                gpu_frame_times.append(gpu_frame_time[0] / NS_PER_MS)
                cpu_main_thread_frame_times.append(cpu_main_thread_frame_time[0] / NS_PER_MS)
                cpu_render_thread_frame_times.append(cpu_render_thread_frame_time[0] / NS_PER_MS)
    ax.scatter(game_objects, frame_times, color='magenta', alpha=0.7)
    ax.scatter(game_objects, gpu_frame_times, color='orange', alpha=0.7)
    ax.scatter(game_objects, cpu_main_thread_frame_times, color='red', alpha=0.7)
    ax.scatter(game_objects, cpu_render_thread_frame_times, color='green', alpha=0.7)
    ax.set_title('CPU Total Frame Time vs Number of Game Objects')
    ax.set_xlabel('Number of Game Objects')
    ax.set_ylabel('CPU Total Frame Time (ms)')
    ax.grid(True)
    # add event markers
    for event in marker_events:
        if event['event'] in active_event_colors:
            ax.scatter(event['value'], 0, color=active_event_colors[event['event']], label=event['event'], marker='x', s=100)
    # Create legend for events
    legend_elements = [
    Line2D([0], [0],
           marker='x',
           linestyle='None',
           color=color,          # controls marker color
           markersize=8,
           label=event)
        for event, color in active_event_colors.items()
    ]
    # Create legend for scatter points
    legend_elements += [Line2D([0], [0], marker='o', linestyle='None', color='magenta', markersize=8, label='CPU Total Frame Time'),
                        Line2D([0], [0], marker='o', linestyle='None', color='orange', markersize=8, label='GPU Frame Time'),
                        Line2D([0], [0], marker='o', linestyle='None', color='red', markersize=8, label='CPU Main Thread Frame Time'),
                        Line2D([0], [0], marker='o', linestyle='None', color='green', markersize=8, label='CPU Render Thread Frame Time')]
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
    fig.tight_layout()
    if DEBUG_SHOW_PLOTS:
        plt.show()
    return fig;


if __name__ == "__main__":
    profiler_file, events_file = get_last_files()
    all_events = load_events(events_file)
    events = all_events
    disabled_event_names = get_disabled_event_names()
    if disabled_event_names:
        original_count = len(events)
        events = [event for event in events if event['event'] not in disabled_event_names]
        removed_count = original_count - len(events)
        print(f"Excluded {removed_count} events matching: {sorted(disabled_event_names)}")
    print(f"Loaded {len(all_events)} total events from {events_file}")
    print(f"Using {len(events)} events after exclusions")
    # debug different names of events
    event_names = set(event['event'] for event in events)
    print(f"Unique event names: {event_names}")
    data = load_data(profiler_file)
    print(f"Loaded data with {len(data)} rows from {profiler_file}")
    # print column names
    print(f"Data columns: {data.columns.tolist()}")
    # here are the data columns: ['Frame', 'Main Thread (ns)', 'CPU Main Thread Frame Time (ns)', 'CPU Render Thread Frame Time (ns)', 'CPU Total Frame Time (ns)', 'GPU Frame Time (ns)', 'Total Used Memory (bytes)']
    # define a command for each plot
    plts = []
    plts.append(plot_FPS_over_time(data, events))
    plts.append(plot_FrameTimes_over_time(data, events))
    plts.append(plot_FrameTimes_over_time_OnlyPhase1(data, events))
    plts.append(plot_memory_over_time(data, events))
    # Use all events for game-object correlation data; excluded events only affect overlay markers.
    plts.append(plot_data_over_gameObjects(data, all_events, marker_events=events))

    save_plots(plts);