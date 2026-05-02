# EE800/820 Test Log

Running record of validation runs across the lab handouts. Each entry captures the handout step under test, the raw output, and a short narrative on what the result means.

---

## LH1-H — End-to-end ingestion (Module 1 capstone)

### Step 5 — Live ingestion run

**Output (seven-segment display):**
- Right two digits alternated `01` / `02` matching live Beacon IDs from Target A and Target B.
- Left two digits incremented as a 16-bit frame counter (low byte) at roughly 2 Hz.
- LED[0] flickered rapidly (rx_strobe), LED[1] pulsed at ~1 Hz cadence (new_frame).

**Narrative:** Initial run after programming the LH1-H bitstream. The right two digits behaved correctly. The left counter, however, only incremented when the Threat board was reset. Investigation traced the failure to the Threat firmware: the USART3 TX path completed exactly one DMA transfer per board reset and then stalled forever. Root cause was the missing `USART3_IRQn` NVIC enable in CubeMX — `HAL_UART_Transmit_DMA` waits on the USART Transmission Complete interrupt to clear `tx_busy`, and without the NVIC line that callback never fired. The captured serial logs corroborated this: every `# stats:` line on the Threat showed `dropped = rx - 1`, with only one frame ever escaping per Threat boot.

**Resolution:** Enable USART3 global interrupt in CubeMX → regenerate code. Documentation updated:
- LH1-C Step 1.6 amended to include the NVIC enable instruction (was missing).
- LH1-C now matches the format of Steps 1.5 (EXTI) and 1.7 (TIM2).

**After fix:** seg7 alternated `01`/`02` at full ~2 Hz cadence as designed.

---

## LH2-A — Module 2 project orientation, FPGA passthrough, capture set

### Step 4 — USB-UART passthrough modification

**Output:** new `ingest_top.vhd` adds the `UART_RXD_OUT` port and a single passthrough assignment routing `uart_rx_pin` directly to the Nexys A7's onboard FT2232 USB-UART. XDC entry for pin `D4` uncommented. Re-synthesis, implementation, and bitstream generation completed with zero errors and timing slack remained positive (WNS ≥ 0, WHS ≥ 0).

**Narrative:** Course originally required a separate USB-to-UART adapter to record the Threat's USART3 stream for Module 2 testbenches. Adapter was not on hand. The Nexys A7's FT2232 already exposes a virtual COM port on the same USB cable used to program the board, and pin D4 is wired to the FPGA-to-host RX direction of that UART. Both ends are 115200 8N1, so a direct wire from `uart_rx_pin` to `UART_RXD_OUT` echoes the byte stream verbatim with no re-serialization. The seven-segment display and frame detector continue to operate unchanged — the passthrough is purely additive. After programming the new bitstream, the host enumerated the FPGA as a new COM port.

### Step 6.1 — Clean capture (`capture_clean.bin`)

**Command:** `python "Code/Tools/RawCapture/raw_capture.py" COM7 115200 "Code/ingest_top/data/capture_clean.bin" --frames 1500`

**Output:** 62952 bytes written, 1500 start delimiters seen. Capture rate was steady at ~2 frames per second (DATA + ACK). No button presses during this run.

**Narrative:** First confirmation that the passthrough path actually delivers a usable byte stream to the host. Frame count and file size both match expectation for ~1500 × 43-byte frames with a small partial-frame leader. Stream content is the radio ping-pong only, no PAUSE traffic.

### Step 6.2 — Mixed capture (`capture_mixed.bin`)

**Command:** `python "Code/Tools/RawCapture/raw_capture.py" COM7 115200 "Code/ingest_top/data/capture_mixed.bin" --frames 1500`

**Output:** 63167 bytes written, 1500 start delimiters seen. Approximately 30 seconds into the recording the Threat's B1 button was held for ~5 seconds; during the hold the seg7 froze on the last beacon ID and the radio ping-pong stalled. After release, traffic and the seg7 alternation resumed normally.

**Narrative:** The original handout claimed PAUSE frames would appear at the FPGA as `FF` on the seg7. Code review of the Threat firmware showed PAUSE frames are *transmitted* by the Threat on the radio but never *received* by it (the SX1276 is half-duplex shadowed during its own TX), so PAUSE frames never enter the USART3 forwarding path. The mixed capture therefore contains only DATA + ACK plus a ~500 ms gap during the button hold. The gap is still useful: it exercises the Module 2 parser's re-sync logic in LH2-G's end-to-end testbench. LH2-A handout was corrected to describe the actual behavior.

---

## LH2-B — UART receiver with oversampling

### Step 4 — Unit testbench `tb_uart_rx`

**Output (Tcl console after `run 1 ms`):**
```
Note: tb_uart_rx PASS
Time: 287900 ns  Iteration: 0  Process: /tb_uart_rx/line__58
$finish called at time : 287900 ns
```

**Narrative:** Sends a single `0xA5` byte at 115200 baud, expects exactly one `rx_strobe` pulse with `rx_data = 0xA5`. Initial run hit two preventable issues:

1. **`to_hstring(std_logic_vector)` not resolved by xsim** under the default VHDL-93 mode. Replaced with a local `slv_to_hex` helper function. Both the on-disk testbench and the LH2-B handout listing were updated.

2. **`run 1 ms` issued twice** in quick succession produced a spurious second `rx_strobe`, tripping the assertion. The first `run` reaches `std.env.finish` and prints PASS, but xsim does not actually exit on `finish` — it stays loaded with state. A second `run` then re-entered the stimulus and generated another byte. Single `run 1 ms` per simulation start is the correct usage.

After both fixes, single-byte unit test passed cleanly at 287.9 µs simulated time. Module 2 `uart_rx` correctly recovers a single byte from a bit-banged 115200 8N1 stream.

### Step 5 — Regression testbench `tb_uart_rx_regression`

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

## LH2-C — Byte FIFO widened from 16 to 64

### Step 4 — Unit testbench `tb_byte_fifo`

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

### Step 5 — Overflow stress testbench `tb_byte_fifo_overflow`

**Output (Tcl console after `run 5 us`):**
```
Note: tb_byte_fifo_overflow PASS
Time: 1595 ns  Iteration: 0  Process: /tb_byte_fifo_overflow/line__30
$finish called at time : 1595 ns
```

**Narrative:** Wrote 65 bytes back-to-back with no reads. The FIFO held at depth 64, the `full` flag first asserted on write index 64 (the 65th attempt), and the 65th write was correctly dropped without corrupting pointers or count. After a full reset, both `empty` and not-`full` returned cleanly. PASS at 1.6 µs simulated.

This confirms the back-pressure behavior the wider FIFO needs once the LH2-D `pkt_parser` introduces transient stalls during CRC computation. With a 64-deep buffer and continuous-rate UART input (~12 µs per byte at 115200 baud after framing), the FIFO can absorb up to ~750 µs of parser stall, comfortably more than any realistic CRC-related back-pressure window.

---

## LH2-D — Frame detector replaced by `pkt_parser`

### Step 5 — Parser unit testbench `tb_pkt_parser`

**Output (Tcl console after `run 20 us`):**
```
Note: tb_pkt_parser PASS
Time: 5675 ns  Iteration: 0  Process: /tb_pkt_parser/line__92
$finish called at time : 5675 ns
```

**Narrative:** Three-frame stimulus driven through a behavioral byte source: a valid frame with Beacon ID `0x01`, a frame with a bad length byte (`0x30` instead of `0x29`), and a valid frame with Beacon ID `0x02`. Parser correctly emitted two `frame_valid` pulses with the right Beacon IDs in `payload(23 downto 16)`, and one `frame_reject` pulse on the bad-length frame. PASS at 5.7 µs simulated.

This is the first test that exercises the full `S_HUNT → S_REQ → S_WAIT → S_CAPTURE` cycle including the registered FIFO-read latency, the length-byte gate (which `frame_detector` did not have), and the `S_REJECT` path. Beacon ID lands at radio packet byte 2 = frame offset 12 = `payload(23 downto 16)` in the packed payload vector — same indexing math the LH2-D `ingest_top` uses to drive the seg7.

CRC verification is not exercised yet (this handout only checks framing and length); LH2-E adds CRC-8 and CRC-16 engines and extends `pkt_parser` to gate `frame_valid` on CRC match.

---

## LH2-E — Hardware CRC-8 and CRC-16 verification

### Step 4 — Golden-vector testbench `tb_crc`

**Output (Tcl console after `run 5 us`):**
```
Note: tb_crc PASS
Time: 435 ns  Iteration: 0  Process: /tb_crc/line__53
$finish called at time : 435 ns
```

**Narrative:** Streamed the ASCII string "123456789" (the canonical CRC check input) through both engines simultaneously and verified the standard test vectors:

- **CRC-8/ITU** (poly 0x07, init 0x00): expected and got `0xF4`
- **CRC-16/CCITT-FALSE** (poly 0x1021, init 0xFFFF): expected and got `0x29B1`

PASS at 435 ns simulated time — one cycle per byte of input plus pipeline reset and post-loop settle. The bit-serial unrolled `update8`/`update16` functions both work correctly; their VHDL `for` loops collapse to combinational XOR trees in synthesis.

Pre-applied the LH2-B fix this time around: replaced `to_hstring(crc8)` and `to_hstring(crc16)` in the assertion-failure messages with local `slv_to_hex8`/`slv_to_hex16` helpers, since Vivado xsim under VHDL-93 mode does not always resolve `to_hstring` for `std_logic_vector`. The handout listing was also updated so future students inherit the working version.

These engines are now wired into the LH2-E `pkt_parser` rewrite. CRC-8 covers frame bytes 1–41 (the trailing byte 42 is the captured CRC); CRC-16 covers radio bytes 0–29 = frame bytes 10–39 (radio bytes 30–31 = frame bytes 40–41 are the captured CRC, with the high byte first per LH1-G's `build_forwarding_frame`). A frame is `frame_valid` only if length, CRC-8, and CRC-16 all check out; otherwise `frame_reject` fires.

---

## LH2-F — Feature extraction and per-Beacon-ID BRAM

### Step 5 — Feature extractor unit testbench `tb_feature_extract`

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

**Bug found and fixed before PASS:** the first attempt failed with row-0x01 frame_count = 6 (all six frames hit row 0x01). Debug `report` statements inside the FSM showed the beacons were extracted correctly (1,1,1,2,2,FF) but every fresh read of an as-yet-unwritten BRAM row was returning a stale non-zero value. Root cause: the original `feature_bram.vhd` had no reset clause — `mem` was initialized via the VHDL signal-declaration default `(others => (others => '0'))` and the registered read outputs had no init at all. Vivado xsim apparently latched stale values from the testbench's signal-driver lifetime and surfaced them as the read result before the first write to a given address.

The fix added an `rst_n` input to `feature_bram` and a synchronous-reset clause that explicitly clears `mem`, `rd_data_a`, and `rd_data_b` while reset is asserted. With clean reset behavior the very first read of any address returns 0 deterministically, the read-modify-write sequence increments correctly, and per-beacon counts come out right. `ingest_top.vhd` was updated to wire `rst_n => rst_n` on `u_bram`. The LH2-F handout listings (`feature_bram.vhd`, the `u_bram` instantiations in both `ingest_top` and the testbench) were updated to match.

This is the broadest pipeline test so far: `pkt_parser` → `feature_extract` → `feature_bram` → host port. Module 2 hardware now correctly accumulates per-Beacon-ID statistics and stores the feature vector at the address determined by the radio packet's sender field. The LH2-G end-to-end testbench will replay the recorded captures through this same pipeline.

---
