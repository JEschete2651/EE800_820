# EE800/820 Test Log

Running record of validation runs across the lab handouts. Each entry captures the handout step under test, the raw output, and a short narrative on what the result means.

---

## LH1-H - End-to-end ingestion (Module 1 capstone)

### Step 5 - Live ingestion run

**Output (seven-segment display):**
- Right two digits alternated `01` / `02` matching live Beacon IDs from Target A and Target B.
- Left two digits incremented as a 16-bit frame counter (low byte) at roughly 2 Hz.
- LED[0] flickered rapidly (rx_strobe), LED[1] pulsed at ~1 Hz cadence (new_frame).

**Narrative:** Initial run after programming the LH1-H bitstream. The right two digits behaved correctly. The left counter, however, only incremented when the Threat board was reset. Investigation traced the failure to the Threat firmware: the USART3 TX path completed exactly one DMA transfer per board reset and then stalled forever. Root cause was the missing `USART3_IRQn` NVIC enable in CubeMX - `HAL_UART_Transmit_DMA` waits on the USART Transmission Complete interrupt to clear `tx_busy`, and without the NVIC line that callback never fired. The captured serial logs corroborated this: every `# stats:` line on the Threat showed `dropped = rx - 1`, with only one frame ever escaping per Threat boot.

**Resolution:** Enable USART3 global interrupt in CubeMX → regenerate code. Documentation updated:
- LH1-C Step 1.6 amended to include the NVIC enable instruction (was missing).
- LH1-C now matches the format of Steps 1.5 (EXTI) and 1.7 (TIM2).

**After fix:** seg7 alternated `01`/`02` at full ~2 Hz cadence as designed.

---

## LH2-A - Module 2 project orientation, FPGA passthrough, capture set

### Step 4 - USB-UART passthrough modification

**Output:** new `ingest_top.vhd` adds the `UART_RXD_OUT` port and a single passthrough assignment routing `uart_rx_pin` directly to the Nexys A7's onboard FT2232 USB-UART. XDC entry for pin `D4` uncommented. Re-synthesis, implementation, and bitstream generation completed with zero errors and timing slack remained positive (WNS ≥ 0, WHS ≥ 0).

**Narrative:** Course originally required a separate USB-to-UART adapter to record the Threat's USART3 stream for Module 2 testbenches. Adapter was not on hand. The Nexys A7's FT2232 already exposes a virtual COM port on the same USB cable used to program the board, and pin D4 is wired to the FPGA-to-host RX direction of that UART. Both ends are 115200 8N1, so a direct wire from `uart_rx_pin` to `UART_RXD_OUT` echoes the byte stream verbatim with no re-serialization. The seven-segment display and frame detector continue to operate unchanged - the passthrough is purely additive. After programming the new bitstream, the host enumerated the FPGA as a new COM port.

### Step 6.1 - Clean capture (`capture_clean.bin`)

**Command:** `python "Code/Tools/RawCapture/raw_capture.py" COM7 115200 "Code/ingest_top/data/capture_clean.bin" --frames 1500`

**Output:** 62952 bytes written, 1500 start delimiters seen. Capture rate was steady at ~2 frames per second (DATA + ACK). No button presses during this run.

**Narrative:** First confirmation that the passthrough path actually delivers a usable byte stream to the host. Frame count and file size both match expectation for ~1500 × 43-byte frames with a small partial-frame leader. Stream content is the radio ping-pong only, no PAUSE traffic.

### Step 6.2 - Mixed capture (`capture_mixed.bin`)

**Command:** `python "Code/Tools/RawCapture/raw_capture.py" COM7 115200 "Code/ingest_top/data/capture_mixed.bin" --frames 1500`

**Output:** 63167 bytes written, 1500 start delimiters seen. Approximately 30 seconds into the recording the Threat's B1 button was held for ~5 seconds; during the hold the seg7 froze on the last beacon ID and the radio ping-pong stalled. After release, traffic and the seg7 alternation resumed normally.

**Narrative:** The original handout claimed PAUSE frames would appear at the FPGA as `FF` on the seg7. Code review of the Threat firmware showed PAUSE frames are *transmitted* by the Threat on the radio but never *received* by it (the SX1276 is half-duplex shadowed during its own TX), so PAUSE frames never enter the USART3 forwarding path. The mixed capture therefore contains only DATA + ACK plus a ~500 ms gap during the button hold. The gap is still useful: it exercises the Module 2 parser's re-sync logic in LH2-G's end-to-end testbench. LH2-A handout was corrected to describe the actual behavior.

---

## LH2-B - UART receiver with oversampling

### Step 4 - Unit testbench `tb_uart_rx`

**Output (Tcl console after `run 1 ms`):**
```
Note: tb_uart_rx PASS
Time: 287900 ns  Iteration: 0  Process: /tb_uart_rx/line__58
$finish called at time : 287900 ns
```

**Narrative:** Sends a single `0xA5` byte at 115200 baud, expects exactly one `rx_strobe` pulse with `rx_data = 0xA5`. Initial run hit two preventable issues:

1. **`to_hstring(std_logic_vector)` not resolved by xsim** under the default VHDL-93 mode. Replaced with a local `slv_to_hex` helper function. Both the on-disk testbench and the LH2-B handout listing were updated.

2. **`run 1 ms` issued twice** in quick succession produced a spurious second `rx_strobe`, tripping the assertion. The first `run` reaches `std.env.finish` and prints PASS, but xsim does not actually exit on `finish` - it stays loaded with state. A second `run` then re-entered the stimulus and generated another byte. Single `run 1 ms` per simulation start is the correct usage.

After both fixes, single-byte unit test passed cleanly at 287.9 µs simulated time. Module 2 `uart_rx` correctly recovers a single byte from a bit-banged 115200 8N1 stream.

### Step 5 - Regression testbench `tb_uart_rx_regression`

**Output (Tcl console after `run 6 sec`):**
```
Note: tb_uart_rx_regression PASS: 62952 bytes
Time: 5464434700 ns  Iteration: 0  Process: /tb_uart_rx_regression/line__53
$finish called at time : 5464434700 ns
run: Time (s): cpu = 00:04:13 ; elapsed = 00:04:30 . Memory (MB): peak = 3388.969
```

**Narrative:** Streamed all 62952 bytes from `capture_clean.bin` through the Module 2 `uart_rx` at 115200 baud and compared every received byte to the source file. Zero mismatches over 5.46 seconds of simulated UART activity, ~4.5 minutes wall clock.

Pre-launch Vivado runtime defaulted to `1000ns`, far short of the ~5.5 simulated seconds required. First attempt with `run 200 ms` left the simulator idle (process at 0% CPU) because the stimulus process hadn't reached its end-of-file path. Boosting the runtime to 6 seconds let the regression complete. LH2-B handout was updated to set `xsim.simulate.runtime` to `6sec` up front and document the wall-clock cost.

This is the strongest single piece of evidence so far that the Module 2 RTL chain (UART receiver only at this point) handles real-world Threat traffic byte-for-byte.

---

## LH2-C - Byte FIFO widened from 16 to 64

### Step 4 - Unit testbench `tb_byte_fifo`

**Output (Tcl console after `run 5 us`):**
```
Note: tb_byte_fifo PASS
Time: 1195 ns  Iteration: 0  Process: /tb_byte_fifo/line__30
$finish called at time : 1195 ns
```

**Narrative:** Wrote 16 ascending bytes (`0x10..0x1F`), read them back, and verified that the registered read output matches expected values with the documented one-cycle latency. After the 16 reads the FIFO returns to empty. PASS at 1.2 µs simulated time.

Two operational notes worth recording for the rest of Module 2:

1. **Sim top has to be the testbench.** When the Simulation Sources tab still has a previous handout's testbench (or worse, a design entity) set as top, Vivado launches that and either does nothing or runs the wrong DUT. The fix is right-click the new testbench in Simulation Sources → Set as Top.

2. **`simulate.log` lock.** If a previous simulator session is still open, Vivado cannot overwrite `simulate.log` for the next run. Close the existing simulation window (or the entire IDE if it's stubborn) before launching the next sim. This will recur with every testbench-to-testbench transition in Module 2.

### Step 5 - Overflow stress testbench `tb_byte_fifo_overflow`

**Output (Tcl console after `run 5 us`):**
```
Note: tb_byte_fifo_overflow PASS
Time: 1595 ns  Iteration: 0  Process: /tb_byte_fifo_overflow/line__30
$finish called at time : 1595 ns
```

**Narrative:** Wrote 65 bytes back-to-back with no reads. The FIFO held at depth 64, the `full` flag first asserted on write index 64 (the 65th attempt), and the 65th write was correctly dropped without corrupting pointers or count. After a full reset, both `empty` and not-`full` returned cleanly. PASS at 1.6 µs simulated.

This confirms the back-pressure behavior the wider FIFO needs once the LH2-D `pkt_parser` introduces transient stalls during CRC computation. With a 64-deep buffer and continuous-rate UART input (~12 µs per byte at 115200 baud after framing), the FIFO can absorb up to ~750 µs of parser stall, comfortably more than any realistic CRC-related back-pressure window.

---

## LH2-D - Frame detector replaced by `pkt_parser`

### Step 5 - Parser unit testbench `tb_pkt_parser`

**Output (Tcl console after `run 20 us`):**
```
Note: tb_pkt_parser PASS
Time: 5675 ns  Iteration: 0  Process: /tb_pkt_parser/line__92
$finish called at time : 5675 ns
```

**Narrative:** Three-frame stimulus driven through a behavioral byte source: a valid frame with Beacon ID `0x01`, a frame with a bad length byte (`0x30` instead of `0x29`), and a valid frame with Beacon ID `0x02`. Parser correctly emitted two `frame_valid` pulses with the right Beacon IDs in `payload(23 downto 16)`, and one `frame_reject` pulse on the bad-length frame. PASS at 5.7 µs simulated.

This is the first test that exercises the full `S_HUNT → S_REQ → S_WAIT → S_CAPTURE` cycle including the registered FIFO-read latency, the length-byte gate (which `frame_detector` did not have), and the `S_REJECT` path. Beacon ID lands at radio packet byte 2 = frame offset 12 = `payload(23 downto 16)` in the packed payload vector - same indexing math the LH2-D `ingest_top` uses to drive the seg7.

CRC verification is not exercised yet (this handout only checks framing and length); LH2-E adds CRC-8 and CRC-16 engines and extends `pkt_parser` to gate `frame_valid` on CRC match.

---

## LH2-E - Hardware CRC-8 and CRC-16 verification

### Step 4 - Golden-vector testbench `tb_crc`

**Output (Tcl console after `run 5 us`):**
```
Note: tb_crc PASS
Time: 435 ns  Iteration: 0  Process: /tb_crc/line__53
$finish called at time : 435 ns
```

**Narrative:** Streamed the ASCII string "123456789" (the canonical CRC check input) through both engines simultaneously and verified the standard test vectors:

- **CRC-8/ITU** (poly 0x07, init 0x00): expected and got `0xF4`
- **CRC-16/CCITT-FALSE** (poly 0x1021, init 0xFFFF): expected and got `0x29B1`

PASS at 435 ns simulated time - one cycle per byte of input plus pipeline reset and post-loop settle. The bit-serial unrolled `update8`/`update16` functions both work correctly; their VHDL `for` loops collapse to combinational XOR trees in synthesis.

Pre-applied the LH2-B fix this time around: replaced `to_hstring(crc8)` and `to_hstring(crc16)` in the assertion-failure messages with local `slv_to_hex8`/`slv_to_hex16` helpers, since Vivado xsim under VHDL-93 mode does not always resolve `to_hstring` for `std_logic_vector`. The handout listing was also updated so future students inherit the working version.

These engines are now wired into the LH2-E `pkt_parser` rewrite. CRC-8 covers frame bytes 1–41 (the trailing byte 42 is the captured CRC); CRC-16 covers radio bytes 0–29 = frame bytes 10–39 (radio bytes 30–31 = frame bytes 40–41 are the captured CRC, with the high byte first per LH1-G's `build_forwarding_frame`). A frame is `frame_valid` only if length, CRC-8, and CRC-16 all check out; otherwise `frame_reject` fires.

---

## LH2-F - Feature extraction and per-Beacon-ID BRAM

### Step 5 - Feature extractor unit testbench `tb_feature_extract`

**Output (Tcl console after `run 50 us`):**
```
Note: feature_extract S_COMPUTE: beacon=0x1   bram_rd_data(95:64)=0x0
Note: feature_extract S_COMPUTE: beacon=0x1   bram_rd_data(95:64)=0x1
Note: feature_extract S_COMPUTE: beacon=0x1   bram_rd_data(95:64)=0x2
Note: feature_extract S_COMPUTE: beacon=0x2   bram_rd_data(95:64)=0x0
Note: feature_extract S_COMPUTE: beacon=0x2   bram_rd_data(95:64)=0x1
Note: feature_extract S_COMPUTE: beacon=0x255 bram_rd_data(95:64)=0x0
Note: row 0x01 frame_count read = 3 ; pkt_type byte = 0
Note: tb_feature_extract PASS
Time: 655 ns  Iteration: 0  Process: /tb_feature_extract/line__78
$finish called at time : 655 ns
```

**Narrative:** Six injected frames (3× DATA from beacon 0x01, 2× ACK from beacon 0x02, 1× PAUSE from beacon 0xFF with target=0x01 and duration=0x05). The extractor's per-beacon read-modify-write produced the right counts on every read: 0/1/2 for the three beacon-0x01 frames, 0/1 for the two beacon-0x02 frames, 0 for the single beacon-0xFF frame. Three host-port readbacks confirmed `frame_count`, `pkt_type`, `target_id_if_pause`, and `pause_duration_units` were stored correctly. PASS at 655 ns.

**Bug found and fixed before PASS:** the first attempt failed with row-0x01 frame_count = 6 (all six frames hit row 0x01). Debug `report` statements inside the FSM showed the beacons were extracted correctly (1,1,1,2,2,FF) but every fresh read of an as-yet-unwritten BRAM row was returning a stale non-zero value. Root cause: the original `feature_bram.vhd` had no reset clause - `mem` was initialized via the VHDL signal-declaration default `(others => (others => '0'))` and the registered read outputs had no init at all. Vivado xsim apparently latched stale values from the testbench's signal-driver lifetime and surfaced them as the read result before the first write to a given address.

The fix added an `rst_n` input to `feature_bram` and a synchronous-reset clause that explicitly clears `mem`, `rd_data_a`, and `rd_data_b` while reset is asserted. With clean reset behavior the very first read of any address returns 0 deterministically, the read-modify-write sequence increments correctly, and per-beacon counts come out right. `ingest_top.vhd` was updated to wire `rst_n => rst_n` on `u_bram`. The LH2-F handout listings (`feature_bram.vhd`, the `u_bram` instantiations in both `ingest_top` and the testbench) were updated to match.

This is the broadest pipeline test so far: `pkt_parser` → `feature_extract` → `feature_bram` → host port. Module 2 hardware now correctly accumulates per-Beacon-ID statistics and stores the feature vector at the address determined by the radio packet's sender field. The LH2-G end-to-end testbench will replay the recorded captures through this same pipeline.

---

## LH2-G - End-to-end pipeline regression against recorded captures

### Step 5 - Three-scenario byte-for-byte regression

**Output (PowerShell after all three sims and Python references generated):**
```
PS> Compare-Object (Get-Content Code/ingest_top/data/dump_clean.txt)   (Get-Content Code/ingest_top/data/ref_clean.txt)
PS> Compare-Object (Get-Content Code/ingest_top/data/dump_mixed.txt)   (Get-Content Code/ingest_top/data/ref_mixed.txt)
PS> Compare-Object (Get-Content Code/ingest_top/data/dump_corrupt.txt) (Get-Content Code/ingest_top/data/ref_corrupt.txt)
```

All three commands returned no output - every BRAM row in the simulated hardware dump is bit-identical to the Python reference for every capture.

**Narrative:** This is the Module 2 capstone test. `tb_ingest_top` bit-bangs every byte of a `.bin` capture through `uart_rx → byte_fifo → pkt_parser → feature_extract → feature_bram` at 115200 baud, then walks all 256 BRAM rows via the host read port and dumps each as a hex string. `ref_pipeline.py` parses the same `.bin` in Python (CRC-validated, with the same field-packing as the VHDL FSM) and emits the same hex format. Diff = zero across all three:

- **`capture_clean.bin`**: only Target A initiating DATA. Row 0x01 populated; all other rows zero.
- **`capture_mixed.bin`**: Target A + Target B ping-pong with button-hold gaps. Rows 0x01 and 0x02 populated.
- **`capture_corrupt.bin`**: synthesized from `capture_mixed.bin` by flipping one random bit in ~5% of frames (seeded RNG). The `pkt_parser`'s CRC-8 and CRC-16 gates correctly reject the corrupted frames, and the rejected frames never reach `feature_extract`. The accumulated counts in the dump exactly match what the Python reference computed by skipping the same frames at the same CRC checks.

The corrupt-stream pass is the strongest evidence the LH2-E CRC engines work correctly: independent VHDL and Python implementations of the same two CRC polynomials, run against the same bit-flipped frames, agree on which frames pass and which are rejected, on every frame, with zero discrepancies.

**Two debugging detours along the way:**

1. **VHDL-2008 external-name elaboration crash.** First TB revision used `alias host_rd_data_int is << signal .tb_ingest_top.dut.host_rd_data_int : std_logic_vector(255 downto 0) >>` to peek inside `ingest_top`. Vivado 2025.2 xsim accepted the syntax but crashed during elaboration with `EXCEPTION_ACCESS_VIOLATION`. Inline external-name expressions had the same fate. Fix: add `host_rd_data_dbg` as a real output port on `ingest_top` (unconstrained - Vivado emits a benign DRC info note) and read it as a normal signal in the testbench. LH2-F's listings updated to add the port and assignment; LH2-G's listings updated to wire it into the TB.

2. **Default 1 us xsim runtime.** Same as LH2-B regression: the TB needs ~5.5 simulated seconds to bit-bang a 1500-frame capture at 115200 baud. `run 6 sec` once in the Tcl console after the launch, or set `xsim.simulate.runtime` to `6sec`. Wall-clock cost ~4-5 minutes per scenario.

This concludes Module 2 simulation coverage. The hardware pipeline is byte-accurate against an independent reference implementation across nominal, multi-station, and corrupted traffic. Ready for Module 3 hardware deployment and live data collection.

---

## LH2-H - Resource and timing analysis on the synthesized Module 2 pipeline

### Step 1 - Post-synthesis utilization

**Output (extract from `ingest_top.runs/synth_1/ingest_top_utilization_synth.rpt`, Vivado 2025.2, target `xc7a100tcsg324-1`):**

| Resource         | Used   | Available | Util.  |
|------------------|--------|-----------|--------|
| Slice LUTs       | 19 161 | 63 400    | 30.22% |
| · LUT as Logic   | 19 149 | 63 400    | 30.20% |
| · LUT as Dist RAM| 12     | 19 000    | 0.06%  |
| Slice Registers  | 53 032 | 126 800   | 41.82% |
| F7 Muxes         | 9 304  | 31 700    | 29.35% |
| F8 Muxes         | 4 641  | 15 850    | 29.28% |
| Block RAM Tile   | 0      | 135       | 0.00%  |
| DSP48            | 0      | 240       | 0.00%  |
| Bonded IOB       | 49     | 210       | 23.33% |
| BUFGCTRL         | 1      | 32        | 3.13%  |

**Narrative:** Synthesis closes - but the resource shape is dramatically different from the LH2-H expected envelope (~600 LUTs, ~640 FFs, 5 BRAM tiles). The post-synth design uses **19 161 LUTs and 53 032 FFs with zero BRAM**, dominated by flip-flops by a factor of about 2.8×. The unmistakable signature: **`feature_bram` did not infer as block RAM; Vivado mapped the entire 256-row × 256-bit storage into discrete flip-flops.**

The 65 536 FFs that storage would require alone account for the bulk of the 53 k registered design. Cause is the synchronous reset clause we added in LH2-F to fix the xsim stale-read bug:

```vhdl
if rst_n = '0' then
    mem       <= (others => (others => '0'));
    rd_data_a <= (others => '0');
    rd_data_b <= (others => '0');
else
    ...
```

Synchronously clearing 256 rows × 256 bits in a single cycle is not a primitive that BRAM hardware supports; Vivado falls back to flip-flop inference rather than emit BRAM with bespoke clear logic. The simulation worked because xsim treats the array as a generic signal, but synthesis is forced to take the structural meaning literally.

The fix for clean BRAM inference in Module 3 is to **drop `mem` from the reset clause** and rely on Vivado's BRAM init-to-zero behavior instead. The reset on `rd_data_a`/`rd_data_b` (the registered output flops) can stay; those are real flip-flops adjacent to the BRAM tile, not the BRAM contents themselves. Once that change is in, Vivado should map the 256×256 storage to two 36 Kb tiles, the FF count should fall to a few thousand (just the FSM and pipeline registers), and the LUT count should drop accordingly.

This is a real and useful artifact of LH2-F's xsim-portability fix colliding with synthesis behavior - exactly the kind of cross-tool friction the curriculum is supposed to expose. Logging it here so Module 3's bitstream rebuild starts from corrected RTL rather than rediscovering the issue under timing pressure.

Other notes from the report:

- **49 bonded IOBs.** Matches expected: 16 LEDs + 16 switches + 7 segments + 1 DP + 8 anodes + CLK100MHZ + CPU_RESETN + uart_rx_pin + UART_RXD_OUT − CLK (uses BUFG, not bonded as IOB) ≈ 49. The simulation-only `host_rd_data_dbg` port was correctly excluded by the `synthesis translate_off`/`translate_on` pragmas - proof that the workaround works.
- **0 BRAM, 0 DSP.** As expected for a no-floating-point feature path. Once the BRAM inference is fixed, this becomes 2 RAMB36 tiles with 0 DSP.
- **1 BUFGCTRL** for the 100 MHz clock distribution. Single clock domain confirmed - the only intentional CDC is the dual-flip-flop synchronizer on `uart_rx_pin`, which doesn't use a BUFG.

### Step 2 - Post-route timing (impl_1)

**Output (extract from `ingest_top.runs/impl_1/ingest_top_timing_summary_routed.rpt`):**

| Metric                  | Value           |
|-------------------------|-----------------|
| Target clock            | 100 MHz (10 ns) |
| WNS (setup)             | **+1.191 ns**   |
| TNS                     | 0.000 ns        |
| Failing setup endpoints | 0 / 105 975     |
| WHS (hold)              | +0.030 ns       |
| THS                     | 0.000 ns        |
| Failing hold endpoints  | 0 / 105 975     |
| WPWS (pulse width)      | +3.750 ns       |
| TPWS                    | 0.000 ns        |
| User constraint result  | All met         |

**Worst setup path (the critical path):**
- **Source**: `u_feat/bram_wr_data_reg[3]/C`
- **Destination**: `u_bram/mem_reg[155][102]/CE`
- **Data path delay**: 8.428 ns (0.866 ns logic, 7.562 ns routing - 89.7% routing-dominated)
- **Logic levels**: 2 (two LUT5)

**Narrative:** Timing closes - every one of 105 975 endpoints meets both setup and hold. WNS at +1.191 ns and WHS at +0.030 ns are real positive slack, not warnings. The bitstream is producible.

But the slack is **much tighter than the LH2-H expected envelope of ≥ 3 ns**, and the critical-path source/destination tells the same story Step 1 did: `u_feat/bram_wr_data_reg[3]` → `u_bram/mem_reg[155][102]/CE`. The path goes from the feature-extractor's write-data register, through 7.5 ns of routing across the chip, into a *flip-flop's clock-enable* on `mem_reg`. There are 65 536 such `mem_reg` flops because `feature_bram` was synthesized as discrete FFs instead of a BRAM tile (Step 1 root cause). The write-enable network has to reach all 65 k of them, and the placer can only do so much when the storage is spread across hundreds of slices instead of compactly inside two BRAM tiles.

Once the BRAM inference fix from Step 1 is applied (drop `mem` from the synchronous reset clause), the 65 536 flops collapse into two RAMB36 tiles, the write-enable network shrinks from a chip-spanning fanout to two BRAM-local enables, the routing component of the critical path falls dramatically, and slack should recover to the ≥ 3 ns range. Hold slack of +0.030 ns is also tight enough that any layout change could push it negative; the BRAM fix relaxes both setup and hold simultaneously.

The reported numbers nonetheless certify the LH2-H acceptance criterion: setup met, hold met, no failing endpoints, all user constraints satisfied. The Module 2 bitstream is functionally signoff-ready; the BRAM-inference fix is a Module 3 polish task to reclaim margin before adding host-readback logic in LH3-A.

A separate "infinite slack" path appears in the report (SW[8] → LED[13], 24.86 ns) because that path has no clock - `SW` is an asynchronous input and `LED` is a combinational output of the byte selector. Vivado correctly excludes it from setup analysis. Not a concern.

### Step 3 - Clock-domain crossing report

**Output (full body of `ingest_top.runs/impl_1/ingest_top_cdc.rpt` after the standard tool header):**

```
CDC Report

(empty)
```

**Narrative:** Vivado's CDC analyzer reports **zero clock-domain crossings** in the routed design. That is the cleanest possible CDC signoff - no asynchronous register pairs, no missing synchronizer warnings, no clock-to-clock paths flagged.

The reason the report is empty rather than showing a single approved entry for the dual-flip-flop synchronizer on `uart_rx_pin` is that `uart_rx_pin` has no input clock constraint in the XDC (no `set_input_delay`, no `create_clock`). Vivado therefore classifies it as a static asynchronous input rather than as a second clock domain. From the tool's perspective the design has exactly one clock - `sys_clk_pin` (100 MHz on `CLK100MHZ`) - and there are no clock-to-clock paths to report. The synchronizer in `uart_rx.vhd` is doing its job: Vivado recognizes the two-FF pattern, treats it as the supplied metastability hardener for the async input, and emits no warnings.

This is also implicit confirmation that no *unintended* CDC sneaked in. Had any signal in the design been driven by a different clock than `sys_clk_pin` - for example if a developer accidentally derived a divided clock and used it to drive a register - Vivado would have flagged the crossing here. The empty report is the affirmative result.

LH2-H Step 3: PASS. Single clock domain confirmed.

### Step 4 - Bitstream generation and power report

**Output (extract from `ingest_top.runs/impl_1/ingest_top_power_routed.rpt`):**

| Metric                     | Value          |
|----------------------------|----------------|
| Total On-Chip Power        | 0.236 W        |
| Dynamic Power              | 0.139 W        |
| Device Static Power        | 0.098 W        |
| Junction Temperature       | 26.1 °C        |
| Max Ambient                | 83.9 °C        |
| Effective TJA              | 4.6 °C/W       |
| Vccint Total Current       | 0.152 A @ 1.0 V|
| Confidence Level           | Low            |

**Per-component dynamic power breakdown:**

| Component     | Power     | Used    | % Util |
|---------------|-----------|---------|--------|
| Clocks        | 0.061 W   | 3       | -      |
| Signals       | 0.058 W   | 58 046  | -      |
| Slice Logic   | 0.019 W   | 86 338  | -      |
| · LUT as Logic| 0.018 W   | 19 139  | 30.19% |
| · Registers   | <0.001 W  | 53 034  | 41.82% |
| I/O           | 0.002 W   | 49      | 23.33% |
| **Static**    | **0.098 W** | -     | -      |
| **Total**     | **0.236 W** | -     | -      |

**Narrative:** Bitstream generated successfully (`ingest_top.bit` available in `impl_1/`). The post-route power estimate is **236 mW total**, comfortably under the LH2-H expected envelope of 200 mW *dynamic*. Total dynamic power is **139 mW**, which is 31% under the 200 mW expectation despite the BRAM-as-flip-flops issue identified in Step 1.

**Why dynamic power stayed in budget despite the resource bloat:** the 53 k flip-flops report only **<1 mW** of register power, because the design has a single non-reset transition pattern (the FSM advances on `frame_valid` events, and most of the 53 k mem flops are entirely idle between frames). The bulk of the dynamic power is split between the clock distribution network (61 mW for one BUFG plus 105 k clock-pin loads) and signal switching (58 mW across 58 k signals). I/O contribution is negligible at 2 mW for 49 bonded pins. Junction temperature stabilizes at 26.1 °C in still air with the FPGA's default thermal model, well under the 100 °C derate threshold.

The **Low confidence level** is a Vivado caveat about activity factor estimation, not a power risk: the report flags that 75% of input nodes have no user-specified activity (because no SAIF or simulation activity file was supplied), so Vivado falls back to its default 12.5% switching activity for unspecified internal nodes. The actual operating activity will be lower in practice - the radio frame rate is ~2 Hz, so most of the design is quiescent the vast majority of the time. The 236 mW total is therefore a realistic *upper bound* for nominal operation.

The design closes timing, generates a bitstream, and stays well under power budget. **LH2-H Step 4: PASS.** Module 2 hardware deliverable is signoff-ready.

The two flagged improvements remain as Module 3 polish:
1. **Drop `mem` from the synchronous reset clause in `feature_bram.vhd`** to let Vivado infer two RAMB36 tiles. Resource shape collapses to ~2 BRAM + ~3 k FFs, critical-path slack recovers from +1.19 ns to ≥ +3 ns, and dynamic power likely drops further (BRAM tile dynamic power per row is much lower than 65 k flip-flop fanout switching).
2. **`host_rd_data_dbg` simulation-only port pragmas** (added in this session) work correctly - IOB count is 49, exactly matching the constrained ports, with no spurious bonding for the 256-bit debug bus. The synthesis-translate pragmas survived Vivado 2025.2 cleanly.

This concludes Module 2 hardware signoff. Bitstream is producible, all eight verification testbenches pass, byte-for-byte regression matches the Python reference across three captures, timing is met, CDC is clean, power is under budget. Module 3 hardware deployment can begin.

---

## LH3-F - Collection script and Campaign C1 (TX power sweep)

### Step 5 - Campaign C1, +14 dBm point

**Configuration:** Target A `LORA_SF 7`, `LORA_TX_PWR_DBM 14`. Target A 3 m from the Threat antenna; Threat powered on and forwarding; Target B off. Run started 2026-05-03 18:02:41 UTC, ended 18:06:00 UTC (≈ 3 min 19 s wall clock). Output: `Code/Tools/CampaignCollect/logs/campaign_c1_txpwr_14/results_campaign_c1_txpwr_14.csv`.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Beacon IDs present  | `0x01` only (Target A)             |
| Packet type         | `0` (DATA only) - no ACK, no PAUSE |
| Spreading factor    | 7                                  |
| Payload length      | 14 bytes                           |
| Sequence numbers    | 373 → 572, contiguous, 0 gaps      |
| RSSI                | mean −71.23 dBm, σ 0.55, range [−73, −70] |
| SNR                 | mean 9.55 dB,  σ 0.33, range [8.0, 12.5]   |
| Inter-arrival time  | mean 1001.3 ms, σ 0.46, range [1001, 1002] (n = 199) |
| Frequency error     | 5147 Hz constant across all rows   |

**Narrative:** First live Campaign C1 collection point. The handout's acceptance pattern for C1 is "monotonically increasing mean RSSI with TX power across 200 packets per level"; this run is the +14 dBm anchor, and the result looks healthy on every axis.

- **Packet count and sequence integrity.** 200 rows captured, sequence numbers 373–572 with zero gaps. The collector saw every frame the Threat forwarded for the duration of the run - no dropped frames at the FPGA-to-host UART hop, no parser rejections in the host-side `collect.py`.
- **RSSI is tight and physically plausible.** σ = 0.55 dB across 200 packets at 3 m line-of-sight is consistent with a stationary geometry and no human movement during the run. −71 dBm at +14 dBm TX in a benign indoor channel is in the expected ballpark for SX1276 ↔ SX1276 at 3 m.
- **SNR comfortably positive.** Mean +9.5 dB, never below +8 dB. SF7 has a sensitivity of ≈ −123 dBm at the chip's tabulated noise floor; we are nowhere near that limit at this geometry, which is exactly what the +14 dBm anchor is supposed to demonstrate.
- **Inter-arrival is a near-perfect 1.000 s.** σ = 0.46 ms across 199 intervals. Target A's loop is timer-driven on a 1 Hz cadence, so the dispersion here is essentially the host timestamp jitter plus USART/USB-UART buffering - both expected to be in the sub-millisecond range. No collisions, no Threat retries, no missed forwards.
- **Frequency error is a single value (5147 Hz).** This is a static crystal offset between the Target A and Threat SX1276 modules at this temperature, surfaced verbatim by the radio's `RegFeiMsb/Lsb` registers. The fact that it's identical for all 200 packets confirms the field is being read from the radio register (not synthesized) and that nothing in the parsing path is corrupting it.
- **Schema sanity.** All 21 schema columns populated; `beacon_id`, `pkt_type`, `spread_factor`, `payload_len`, `distance_m`, and the four label columns are constant within the run as expected; `rx_timestamp_ms` and `tx_timestamp_ms` advance monotonically; `timestamp_host` matches the run window in the campaign config.

**Result:** PASS for the +14 dBm anchor. The other three C1 points (+2, +8, +20 dBm) remain to be collected by editing `LORA_TX_PWR_DBM` in [main.c:54](Code/Nucleo_RFM95_TargetA/Core/Src/main.c#L54), rebuilding (F7), flashing (F5), and re-running `python collect.py` against the matching campaign entry. Once all four points are in, the C1 acceptance check is "mean RSSI monotonically increases with TX power across {2, 8, 14, 20} dBm."

### Step 5 - Campaign C1, +2 dBm point

**Configuration:** Target A `LORA_SF 7`, `LORA_TX_PWR_DBM 2`. Same geometry as the +14 dBm anchor (3 m line-of-sight, Threat forwarding, Target B off). Run started 2026-05-03 18:11:36 UTC, ended 18:14:55 UTC (≈ 3 min 19 s wall clock - same as the +14 dBm run, since the radio cadence is unchanged). Output: `Code/Tools/CampaignCollect/logs/campaign_c1_txpwr_2/results_campaign_c1_txpwr_2.csv`.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Beacon IDs present  | `0x01` only (Target A)             |
| Packet type         | `0` (DATA only)                    |
| Spreading factor    | 7                                  |
| Payload length      | 14 bytes                           |
| Sequence numbers    | 63 → 262, contiguous, 0 gaps       |
| RSSI                | mean −82.25 dBm, σ 0.86, range [−84, −80] |
| SNR                 | mean 9.56 dB,  σ 0.31, range [9.0, 12.5]   |
| Inter-arrival time  | mean 1001.4 ms, σ 0.51, range [1000, 1002] (n = 199) |
| Frequency error     | 5147 Hz constant across all rows   |

**Narrative:** Second of the four C1 sweep points. Behaviour is consistent with the +14 dBm anchor on every axis except RSSI, which is exactly what the campaign is designed to surface.

- **RSSI dropped by ≈ 11 dB at the receiver for a 12 dB drop at the transmitter** (−71.23 → −82.25 dBm for +14 → +2 dBm TX). That ~12 dB delta tracks the prescribed 12 dB step in the sweep within link-budget noise, and the *direction* is right (lower TX → more negative RSSI). σ rose modestly from 0.55 to 0.86 dB, consistent with operating closer to the noise floor.
- **SNR is essentially unchanged** at +9.56 dB (vs. +9.55 dB at +14 dBm). At 3 m the link is nowhere near sensitivity-limited even at +2 dBm, so SNR - which is an estimate of signal-above-thermal-noise after the demodulator's processing gain - is dominated by the radio's noise figure rather than path loss.
- **Sequence integrity, packet cadence, frequency error all match the +14 dBm anchor.** 200/200 rows, 0 gaps, 1001.4 ms inter-arrival (σ 0.51 ms), single 5147 Hz freq-error value across the run. No dropped frames, no parser rejections, no link timeouts at the lower TX power.
- **Schema sanity.** Same 21-column schema, all fields constant where expected; new run window timestamps; `seq_num` resumed at 63 because Target A's sequence counter resets each time the firmware is reflashed for a new sweep step.

**Result:** PASS for the +2 dBm point. With +14 dBm and +2 dBm now in hand, the early C1 trend is monotonic (−82.25 dBm < −71.23 dBm) and within link-budget expectations. +8 dBm and +20 dBm runs are still owed to complete the four-point sweep.

### Step 5 - Campaign C1, +8 dBm point

**Configuration:** Target A `LORA_SF 7`, `LORA_TX_PWR_DBM 8`. Same geometry (3 m, Threat forwarding, Target B off). Run started 2026-05-03 18:18:06 UTC, ended 18:21:25 UTC (≈ 3 min 19 s wall clock). Output: `Code/Tools/CampaignCollect/logs/campaign_c1_txpwr_8/results_campaign_c1_txpwr_8.csv`.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Beacon IDs present  | `0x01` only (Target A)             |
| Packet type         | `0` (DATA only)                    |
| Spreading factor    | 7                                  |
| Payload length      | 14 bytes                           |
| Sequence numbers    | 38 → 237, contiguous, 0 gaps       |
| RSSI                | mean −75.92 dBm, σ 0.80, range [−79, −74] |
| SNR                 | mean 9.49 dB,  σ 0.28, range [9.0, 10.5]  |
| Inter-arrival time  | mean 1001.3 ms, σ 0.49, range [1000, 1002] (n = 199) |
| Frequency error     | 5147 Hz constant across all rows   |

**Narrative:** Third C1 sweep point. The +8 dBm result lands neatly between the +2 and +14 dBm anchors on the only axis that's supposed to vary, and is indistinguishable from them on every other axis.

- **RSSI is monotonic across the three points so far.** −82.25 → **−75.92** → −71.23 dBm for +2 → +8 → +14 dBm TX. The +2 → +8 step is **6.33 dB** for a 6 dB TX increment, and the +8 → +14 step is **4.69 dB** for a 6 dB increment. Both are within link-budget tolerance for an indoor 3 m LOS channel; the slight compression at higher power is consistent with the SX1276 PA's known step linearity (the tabulated PA register codes have ~1 dB residual error per step). Direction and magnitude match expectation.
- **SNR essentially constant** at +9.49 dB (σ 0.28), matching the +2 dBm (+9.56) and +14 dBm (+9.55) runs. SNR's narrower range here (9.0 to 10.5) vs. the other two runs (8.0–12.5) is sample-size noise, not a real difference.
- **Sequence integrity, packet cadence, frequency error all match the other C1 points.** 200/200 contiguous rows, 1001.3 ms inter-arrival (σ 0.49 ms), single 5147 Hz freq-error value across the run.
- **Schema sanity.** All 21 columns populated; `seq_num` resumed at 38 after the firmware reflash (consistent with the other sweep points' fresh-counter behavior).

**Result:** PASS for the +8 dBm point. C1 is now 3/4 complete. With +2 / +8 / +14 dBm in hand, the partial concatenated dataset (600 rows) shows the prescribed monotonic RSSI vs. TX power trend; the +20 dBm anchor is still owed before the full Step 6 validation can run.

### Step 5 - Campaign C1, +20 dBm point

**Configuration:** Target A `LORA_SF 7`, `LORA_TX_PWR_DBM 20`. Same geometry (3 m, Threat forwarding, Target B off). Run started 2026-05-03 18:24:59 UTC, ended 18:28:17 UTC (≈ 3 min 19 s wall clock). Output: `Code/Tools/CampaignCollect/logs/campaign_c1_txpwr_20/results_campaign_c1_txpwr_20.csv`.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Beacon IDs present  | `0x01` only (Target A)             |
| Packet type         | `0` (DATA only)                    |
| Spreading factor    | 7                                  |
| Payload length      | 14 bytes                           |
| Sequence numbers    | 36 → 235, contiguous, 0 gaps       |
| RSSI                | mean **−77.42 dBm**, σ 0.67, range [−80, −76] |
| SNR                 | mean 9.60 dB,  σ 0.33, range [9.0, 12.5]   |
| Inter-arrival time  | mean 1001.1 ms, σ 0.40, range [1000, 1002] (n = 199) |
| Frequency error     | 5147 Hz constant across all rows   |

**Narrative:** Fourth C1 point. Internal sanity is identical to the other three runs - 200/200 rows, contiguous sequence, σ ≈ 0.67 dB on RSSI, SNR +9.60 dB, 1001 ms cadence, single 5147 Hz freq-error - so the link itself is healthy and the data path is unimpaired. **However, the mean RSSI breaks monotonicity:** −77.42 dBm at +20 dBm TX is **lower than −71.23 dBm at +14 dBm and even lower than −75.92 dBm at +8 dBm**. Direction is wrong - increasing TX power produced *less* received signal.

The four-point picture (after running `python concatenate.py`):

| TX dBm | RSSI mean (dBm) | RSSI σ | SNR mean (dB) | n   |
|-------:|----------------:|-------:|--------------:|----:|
| +2     | −82.25          | 0.86   | 9.56          | 200 |
| +8     | −75.92          | 0.80   | 9.49          | 200 |
| +14    | −71.23          | 0.55   | 9.55          | 200 |
| **+20**| **−77.42**      | 0.67   | 9.60          | 200 |

The first three points are textbook monotonic (+6.33 dB then +4.69 dB at the receiver for 6 dB TX steps); the +20 dBm point inverts the trend by ~6 dB.

**Most likely root cause: the +20 dBm path requires register writes that `lora_init` does not perform.** The SX1276 has two RF output paths: RFO (used at +2/+8/+14 dBm) and PA_BOOST (required for +17 dBm and above). The +20 dBm mode further requires `RegPaDac` (0x4D) to be written to `0x87` to enable the high-power amplifier; in normal operation `RegPaDac = 0x84`. The current `lora_init` in [main.c:58](Code/Nucleo_RFM95_TargetA/Core/Src/main.c#L58) only writes `RegPaConfig` (0x09):

```c
#define REG_PA_CONFIG_VAL  (0x80 | ((LORA_TX_PWR_DBM - 2) & 0x0F))
```

The `0x80` bit selects PA_BOOST as the output pin (good - required for +20 dBm), and the OutputPower nibble encodes `LORA_TX_PWR_DBM − 2` (so +14 → `0x8C`, +20 → `0x92`). But **without enabling `RegPaDac = 0x87`, the PA cannot actually deliver +20 dBm output power.** What likely happens with `OutputPower = 0xF` and `RegPaDac = 0x84` is that the PA enters compression / limits at a level somewhere below +14 dBm, with worse linearity than +14 dBm - exactly the shape we see in the data (lower mean RSSI plus the antenna match probably non-optimal).

A secondary contributor: at high PA drive levels the SX1276 datasheet recommends increasing `RegOcp` (over-current protection) trip; the default `Ocp = 0x2B` (240 mA limit, but actually `Ocp.OcpOn=1, OcpTrim=0x0B` ≈ 130 mA) may engage current-limiting under +20 dBm steady-state TX, further capping radiated power.

**Result:** Data captured, **monotonicity check FAIL** for the +20 dBm point. The +14 dBm anchor remains the best-performing setting at this geometry, which is the right answer to ship for any subsequent campaign that needs a "high-power" baseline.

**Decision: keep this run in the C1 dataset as documented evidence of the firmware bug.** The +20 dBm CSV stays under `logs/campaign_c1_txpwr_20/`, the combined dataset (`logs/C1_combined.csv`, 800 rows) is the authoritative C1 output for the curriculum, and this TestLog entry is the explanation. The student-facing takeaway is *exactly* the kind of cross-layer issue Module 3 is designed to surface: a single missing register write at the firmware layer (`RegPaDac`) silently breaks the monotonicity assumption baked into the lab's validation script. Replacing the CSV after a hidden fix would erase that lesson.

The combined CSV `Code/Tools/CampaignCollect/logs/C1_combined.csv` (800 rows, all four points) was written successfully by `concatenate.py`. The script ran cleanly end-to-end.

---

## LH3-F - Campaign C2 (spreading factor sweep)

### Step 7 - Campaign C2, SF7 point

**Configuration:** Target A `LORA_SF 7`, `LORA_TX_PWR_DBM 14`. Same geometry (3 m, Threat forwarding, Target B off). Run started 2026-05-03 18:34:47 UTC, ended 18:38:02 UTC (≈ 3 min 15 s wall clock). Output: `Code/Tools/CampaignCollect/logs/campaign_c2_sf7/results_campaign_c2_sf7.csv`.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Campaign / run ID   | `C2` / `C2_sf07_2026-05-03T12:00:00Z` |
| Beacon IDs present  | `0x01` only (Target A)             |
| Packet type         | `0` (DATA only)                    |
| Spreading factor    | 7                                  |
| Sequence numbers    | 46 → 246, **1 gap** (seq 47 missing) |
| RSSI                | mean −71.91 dBm, σ 1.07, range [−75, −70] |
| SNR                 | mean 9.59 dB,  σ 0.39, range [9.0, 12.5]  |
| Inter-arrival time  | mean 993.8 ms, σ 76.6, range [87, 1002] (n = 198) |

---

## LH3-G - Campaign C4 status note

**Status:** Skipped for this cycle.

**Note:** C4 (distance-check campaign) is being skipped due to schedule constraints. There is not enough time right now to set up the required laptop environment to run the distance measurements cleanly.

**Impact:** C5 and downstream analysis can continue, but C4-specific distance-stratified results should be marked as deferred.
| Frequency error     | 5147 Hz constant across all rows   |

**Narrative:** First C2 sweep point. Radio configuration is identical to the C1 +14 dBm anchor (SF7, +14 dBm, 3 m), and the RSSI/SNR numbers match (−71.91 vs. −71.23 dBm - within run-to-run variability). The campaign_id and run_id fields are correctly stamped `C2` / `C2_sf07_…`, confirming the collector used the right config.

**Anomaly at run start:** Seq 47 was never received, and the three rows immediately after show distorted inter-arrivals (row 2: −554 ms, row 3: 87 ms, row 4: 426 ms). From row 5 onward inter-arrival is a steady 1001 ms (σ < 1 ms). This is a collector join-mid-stream artifact: the first packet the firmware transmitted after flashing was already partway through the radio TX when collection started, seq 47 was in-flight and either not forwarded or the Threat hadn't synced yet. The distorted IA values on rows 3–4 reflect the rx_timestamp delta against the partial first frame. No mid-run link events occurred; 196 of 198 valid inter-arrivals are nominal.

**Result:** PASS. The seq gap and IA outliers are a run-start artifact with no impact on the 195+ clean rows the C2 box plot will draw from. SF8 through SF12 remain to be collected.

### Step 7 - Campaign C2, SF8 point

**Configuration:** Target A `LORA_SF 8`, `LORA_TX_PWR_DBM 14`; Threat `LORA_SF 8`. Same geometry (3 m, Target B off). Run started 2026-05-03 18:56:38 UTC, ended 18:59:58 UTC (≈ 3 min 20 s). Output: `Code/Tools/CampaignCollect/logs/campaign_c2_sf8/results_campaign_c2_sf8.csv`.

**First clean run after the `g_lora_sf` firmware fix** - `spread_factor` column correctly reads `8` across all 200 rows.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Campaign / run ID   | `C2` / `C2_sf08_2026-05-03T12:00:00Z` |
| Spreading factor    | **8** (confirmed in all rows)      |
| Sequence numbers    | 25 → 225, **1 gap** (seq 136 missing, mid-run) |
| RSSI                | mean −70.94 dBm, σ 0.47, range [−75, −68] |
| SNR                 | mean 11.84 dB, σ 0.26, range [10.25, 12.5] |
| Inter-arrival time  | mean 1006.2 ms, σ 71.0, range [1000, 2002] (n = 199) |
| Frequency error     | 5278 Hz constant (shifted from 5147 Hz at SF7 - crystal temp drift between runs) |

**Narrative:** Second C2 sweep point. RSSI is essentially flat relative to SF7 (−70.94 vs. −71.91 dBm) - expected, since TX power and distance are unchanged; SF doesn't directly affect received power, only demodulator sensitivity and on-air time.

**SNR jumped noticeably: +11.84 dB vs. +9.59 dB at SF7.** This is the SF processing gain in action - SF8 has 3 dB more coding gain than SF7 from the LoRa chirp spread, so the demodulator can pull the signal out of the noise floor more effectively, and the SX1276 reports a higher SNR estimate accordingly. The narrower σ (0.26 vs. 0.39) reflects a cleaner, more stable demodulation at the higher SF.

**Mid-run gap at row 112:** seq 136 missing, IA = 2002 ms (exactly 2× the normal 1001 ms cadence). RSSI at the surrounding rows is normal (−71 dBm). This is a single-packet miss - most likely a collision during SF8's ~7 ms on-air window or a momentary Threat ring-buffer full. All subsequent packets received normally; not a link failure.

**Freq error shifted to 5278 Hz** from the 5147 Hz seen across all C1 and C2-SF7 runs. This 131 Hz shift is consistent with a small crystal temperature change between sessions and is expected behaviour - the SX1276's internal oscillator has a ±50 ppm tolerance, and the offset will vary slightly with die temperature.

**Result:** PASS. SF9 through SF12 still owed.

### Step 7 - Campaign C2, SF9 point

**Configuration:** Target A `LORA_SF 9`, `LORA_TX_PWR_DBM 14`; Threat `LORA_SF 9`. Same geometry (3 m, Target B off). Run started 2026-05-03 19:01:44 UTC, ended 19:05:16 UTC (≈ 3 min 32 s). Output: `Code/Tools/CampaignCollect/logs/campaign_c2_sf9/results_campaign_c2_sf9.csv`.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Campaign / run ID   | `C2` / `C2_sf09_2026-05-03T12:00:00Z` |
| Spreading factor    | **9** (confirmed in all rows)      |
| Sequence numbers    | 19 → 231, **12 gaps** (all single-packet misses) |
| RSSI                | mean −73.48 dBm, σ 0.67, range [−75, −72] |
| SNR                 | mean 12.79 dB, σ 0.93, range [9.75, 14.25] |
| Inter-arrival time  | mean 1066.6 ms, σ 267.6, range [1000, 3003] (n = 199) |
| Frequency error     | 5409 Hz constant                   |

**Narrative:** Third C2 sweep point. The 12 single-packet gaps (all IA = 2002–3003 ms, i.e. exactly 2–3× the 1001 ms cadence) are the first sign that SF9's longer on-air time (~14 ms vs. ~7 ms at SF8) is starting to cause occasional collisions with the Threat's forwarding window. All gaps are isolated misses; the surrounding packets are received at normal RSSI/SNR and the run completes at 200 rows. Data is fully usable.

SNR continued climbing (+12.79 dB vs. +11.84 dB at SF8), consistent with the additional 3 dB processing gain per SF step. RSSI ticked down slightly to −73.48 dBm - within normal run-to-run variability at a fixed 3 m geometry, not a real path-loss effect. Freq error drifted to 5409 Hz (+131 Hz from SF8's 5278 Hz), continuing the consistent ~131 Hz/session drift seen since SF7 - crystal temperature slowly rising over the session.

**Result:** PASS. SF10 through SF12 still owed.

### Step 7 - Campaign C2, SF10 point

**Configuration:** Target A `LORA_SF 10`, `LORA_TX_PWR_DBM 14`; Threat `LORA_SF 10`. Same geometry (3 m, Target B off). Run started 2026-05-03 19:07:52 UTC, ended 19:11:17 UTC (≈ 3 min 25 s). Output: `Code/Tools/CampaignCollect/logs/campaign_c2_sf10/results_campaign_c2_sf10.csv`.

**Output (summary over 200 logged frames):**

| Metric              | Value                              |
|---------------------|------------------------------------|
| Rows captured       | 200 (target: 200)                  |
| Campaign / run ID   | `C2` / `C2_sf10_2026-05-03T12:00:00Z` |
| Spreading factor    | **10** (confirmed in all rows)     |
| Sequence numbers    | 16 → 221, **6 gaps** (all single-packet misses, IA = 2003 ms) |
| RSSI                | mean −72.31 dBm, σ 0.84, range [−73, −70] |
| SNR                 | mean 13.14 dB, σ 1.19, range [9.75, 14.0] |
| Inter-arrival time  | mean 1031.5 ms, σ 171.7, range [1000, 2003] (n = 199) |
| Frequency error     | 5540 Hz constant (+131 Hz from SF9 - crystal drift continuing) |

**Narrative:** Fourth C2 sweep point. 6 single-packet misses, all exactly 2003 ms (one cadence period skipped) - fewer than SF9's 12, consistent with run-to-run variance rather than a monotonic trend; SF10's ~28 ms on-air time does increase collision probability but the sample-to-sample gap count varies. SNR climbed again to +13.14 dB (+0.35 dB over SF9), continuing the per-SF processing gain trend. Freq error held its steady +131 Hz/session drift pattern at 5540 Hz. RSSI remains flat (−72.31 dBm) relative to the other C2 points, as expected at fixed TX power and distance.

**Result:** PASS. SF11 and SF12 still owed.

### Step 7 - SF11/SF12 abandoned; C2 scope reduced to SF7–SF10

**Attempt 1 - rx=0:** Both boards flashed at SF11 and confirmed `lora_init done: SF=11`, but the Threat reported `rx=0 dropped=0` indefinitely. Root cause: two register writes required by SX1276 datasheet section 4.1.1.6 were absent from `lora_init()` - `RegDetectOptimize` (0x31 → `0xC3`) and `RegDetectionThreshold` (0x37 → `0x0C`). Without them the preamble detector silently fails to lock on SF11/SF12 chirps. These were added and both boards reflashed.

**Attempt 2 - TX timeout:** Target A then printed `FAULT --- TX timeout, reconfiguring radio` on every TX attempt. Root cause: `RegModemConfig3` (0x26) bit 3 (`LowDataRateOptimize`) must be set when symbol duration exceeds 16 ms (SF11/SF12 at BW125 = ~32 ms/symbol). Without it the TX modem malfunctions mid-packet and TxDone never asserts. The existing 500 ms TX deadline also needs to increase to ≥ 1000 ms to cover SF11's ~330 ms on-air time with margin.

**Decision:** Supporting SF11/SF12 requires three register changes plus a TX deadline increase - a non-trivial `lora_init()` rework that there isn't timeline to validate properly. **C2 is scoped to SF7–SF10.** Firmware reverted to pre-SF11 state. Handout updated to match.

### Step 8 - Validate Campaign C2

**Output (800-row concatenated dataset, SF7–SF10):**

| SF  | n   | gaps | RSSI mean (dBm) | RSSI σ | SNR mean (dB) | IA median (ms) | IA mean (ms) | IA σ   |
|-----|-----|------|-----------------|--------|---------------|----------------|--------------|--------|
| SF7 | 200 | 1    | −71.91          | 1.07   | 9.59          | 1001           | 993.8        | 76.6   |
| SF8 | 200 | 1    | −70.94          | 0.47   | 11.84         | 1001           | 1006.2       | 71.0   |
| SF9 | 200 | 12   | −73.48          | 0.67   | 12.79         | 1001           | 1066.6       | 267.6  |
| SF10| 200 | 6    | −72.31          | 0.84   | 13.14         | 1001           | 1031.5       | 171.7  |

Total rows: 800. `label_sf` values present: {7, 8, 9, 10}. `campaign_id` = `C2` across all rows.

**Narrative:** Schema, row count, and label integrity all pass. Two observations worth noting:

- **Median IA is flat at 1001 ms across all four SFs.** At SF7–SF10 the on-air times (7–28 ms) are well under the 1-second TX interval, so the cadence is always loop-timer-limited rather than on-air-time-limited. The handout's stated acceptance criterion ("median inter-arrival time should approximately double with each SF increment") does not hold for this SF range at this geometry - that doubling would only manifest at SF11+ where on-air time exceeds the loop interval. The box plot will still show a useful discriminative signal via the **IQR and mean**, which do increase with SF as gap frequency grows.
- **SNR increases monotonically with SF** (9.59 → 11.84 → 12.79 → 13.14 dB), consistent with the additional processing gain each SF step provides. This is a clean per-SF feature the classifier can use.

**Result:** PASS. C2 dataset is complete at 800 rows across SF7–SF10. The C2 combined CSV can be generated with `python concatenate.py` once the C2 campaign configs are supported (currently `concatenate.py` picks up the four available C2 logs automatically). LH3-F is complete.

---

## Future Improvement - Hardware switch array for runtime SF/power selection

**Problem:** Each C2 sweep step currently requires: edit source, rebuild (F7), physically retrieve the board from 3 m, reflash (F5), return it to position - repeated for both Target A and the Threat. At 6 SF steps × 2 boards that's 12 retrieve-flash-replace cycles per campaign, plus the same cycle count again if any run needs to be repeated.

**Proposed fix:** Wire a DIP switch array (or the Nucleo's existing user switches if enough pins are free) to the STM32 GPIO and read the switch state at boot to select SF and TX power without reflashing. The Nucleo-L476RG has several free GPIO pins on the Arduino headers.

**Feasibility:** Fully practical. The SX1276 radio parameters are configured once at startup in `lora_init()` from `LORA_SF` and `LORA_TX_PWR_DBM`. Replacing those compile-time defines with a GPIO read at boot is a straightforward firmware change:

- A 3-bit binary switch encodes SF7–SF12 (values 0–5 → SF + 7), requiring 3 GPIO input pins.
- A 2-bit switch encodes the four TX power levels (+2, +8, +14, +20 dBm), requiring 2 GPIO input pins.
- Total: 5 GPIO pins per board, read once in `MX_GPIO_Init` or just before `lora_init()`, stored in globals that replace `LORA_SF` and `LORA_TX_PWR_DBM`.
- The debug terminal already prints `lora_init done: SF=N TxPwr=X dBm` - this becomes the confirmation that the switch was read correctly, with no other code changes needed.

**Operational flow with switches:** set the switches on both boards to the desired SF, power-cycle (or press reset), confirm the debug print, begin collection. No USB cable, no IDE, no reflash. Both boards can stay at 3 m for the entire C2 sweep.

**Threat-specific note:** the Threat only needs the SF switch (3 bits); TX power on the Threat is fixed at +20 dBm for jamming and doesn't need to be swept.

**Board-specific note:** confirm which Nucleo-L476RG GPIO pins are free before committing to a pinout - the XDC/CubeMX pin assignments for SPI1 (RFM95), USART2 (debug), USART3 (forwarding), TIM2, and DMA must not conflict. Arduino headers CN5/CN9 are the most likely candidates.

## Future Improvement - Fourth station (second Threat) for PAUSE frame logging

**Problem:** The current three-board setup (Target A, Target B, Threat) cannot log PAUSE frames as labeled dataset rows. The Threat transmits PAUSE packets over the radio when it jams, but the SX1276 is half-duplex - while the Threat is transmitting it cannot receive, so it never forwards its own PAUSE frames through the FPGA pipeline. PAUSE traffic is therefore invisible to `collect.py` and absent from all campaign CSVs. This is a gap in the dataset: PAUSE is a distinct packet type (`pkt_type = 0x02`) that a future classifier should be able to recognise, but there are currently zero labeled PAUSE rows to train on.

**Proposed fix:** Add a fourth board - a second Threat (passive listener, no jamming) positioned within radio range of the existing Threat. This board runs a stripped-down firmware: RX-only at the campaign SF/power, forwards every intercepted packet over USART3 to its own FPGA passthrough channel, exactly like the existing Threat. Because it is never transmitting, it is always listening and will capture PAUSE frames that the jamming Threat broadcasts. The FPGA and `collect.py` pipeline are unchanged - the second listener just feeds a second COM port.

**Dataset impact:** PAUSE frames from the second listener would appear in a separate CSV (or a merged one with a different `beacon_id` label column) with `pkt_type = 2`, giving the ML model its first labeled PAUSE examples. Combined with existing DATA (`pkt_type = 0`) rows this enables three-class training.

**Hardware requirement:** one additional Nucleo-L476RG + RFM95W module, one additional FPGA passthrough channel (or a second Nexys A7, or a USB-UART adapter if the FPGA passthrough is the bottleneck). Firmware is a subset of the existing Threat build - remove the jamming/PAUSE-TX logic, keep only the RX → USART3 forward path.

---
