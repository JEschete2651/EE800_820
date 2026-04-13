# EW Engagement Simulator

The Engagement Simulator is a Python desktop application for experimenting with electronic-warfare style communication and jamming behavior. It models communication between target assets, passive interception by threats, active jamming, reactive counter-jamming, RF range effects, frequency hopping, recovery/resynchronization, and session logging through a GUI built with `customtkinter`.

## What It Simulates

The default scenario starts with one threat and two targets:

- `Threat-1`
- `Target-Alpha`
- `Target-Bravo`

Targets exchange binary data and acknowledgements over shared hop sequences. Threats attempt to detect and intercept those exchanges, infer hop behavior, and jam selected targets. Jammed targets can recover after a cooldown window and use a SYNC-based resynchronization flow before resuming normal communications.

## Requirements

- Python 3.10 or newer
- `customtkinter>=5.2.0`

## Setup and Run

From the project directory:

```bash
cd Code/EngagementSim
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python -m app.main
```

Windows can also launch directly without activating the environment:

```bash
.venv/Scripts/python -m app.main
```

On Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Running Tests

```bash
cd Code/EngagementSim
python -m unittest discover -s tests -v
```

## Current Features

- Tick-based simulation engine with start, stop, pause, resume, reset, and single-step control
- Communication between targets with binary data and ACK exchanges
- Threat-side passive interception and active jamming
- Range-aware RF behavior using geospatial distance and simple link-budget calculations
- Frequency hopping and hop-sequence inference logic
- Reactive target counter-jamming
- Jam threshold, cooldown, and post-jam resynchronization behavior
- Dynamic asset management for adding and removing targets and threats
- Inline per-asset RF and jamming parameter editing from the GUI
- Map visualization for asset positions and interaction lines
- Real-time metrics charts for communications and jamming performance
- Scenario save/load support and CSV export
- Session logging to per-run log directories

## GUI Overview

- Left panel: simulation controls and per-asset configuration/status cards
- Center panel: map view and rolling metrics charts
- Right panel: event log and binary data-stream display
- Menu bar: scenario save/load, CSV export, global settings, asset management, and log clearing

Status colors currently indicate more than the original three-state view:

- Green: active
- Yellow: listening or actively jamming
- Red: jammed
- Purple: scanning
- Cyan: resynchronizing
- Gray: offline or inactive

## Logging

Each run writes logs under `logs/<timestamp>/` with per-asset and aggregate outputs. The simulator maintains separate event and binary-stream logs, which makes it easier to inspect both operator-visible behavior and raw message activity.

## Project Structure

```text
EngagementSim/
├── app/
│   ├── main.py
│   ├── models/
│   │   ├── asset_base.py
│   │   ├── engagement_state.py
│   │   ├── target.py
│   │   └── threat.py
│   ├── simulation/
│   │   └── engine.py
│   ├── systems/
│   │   ├── communication.py
│   │   ├── jamming.py
│   │   └── logger.py
│   ├── ui/
│   │   ├── chart_panel.py
│   │   ├── config_dialog.py
│   │   ├── control_panel.py
│   │   ├── log_panel.py
│   │   ├── main_window.py
│   │   ├── map_panel.py
│   │   ├── menu_bar.py
│   │   └── status_panel.py
│   └── utils/
│       ├── constants.py
│       └── helpers.py
├── logs/
├── tests/
│   ├── test_communication.py
│   ├── test_jamming.py
│   └── test_simulation.py
├── pyproject.toml
└── requirements.txt
```

## Notes

- The GUI implementation uses `customtkinter`, not the standard `tkinter` widgets alone.
- The default scenario is centered around White Sands Missile Range coordinates for map display and range visualization.
- The simulator is currently the most mature executable component in the broader EE800/820 project.
