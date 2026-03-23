# EE800/820: An Educational Framework for AI-Driven RF Signal Processing on FPGA

A progressive, hardware-grounded curriculum integrating FPGA digital design, RF communications, embedded firmware, and machine learning into a single unified learning experience.

**Student:** Jude Eschete
**Advisor:** Bernard Yett
**Institution:** Stevens Institute of Technology
**Semester:** Spring 2026

---

## Project Overview

This project develops a five-module educational framework built around a concrete benchtop hardware platform. STM32 microcontrollers paired with RFM95W LoRa transceivers transmit RF signals that are received and processed in real time by a Digilent Nexys A7-100T FPGA, with collected signal data feeding a machine learning classification pipeline. A custom Python engagement simulator provides a physics-grounded, labeled training environment before physical hardware is operational.

The framework targets senior undergraduate and master's-level EE students, making each cross-domain interface an explicit teaching objective rather than an incidental detail.

---

## Hardware

| Component | Model | Purpose |
|-----------|-------|---------|
| FPGA Development Board | Digilent Nexys A7-100T (Artix-7) | Signal processing, feature extraction |
| Microcontroller | STM32 Nucleo-L476RG | Beacon firmware, receiver interface |
| LoRa Transceiver | HopeRF RFM95W (SX1276) | RF transmission at 915 MHz ISM band |

---

## Repository Structure

```
├── Code/
│   └── EngagementSim/          # Python EW engagement simulator
├── Term_Paper/
│   ├── Midstage/               # Mid-stage report (LaTeX + PDF)
│   └── Sources/
│       ├── Datasheets/         # Hardware reference manuals
│       ├── IEEESources/        # IEEE papers (gitignored)
│       └── Sources.md          # Annotated bibliography
├── Weekly_Reports/
├── .gitignore
└── README.md
```

---

## Curriculum Modules

| Module | Topic |
|--------|-------|
| 1 | RF Hardware and Subsystem Design |
| 2 | FPGA RTL Design and Simulation |
| 3 | System Integration and Data Collection |
| 4 | AI-Driven Classification Pipeline |
| 5 | System Validation and Benchmarking |

---

## Status

🟠 **Mid-Stage** — Mid-stage report complete and to be submitted. Hardware acquired. Engagement simulator implemented. FPGA RTL development in progress.
