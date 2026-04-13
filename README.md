# EE800/820: Educational Framework for AI-Driven RF Signal Processing on FPGA

This repository collects the working materials for an EE800/820 project that links RF communications, FPGA design, embedded systems, and machine learning into a single instructional pipeline.

Student: Jude Eschete  
Advisor: Bernard Yett  
Institution: Stevens Institute of Technology  
Semester: Spring 2026

## Overview

The project is organized around a benchtop RF platform in which STM32-based nodes and LoRa radios generate signals that can later be received and processed on a Digilent Nexys A7-100T FPGA. The long-term goal is an educational framework that takes students from subsystem design through data collection, feature extraction, and AI-based classification.

Before the hardware pipeline is fully operational, the repository includes a Python electronic-warfare engagement simulator that models target-to-target communication, threat detection, jamming, counter-jamming, resynchronization, logging, and scenario-level experimentation. That simulator currently serves as the most complete executable artifact in the repo.

## Hardware Platform

| Component | Model | Role |
|-----------|-------|------|
| FPGA Development Board | Digilent Nexys A7-100T (Artix-7) | Signal processing and future feature extraction |
| Microcontroller | STM32 Nucleo-L476RG | Beacon firmware and peripheral control |
| LoRa Transceiver | HopeRF RFM95W (SX1276) | RF transmission in the 915 MHz ISM band |

## Repository Layout

```text
.
├── Code/
│   ├── EngagementSim/              # Python EW simulator with GUI, logging, tests
│   └── LoRa_FPGA_FeaturePipeline/  # Vivado FPGA project assets
├── LessonPlans/                    # Curriculum modules and teaching materials
├── Notes/                          # Collected notes, URLs, reference images
├── Proposal/                       # Proposal LaTeX sources
├── Term_Paper/                     # Midstage report, paper assets, references
├── Weekly_Reports/                 # Weekly progress reports
├── ToDo.txt
└── README.md
```

## Curriculum Modules

| Module | Topic |
|--------|-------|
| 1 | RF Hardware and Subsystem Design |
| 2 | FPGA RTL Design and Simulation |
| 3 | System Integration and Data Collection |
| 4 | AI-Driven Classification Pipeline |
| 5 | System Validation and Benchmarking |

## Current Project State

The repo is currently split between documentation artifacts and implementation work:

- The Python simulator in `Code/EngagementSim` is functional and includes a GUI, map view, charts, per-asset RF configuration, scenario save/load support, CSV export, logging, and unit tests.
- The FPGA feature-pipeline work exists as a Vivado project scaffold in `Code/LoRa_FPGA_FeaturePipeline`.
- The lesson plans, proposal, term paper, and weekly reports document the instructional and research side of the project.

## Recommended Starting Points

- If you want to run software immediately, start with `Code/EngagementSim`.
- If you want the academic narrative, review `Term_Paper`, `Proposal`, and `Weekly_Reports`.
- If you want the teaching structure, review `LessonPlans`.

## Status

Mid-stage development. Hardware has been acquired, the simulator is implemented and tested, and the FPGA/feature-extraction path remains under active development.
