# Serial Monitor Logger

PyQt5 desktop app for monitoring and logging multiple serial ports simultaneously.

## Features
- Detects available COM ports and refreshes automatically.
- Starts monitoring for multiple selected ports at the same time.
- Live per-port display in separate tabs.
- Optional per-port CSV logging with timestamps.
- Safe stop for selected ports or all ports.
- Safe shutdown on app close (prompts if sessions are active).

## Setup
```powershell
cd "D:\judee\Google Drive\School\Classes\EE800_820\Code\SerialMonitorLogger"
python -m pip install -r requirements.txt
```

## Run
```powershell
python main.py
```

## Notes
- Logs are written to `logs/` next to `main.py`.
- One CSV file is created per started port session.
- CSV columns: `timestamp,port,line`.
