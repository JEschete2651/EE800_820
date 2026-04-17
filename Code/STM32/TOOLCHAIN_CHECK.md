# STM32 Nucleo L476RG Toolchain Check

Generated: 2026-04-17
Host: Windows 11 Pro

## Summary

| Component | Status | Notes |
|---|---|---|
| VS Code STM32 extension pack | OK | All ST extensions present |
| Cortex-Debug + MCU-debug suite | OK | Peripheral/memory/RTOS viewers installed |
| STM32CubeIDE 2.1.1 | OK | `C:\ST\STM32CubeIDE_2.1.1` |
| arm-none-eabi GCC 14.3.rel1 | Bundled only | Inside CubeIDE plugins; NOT on PATH |
| OpenOCD | Bundled only | Inside CubeIDE plugins; NOT on PATH |
| STM32CubeProgrammer | Bundled only | Inside CubeIDE plugins; NOT on PATH |
| ST-LINK server | OK | `C:\Program Files (x86)\STMicroelectronics\stlink_server\stlinkserver.exe` |
| CMake 3.29.2 | OK (PATH) | `C:\Strawberry\c\bin\cmake` |
| Ninja 1.12.0 | OK (PATH) | `C:\Strawberry\c\bin\ninja` |

## Installed VS Code extensions (STM32-relevant)

### STMicroelectronics
- stmicroelectronics.stm32-vscode-extension
- stmicroelectronics.stm32cube-ide-core
- stmicroelectronics.stm32cube-ide-project-manager
- stmicroelectronics.stm32cube-ide-build-cmake
- stmicroelectronics.stm32cube-ide-build-analyzer
- stmicroelectronics.stm32cube-ide-bundles-manager
- stmicroelectronics.stm32cube-ide-clangd
- stmicroelectronics.stm32cube-ide-registers
- stmicroelectronics.stm32cube-ide-rtos
- stmicroelectronics.stm32cube-ide-debug-core
- stmicroelectronics.stm32cube-ide-debug-stlink-gdbserver
- stmicroelectronics.stm32cube-ide-debug-jlink-gdbserver
- stmicroelectronics.stm32cube-ide-debug-generic-gdbserver

### Debug / embedded
- marus25.cortex-debug
- dan-c-underwood.arm
- mcu-debug.debug-tracker-vscode
- mcu-debug.memory-view
- mcu-debug.peripheral-viewer
- mcu-debug.rtos-views
- eclipse-cdt.serial-monitor

### Build / C/C++
- ms-vscode.cpptools
- ms-vscode.cpptools-extension-pack
- ms-vscode.cpptools-themes
- ms-vscode.cpp-devtools
- ms-vscode.cmake-tools
- ms-vscode.hexeditor

## CLI checks (from Git Bash PATH)

```
arm-none-eabi-gcc : NOT FOUND
openocd           : NOT FOUND
STM32_Programmer_CLI : NOT FOUND
cmake             : /c/Strawberry/c/bin/cmake  (3.29.2)
ninja             : /c/Strawberry/c/bin/ninja  (1.12.0)
```

## Bundled toolchain inside STM32CubeIDE

Path: `C:\ST\STM32CubeIDE_2.1.1\STM32CubeIDE\plugins\`

- `com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.14.3.rel1.win32_1.0.100.202602081740\tools\bin\`
  Contains full `arm-none-eabi-*` binaries (gcc-14.3.1, g++, gdb, objcopy, size, etc.)
- `com.st.stm32cube.ide.mcu.debug.openocd_2.3.300.202602021527\`
- `com.st.stm32cube.ide.mcu.externaltools.openocd.win32_2.4.400.202601091506\`
- `com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.400.202601091506\`

These work from inside CubeIDE but are not reachable by the VS Code ST extension unless explicitly pointed at them, or unless STM32CubeCLT is installed.

## Verdict for Nucleo L476RG development in VS Code

The VS Code extension set is complete. The missing piece is the **command-line toolchain front-end**. You have two paths:

### Option A (recommended) — Install STM32CubeCLT
- Download: https://www.st.com/en/development-tools/stm32cubeclt.html
- Provides a single install that exposes: GNU Arm toolchain, CMake, Ninja, OpenOCD, ST-LINK GDB server, STM32_Programmer_CLI, and sets up the ST VS Code extension paths automatically.
- This is what `stmicroelectronics.stm32-vscode-extension` expects.

### Option B — Point VS Code at the CubeIDE bundle
Add these to your user or workspace `settings.json`:
```json
{
  "cortex-debug.armToolchainPath": "C:/ST/STM32CubeIDE_2.1.1/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.14.3.rel1.win32_1.0.100.202602081740/tools/bin",
  "cortex-debug.openocdPath": "C:/ST/STM32CubeIDE_2.1.1/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.openocd.win32_2.4.400.202601091506/tools/bin/openocd.exe"
}
```
Works, but brittle — plugin version strings change on every CubeIDE update.

### STM32CubeMX
Not found standalone. For `.ioc` code generation:
- Use CubeIDE's embedded CubeMX (File > New > STM32 Project), **or**
- Install standalone STM32CubeMX: https://www.st.com/en/development-tools/stm32cubemx.html

## Nucleo L476RG specifics

- MCU: STM32L476RGT6 (Cortex-M4F, 1 MB flash, 128 KB SRAM)
- On-board ST-LINK/V2-1 — uses `stmicroelectronics.stm32cube-ide-debug-stlink-gdbserver` (installed)
- Virtual COM Port exposed over the same USB — use `eclipse-cdt.serial-monitor` (installed)
- No extra drivers needed on Windows 11 beyond what ST-LINK server provides (installed)

## Action items

1. Install **STM32CubeCLT** (fixes the biggest gap).
2. Install **STM32CubeMX** if you plan to edit `.ioc` files without opening CubeIDE.
3. After CubeCLT install, re-run this check — `arm-none-eabi-gcc --version`, `openocd --version`, `STM32_Programmer_CLI --version` should all succeed from a fresh terminal.
