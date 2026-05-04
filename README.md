# EE800/820: Educational Framework for AI-Driven RF Signal Processing on FPGA

This repository contains the complete deliverable for an EE800/820 master's capstone project: a five-module progressive curriculum that integrates FPGA digital design, RF communications, embedded firmware, and machine learning into a single hardware-grounded learning sequence, paired with a benchtop reference implementation that instantiates each cross-domain interface as a directly observable design problem.

Student: Jude Eschete
Advisor: Dr. Bernard Yett
Institution: Stevens Institute of Technology, Department of Electrical and Computer Engineering
Semester: Spring 2026

## Overview

The framework targets senior-undergraduate and master's-level electrical engineering students who have completed introductory coursework in each of the four constituent disciplines individually but lack experience integrating them into a working system. Three STM32 Nucleo nodes (two cooperative targets running a DATA/ACK ping-pong protocol, one interceptor capturing the bidirectional traffic and running a button-gated PAUSE protocol) feed a Digilent Nexys A7-100T FPGA over a 43-byte CRC-protected forwarding frame; the FPGA emits per-emitter feature vectors over USB-UART to a host machine, where four classifier families (random forest, SVM, MLP, 1-D CNN) are trained on a labeled dataset and the deployed pipeline runs against the live FPGA stream.

Modules 1–4 were executed end-to-end on physical hardware. Module 5 is fully specified across eight lab handouts and left as future cohort work. Four cross-domain integration faults surfaced organically during execution and are documented in [TestLog.md](TestLog.md) and the final report.

## Hardware Platform

| Component | Model | Role |
|-----------|-------|------|
| FPGA Development Board | Digilent Nexys A7-100T (Artix-7 `xc7a100tcsg324-1`) | Ingestion, parsing, CRC verification, feature extraction, host export |
| Microcontroller (×3) | STM32 Nucleo-L476RG | Cooperative target A, cooperative target B, interceptor (Threat) firmware |
| LoRa Transceiver (×3) | Adafruit RFM95W (Semtech SX1276) | RF transmission and reception in the U.S. 915 MHz ISM band, 906.5 MHz channel |

## Repository Layout

```text
.
├── Code/
│   ├── Nucleo_RFM95_TargetA/        # STM32 firmware: cooperative target A (DATA initiator)
│   ├── Nucleo_RFM95_TargetB/        # STM32 firmware: cooperative target B (ACK responder)
│   ├── Nucleo_RFM95_Threat/         # STM32 firmware: interceptor (Threat) with PAUSE TX scheduler
│   ├── Nucleo_RFM95W_Base/          # Shared firmware skeleton (LH1-A through LH1-C bring-up)
│   ├── ingest_top/                  # Vivado FPGA project: full Module 2 ingestion pipeline
│   ├── ila_0_ex/                    # Vivado ILA debug-bitstream example for Module 3
│   ├── Nexys_LoopBack/              # Vivado loopback projects for LH1-E toolchain validation
│   ├── AIML/                        # Module 4 ML pipeline (preprocess, train, deploy, live demo)
│   ├── EngagementSim/               # Pre-hardware Python EW engagement simulator (legacy)
│   ├── Tools/                       # Capture, dataset collection, EDA, Vivado-report parsers
│   ├── STM32/                       # CubeMX shared project assets
│   ├── Labs/                        # Lab-handout-specific working files
│   └── NeededFiles/                 # Loose reference assets
├── LessonPlans/
│   ├── Module 1/ ... Module 5/      # Lesson plans + 8 lab handouts per module (LH*-A..H)
├── Term_Paper/
│   ├── Proposal/                    # Original research proposal (Spring 2026)
│   ├── Midstage/                    # Mid-stage report (March 2026)
│   ├── FinalReport/                 # Final IEEE-format report (May 2026)
│   ├── PresentationScaffold.md      # 5-slide capstone presentation outline + Q&A bank
│   ├── FinalReportReqs.txt          # Course-level submission requirements
│   └── How to prepare the final report.pdf
├── Notes/                           # Working notes, references, screenshots
├── Weekly_Reports/                  # Per-week progress reports
├── Videos/                          # Demo / lab-walkthrough captures
├── TestLog.md                       # Running validation log across all lab handouts
├── ExplanationsLog.md               # Documented integration faults and resolutions
├── FigList.txt                      # Figure inventory for the final report
├── FinalReportNeeds.txt             # Pre-pivot scope-tracking checklist
├── LabHandoutNotes.txt              # Curriculum revision notes
├── ToDo.txt                         # Outstanding tasks
├── AI Use Disclaimer.txt
└── README.md
```

## Curriculum Modules

Each module spans four sessions of ~3 hours and ships eight lab handouts (`LH<n>-A` through `LH<n>-H`) under [LessonPlans/Module N/LabHandouts/](LessonPlans/).

| Module | Topic | Status |
|--------|-------|--------|
| 1 | RF Hardware and Subsystem Design | Executed on hardware (LH1-A through LH1-H) |
| 2 | FPGA RTL Design and Simulation | Executed on hardware (LH2-A through LH2-H) |
| 3 | System Integration and Data Collection | Executed on hardware; C3 (modulation) removed at design time, C4 (distance) deferred under schedule |
| 4 | AI-Driven Classification Pipeline | Executed on hardware (LH4-A through LH4-H), live three-task demo at 2 fps |
| 5 | System Validation and Benchmarking | Fully specified (LH5-A through LH5-H); cohort execution left as future work |

## Headline Results

- **Module 2 ingestion pipeline:** Vivado timing closed at 100 MHz with all 105,975 endpoints meeting setup and hold; CDC report empty; 10/10 verification testbenches pass, including byte-for-byte agreement with an independent Python reference across three recorded captures (clean, mixed, ~5% bit-flipped).
- **Module 3 dataset:** 2,197 labeled feature vectors collected across the TX-power sweep (C1, four levels), the spreading-factor sweep (C2, SF7–SF10), and the active-station-count sweep (C5, configurations C5a and C5b). Nine-check data-integrity audit passed.
- **Module 4 classifiers:** 1-D CNN over 8-frame sequences reaches 0.985 test accuracy on the spreading-factor task (95% Wilson CI [0.965, 0.993]), narrowly outperforming the random forest, SVM, and MLP baselines that all tied at 0.963–0.966 within Wilson-CI overlap.
- **Module 4 live demo:** 362 frames classified across a 3-minute timed run on physical hardware, 2.00 fps aggregate, every frame correctly classified, host inference latency p99 = 1.6 ms (8 ms budget).
- **Documented integration faults:** four cross-domain faults surfaced during execution — a missing NVIC interrupt enable, a synthesis-vs-simulation reset divergence converting block RAM into discrete flip-flops, a missing PA register write breaking link-budget monotonicity, and a session-confounded frequency-error feature — each documented in `TestLog.md` and propagated as corrected procedure into the published handouts.

## Recommended Starting Points

- **Final report (most current narrative):** [Term_Paper/FinalReport/EE800_FinalReport_Eschete.pdf](Term_Paper/FinalReport/EE800_FinalReport_Eschete.pdf) and the corresponding `.tex` source.
- **Curriculum:** [LessonPlans/](LessonPlans/) — start with `Module 1/Module1.tex` for the lesson plan and the `LabHandouts/LH1-*.tex` files for the per-handout deliverables.
- **Validation evidence:** [TestLog.md](TestLog.md) — running record of every executed lab handout.
- **FPGA implementation:** [Code/ingest_top/](Code/ingest_top/) — Vivado project for the Module 2 ingestion pipeline.
- **Firmware:** [Code/Nucleo_RFM95_TargetA/](Code/Nucleo_RFM95_TargetA/), [Code/Nucleo_RFM95_TargetB/](Code/Nucleo_RFM95_TargetB/), [Code/Nucleo_RFM95_Threat/](Code/Nucleo_RFM95_Threat/) — STM32CubeIDE projects for the three roles.
- **ML pipeline:** [Code/AIML/](Code/AIML/) — preprocess, train, select, and deploy scripts; per-stage manifest JSONs and archived run logs under `Code/AIML/Logs/`.
- **Datasets:** [Code/Tools/CampaignCollect/logs/](Code/Tools/CampaignCollect/logs/) — per-campaign CSVs and the merged `merged_dataset.csv`.
- **Pre-hardware engagement simulator (legacy):** [Code/EngagementSim/](Code/EngagementSim/) — Python EW simulator developed during the design phase before the hardware platform came online.

## Status

Final-report submission ready. The four executed modules have hardware evidence archived in `TestLog.md`, the manifest files under `Code/AIML/`, and the Vivado synthesis/implementation reports under `Code/ingest_top/`. Module 5 cohort execution and the deferred C3/C4 campaigns are documented as future work.
