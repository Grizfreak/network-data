# Streamlit Benchmark FPS Viewer

Quick Streamlit app to visualize FPS from CSV profiler/stat files.

It also supports pcap-derived CSV summaries if you convert captures to bucketed packet and byte rate series first.

Requirements

Install dependencies in your Python environment (preferably a venv):

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

Usage

- Upload one or more CSV files exported from your profilers.
- For pcap input, run the conversion script in the project root first and then load the generated CSV.
- The app will try to detect `Frame` (or `Time Stamp`/`Time`) and `FPS` (or `average_frame_rate`) columns.
- Select which series to show from the uploaded files and optionally normalize to first sample.

Notes

This is a minimal prototype. If you want more features (searching result folders, automatic grouping by label, event-based GameObject aggregation, presets for the comparison groups), I can add them next.

`data_loader.py` and `metrics_engine.py` are shared with the `../ccl/` batch analysis pipeline (file discovery/pairing/subsystem classification, and metric extraction/unit normalization, respectively) rather than being app-specific — see `../ccl/README.md` for how that pipeline uses them, including what's involved in registering a new benchmark type.

Tests

`classify_subsystem()` (in `data_loader.py`) has a real test suite pinning its current behavior against real filenames from `../data/`, since it's an ordered, order-sensitive matching table used by both this app and the `ccl/` pipeline:

```bash
python -m unittest discover -s tests -v
```