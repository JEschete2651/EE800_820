# EW Engagement Simulator

Electronic warfare engagement simulator with a tkinter GUI. Simulates a threat
asset jamming two target assets, with reactive counter-jamming, binary signal
sequences, and dual-file logging.

> **Note:** The GUI for this project was created using Gemini Code Assist AI.

## Running

```bash
cd Code/EngagementSim/code/EngagementSim
python -m venv .venv
.venv/Scripts/python -m app.main      # Windows
# .venv/bin/python -m app.main        # Linux/macOS
```

No external dependencies — uses only the Python standard library (tkinter).

## Project Structure

```
EngagementSim/
├── app/
│   ├── main.py                 # Entry point
│   ├── models/
│   │   ├── target.py           # Target asset (comm, counter-jam, jam state)
│   │   ├── threat.py           # Threat asset (listen, intercept, jam)
│   │   └── engagement_state.py # All assets + config container
│   ├── systems/
│   │   ├── communication.py    # Target-to-target binary data exchange
│   │   ├── jamming.py          # Threat jamming + target counter-jamming
│   │   └── logger.py           # Dual-file logger
│   ├── simulation/
│   │   └── engine.py           # Tick-based simulation loop
│   ├── ui/
│   │   ├── main_window.py      # Root tkinter window
│   │   ├── status_panel.py     # Status lights per asset
│   │   ├── control_panel.py    # Controls, config, jam buttons
│   │   └── log_panel.py        # Event log + data stream display
│   └── utils/
│       ├── constants.py        # Binary sequences, defaults, colors
│       └── helpers.py          # Sequence generators, formatters
├── logs/                       # Runtime log output
├── pyproject.toml
└── requirements.txt
```

## Features

- **3 assets**: Threat-1, Target-Alpha, Target-Bravo
- **Binary signal sequences**: DATA, ACK, JAM, counter-JAM
- **Operator-selected jamming**: Two buttons to jam either target (one at a time)
- **Reactive counter-jamming**: Targets auto-engage counter-jam when they detect jamming (40% success rate)
- **Jam threshold + cooldown**: Configurable via GUI (default: 3 hits, 5s cooldown)
- **Status lights**: Green (active), Yellow (listening/jamming), Red (jammed)
- **Dual logging**: `engagement.log` (events) and `data_stream.log` (raw binary)
- **Clear logs** button to reset both files and GUI displays
