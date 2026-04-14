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

	ax = fig.add_subplot(111)

	required_cols = ["Frame", "FPS"]
	missing_cols = [col for col in required_cols if col not in data.columns]
	if missing_cols:
		raise ValueError(f"Missing required columns in stats file: {', '.join(missing_cols)}")

	plot_data = data[["Frame", "FPS"]].copy()
	plot_data["Frame"] = pd.to_numeric(plot_data["Frame"], errors="coerce")
	plot_data["FPS"] = pd.to_numeric(plot_data["FPS"], errors="coerce")
	plot_data = plot_data.dropna(subset=["Frame", "FPS"])

	finished_rows = pd.DataFrame()
	if {"Frame", "Event", "Value"}.issubset(events.columns):
		finished_rows = events.loc[
			events["Event"] == "FinishedInstantiation", ["Frame", "Value"]
		].copy()
		finished_rows["Frame"] = pd.to_numeric(finished_rows["Frame"], errors="coerce")
		finished_rows["Value"] = pd.to_numeric(finished_rows["Value"], errors="coerce")
		finished_rows = finished_rows.dropna().sort_values("Frame").reset_index(drop=True)

	segment_points = []
	previous_frame = None
	for _, row in finished_rows.iterrows():
		current_frame = row["Frame"]
		current_value = row["Value"]
		if previous_frame is None:
			segment = plot_data.loc[plot_data["Frame"] <= current_frame, "FPS"]
		else:
			segment = plot_data.loc[
				(plot_data["Frame"] > previous_frame) & (plot_data["Frame"] <= current_frame),
				"FPS",
			]

		if not segment.empty:
			segment_points.append((current_value, segment.mean(), current_frame))
		previous_frame = current_frame

	if segment_points:
		segment_data = pd.DataFrame(segment_points, columns=["GameObjects", "AverageFPS", "Frame"])
		ax.plot(
			segment_data["GameObjects"],
			segment_data["AverageFPS"],
			marker="o",
			label="Average FPS between FinishedInstantiation events",
		)
		ax.set_xlabel("GameObjects")
		ax.set_ylabel("Average FPS")
		fig.suptitle("Average FPS per GameObject over FinishedInstantiation Events")
		ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
	else:
		ax.plot(plot_data["Frame"], plot_data["FPS"], label="FPS")
		ax.set_xlabel("Frame")
		ax.set_ylabel("FPS")
		fig.suptitle("FPS per GameObject over Frames")
		ax.ticklabel_format(style='plain', axis='x')
		ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))

	if not segment_points:
		if "Object Spawned Received" in data.columns:
			spawn_data = data[["Frame", "Object Spawned Received"]].copy()
			spawn_data["Frame"] = pd.to_numeric(spawn_data["Frame"], errors="coerce")
			spawn_data["Object Spawned Received"] = pd.to_numeric(
				spawn_data["Object Spawned Received"], errors="coerce"
			).fillna(0)
			spawn_data = spawn_data.dropna(subset=["Frame"]).sort_values("Frame")
			spawn_data["Cumulative GameObjects"] = spawn_data["Object Spawned Received"].cumsum()

			changed_rows = spawn_data.loc[
				spawn_data["Cumulative GameObjects"].ne(spawn_data["Cumulative GameObjects"].shift())
			]

			if not changed_rows.empty:
				top_ax = ax.secondary_xaxis("top")
				top_ax.set_xlabel("Cumulative GameObjects Spawned")
				top_ax.set_xticks(changed_rows["Frame"].tolist())
				top_ax.set_xticklabels(
					[f"{int(v):,}" for v in changed_rows["Cumulative GameObjects"]],
					rotation=45,
					ha="left",
				)
				top_ax.tick_params(axis="x", labelsize=8, pad=2)

	if not segment_points and {"Frame", "Event"}.issubset(events.columns):
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

	ax.axhline(y=72, color="red", linestyle="--", linewidth=1.2, label="72 FPS limit")

	fig.subplots_adjust(right=0.85)
	ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
	if debug:
		plt.show()
	return fig
