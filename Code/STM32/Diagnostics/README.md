# L476RG Board Diagnostics

Self-test firmware for the STM32 Nucleo-L476RG. Flash this to each of the three boards (**Defender-A**, **Defender-B**, **Threat**) to confirm the board is operational before integrating the RF module or FPGA link.

## What it verifies

| # | Check | How |
|---|---|---|
| 1 | MCU identity | Reads `DBGMCU->IDCODE` → device/rev ID |
| 2 | Flash size | Reads `FLASHSIZE_BASE` (0x1FFF75E0) |
| 3 | Unique 96-bit ID | Reads UID at 0x1FFF7590 — used to tag each physical board |
| 4 | SysTick / clock | Measures `HAL_GetTick` over a known delay window |
| 5 | GPIO output | Toggles **LD2** (PA5) at 1 Hz, 5 pulses |
| 6 | GPIO input | Polls **B1** (PC13) for 5 s, expects one press |
| 7 | ADC VREFINT | Computes VDDA from the factory VREFINT calibration |
| 8 | ADC temperature sensor | Computes die temperature from TS_CAL1/TS_CAL2 |
| 9 | Heartbeat loop | Continuous LED toggle + VDDA/temp/button status over UART |

No external wiring required. All tests use only on-board resources of the Nucleo-L476RG.

## Required CubeMX configuration

Create a new project (VS Code: `STM32: New Project` → **Empty** → **NUCLEO-L476RG** → **CMake**), then in the integrated STM32CubeMX pinout view enable the following. Everything else can stay at defaults.

### Pinout & Configuration
- **PA5** — `GPIO_Output`, label `LD2`
- **PC13** — `GPIO_Input`, label `B1`, internal pull-up enabled (safe regardless of R40 population)
- **PA2** — `USART2_TX` (already default on Nucleo for the ST-LINK VCP)
- **PA3** — `USART2_RX` (already default)

### Peripherals
- **USART2**: Asynchronous, 115200 8-N-1, no flow control
- **ADC1**:
  - Enable channel **IN-Vrefint**
  - Enable channel **Temperature Sensor Channel**
  - Resolution: 12-bit
  - Continuous Conversion Mode: Disabled
  - Sampling time (both channels): **247.5 Cycles** (≥5 µs required for internal channels)
- **RCC**: High-Speed Clock Source → `MSI` (default) — this is what the default L476RG project boots with

### Clock tree
Leave at the default **80 MHz SYSCLK from PLL/MSI**. The diagnostic doesn't care about the exact clock as long as SysTick is coherent.

Click **Generate Code**. CubeMX creates `main.c`, `stm32l4xx_hal_msp.c`, CMakeLists.txt, etc.

## Integration (3 edits to the generated `main.c`)

Copy [Inc/diagnostic.h](Inc/diagnostic.h) and [Src/diagnostic.c](Src/diagnostic.c) into your project's `Core/Inc/` and `Core/Src/` folders respectively (or add them to `target_sources` in your CMakeLists.txt).

In the CubeMX-generated `Core/Src/main.c`, add three blocks between the existing `USER CODE BEGIN … / END` markers:

```c
/* USER CODE BEGIN Includes */
#include "diagnostic.h"
/* USER CODE END Includes */
```

```c
/* USER CODE BEGIN 2 */                 // after all MX_xxx_Init() calls
  Diag_Config_t cfg = {
    .uart            = &huart2,
    .adc             = &hadc1,
    .led_port        = GPIOA,  .led_pin = GPIO_PIN_5,
    .btn_port        = GPIOC,  .btn_pin = GPIO_PIN_13,
    .btn_active_low  = 1,
  };
  Diag_Init(&cfg);
  Diag_RunAll();
/* USER CODE END 2 */
```

```c
  while (1) {
    /* USER CODE END WHILE */
    /* USER CODE BEGIN 3 */
    Diag_Heartbeat();
    /* USER CODE END 3 */
  }
```

That's it. No other changes to CubeMX-generated files.

## Build, flash, observe

1. `CMake: Configure` → `CMake: Build` (from the VS Code command palette).
2. Plug the Nucleo in; `CMake: Debug` (or F5) to flash and run. Click **Continue** once if the debugger halts at `main`.
3. Open the Serial Monitor (`eclipse-cdt.serial-monitor`), select the **STLink Virtual COM Port**, **115200 8-N-1**.
4. Press the on-board blue **B1** button once when prompted.

Expected output is shown in [expected_output.txt](expected_output.txt). Values that vary per board (unique ID, VDDA, temperature) are marked `<…>`.

## PASS criteria

A board is **operational** if, in a single boot:

- Banner + "MCU ident" line prints within 2 s of power-on.
- Flash size reports **1024 kB**.
- DEV_ID reports **0x415** (STM32L4x6 family).
- LD2 visually toggles 5 times at ~1 Hz during phase 3.
- B1 press is detected within the 5 s window (phase 4).
- VDDA reads **3.10–3.45 V** (typical 3.3 V ± ~5% across the ST-LINK LDO).
- Temperature reads a plausible ambient (**15–45 °C** on a bench).
- Final summary shows every line as `PASS` (`GPIO in` may be `SKIPPED` only if you intentionally didn't press — not acceptable for board acceptance).
- Heartbeat loop runs indefinitely after the summary.

Any FAIL, missing line, or hang indicates the board (or its ST-LINK, USB cable, or VCP driver) needs attention before use.

## Testing all three boards

Run this procedure once per physical board:

1. Flash the same binary to the board.
2. Capture the first 60 s of serial output to a file. Suggested file name: `logs/<role>_<date>.txt` (e.g. `logs/DefenderA_2026-04-17.txt`).
3. Copy the **Unique ID** line from the output and record it in [board_map.md](board_map.md) against the logical role (`Defender-A`, `Defender-B`, `Threat`).

Once all three rows in `board_map.md` are filled in, physical-to-logical assignment is locked in and any future firmware can identify its role by reading the UID at boot (see *Future work* below).

## Future work

- **Role-aware firmware**: read the UID at boot and branch on the `board_map.md` table so a single binary boots correctly on any of the three nodes.
- **RF module check**: once the LoRa breakout is wired, extend `Diag_RunAll()` with an SPI register-probe against the module's chip-ID register. Track that in a Module-1 follow-up lab, not here.
- **Automated capture**: a small Python script that opens the VCP, streams to a log, and greps for `PASS`/`FAIL` would turn this into a regression check for future firmware changes. Not in scope for the first pass.

## File layout

```
Diagnostics/
├── README.md            (this file)
├── Inc/diagnostic.h     Public API — three functions
├── Src/diagnostic.c     Implementation
├── expected_output.txt  Reference serial output for a known-good board
└── board_map.md         UID → logical role table (fill in per lab)
```
