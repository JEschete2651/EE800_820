# EE800/820 Explanations Log

Running record of conceptual explanations and "wait, why did we do that?" moments. Each entry has a topic, the question, and the answer in plain language. Skim by heading to find the thing you forgot.

---

## The three-board chain (Target A, Target B, Threat) and the FPGA

**Question:** Who talks to whom, and which direction does data flow?

**Answer:**
```
Target A/B  --radio-->  Threat (STM32)  --PC4 wire-->  FPGA  --D4 (USB-UART)-->  Host PC
                                          (in)                  (out)
```

- **Targets A and B** ping-pong DATA and ACK packets at ~1 Hz over LoRa. A is the initiator, B is the responder.
- **Threat** is a third Nucleo board sitting in continuous-receive mode. It hears every radio packet, timestamps it, and forwards a 43-byte frame out its USART3 TX pin (PC4) at 115200 baud.
- **FPGA** receives those bytes on PMOD pin C17 (`uart_rx_pin`), parses them, and drives the seg7 display.
- **Host PC** sees the same byte stream because the FPGA also echoes it out pin D4 (`UART_RXD_OUT`) → onboard FT2232 chip → same USB cable that programs the board → COM port on the PC.

When you held the Threat's button, the Threat *transmitted* PAUSE frames on the radio. It did not receive its own transmissions (half-duplex shadowing), so no PAUSE bytes ever reached the FPGA. The button hold caused a *gap* in the captured stream, not new bytes.

---

## Why `UART_RXD_OUT` is wired even though we don't "transmit" anything

**Question:** Why does the FPGA have a UART output to the host PC?

**Answer:** "Output" here means FPGA → host PC, which is how `raw_capture.py` records the `.bin` files. We don't have a separate USB-to-UART adapter, so the FPGA passively forwards the Threat's incoming byte stream out its onboard USB-UART pin so the host can see it. The FPGA is not generating data — it's a wire.

The line in `ingest_top.vhd` is literally:
```vhdl
UART_RXD_OUT <= uart_rx_pin;
```
Zero logic, zero LUTs. Just a routing wire. Both ends are 115200 8N1 so no re-serialization is needed.

If we ever bought a USB-to-UART adapter and wired it directly to the Threat's PC4, this passthrough wouldn't be needed. But we didn't, so it is.


---

## Why `tx_busy` got stuck on the Threat (the USART3 NVIC bug)

**Question:** Why was the Threat dropping ~99.997% of its packets, and why did pressing the Threat's reset button let exactly one frame through each time?

**Answer:** `HAL_UART_Transmit_DMA` does not consider the transfer "complete" when DMA finishes — it waits for the USART's Transmission Complete (TC) interrupt to confirm the last byte has clocked out the wire. The TC interrupt only fires if `USART3_IRQn` is enabled in the NVIC.

CubeMX's NVIC settings tab had USART3's global interrupt unchecked. So:

1. First DMA transmit after boot: works. Bytes hit the wire. The TC interrupt is masked, so `HAL_UART_TxCpltCallback` never runs. `tx_busy` stays at 1 forever.
2. Every subsequent attempt to forward a frame: spins on `while (tx_busy)` for 10 ms, gives up, increments `dropped`.

Pressing the Threat reset zeros all of RAM (including `tx_busy`), letting exactly one more frame escape before the cycle repeats. That matched perfectly: `dropped = rx - 1` in every captured Threat USART2 status line.

Fix: enable USART3 global interrupt in CubeMX → regenerate code. LH1-C Step 1.6 was missing this instruction; the handout was patched.

---

## Why `run 1 ms` once but not twice in xsim

**Question:** Why does the unit testbench fail when you run `run 1 ms` a second time?

**Answer:** xsim does not exit on `std.env.finish`. It prints the message, calls finish, but stays loaded with simulator state. When you issue another `run` command, the stimulus process re-enters from where it was suspended — but the assertion logic has already counted strobes from the first byte. A second byte, a second strobe, and the "expected exactly one rx_strobe" assertion trips.

Rule of thumb: one `run <time>` per launch of the simulator. If you need to re-run, click **Restart** in the simulator toolbar (or close and re-launch the simulation), then issue a fresh `run`.

---

## Why `tb_uart_rx_regression` needs `run 6 sec` not `run 200 ms`

**Question:** Why did the regression sit idle when we asked for `run 200 ms`?

**Answer:** The regression bit-bangs every byte of `capture_clean.bin` through the UART receiver. At 115200 baud, each byte takes ~87 µs. 62952 bytes × 87 µs ≈ **5.48 simulated seconds**. 200 ms simulated isn't enough — the stimulus process is mid-stream when xsim runs out of time, and just sits there. xsim's process drops to 0% CPU because nothing is queued.

`run 6 sec` lets the stimulus process reach end-of-file, the assertions fire, `std.env.finish` ends the sim. Wall-clock cost is around 4.5 minutes (xsim simulates ~18 ms per wall-clock second on a typical laptop for this kind of bit-banged stimulus).

---

## Why both COM port labels and physical board labels matter

**Question:** I had COM3, COM4, COM5 labeled A/B/Threat in my head, but the printf signatures on the consoles disagreed with my labels. Was something wrong?

**Answer:** No. Three independent things to keep straight:

- **COM port number** = what Windows assigned to a USB device. Arbitrary; can change between reboots.
- **Physical board** = which Nucleo is in your hand.
- **Firmware role** = which `.elf` was flashed (initiator A, responder B, or Threat).

The protocol works as long as the physical-board-to-firmware mapping is correct. COM port labels are just for your convenience when reading logs. If COM3 prints the responder's `RX DATA seq=N` lines, that means COM3 is plugged into whichever board has Target B's firmware on it — the COM number itself doesn't matter.

You can verify mapping by reading each console's boot banner: `Target A initiator ready`, `Target B responder ready`, or `Threat (Interceptor, ID=0xFF) ready`.

---

## Why the FIFO was widened from 16 to 64 in LH2-C

**Question:** The LH1-H 16-deep FIFO worked fine. Why bump to 64?

**Answer:** LH1-H's `frame_detector` drains continuously (one byte per FIFO read, immediately), so 16 entries is plenty. LH2-D's `pkt_parser` adds CRC computation and a reject path, which introduces transient stalls — a few cycles here, a frame-time there. Once you compose `pkt_parser` with the feature extractor in LH2-F, parser back-pressure can hold the FIFO read enable low for hundreds of microseconds.

Math: at 115200 baud the UART produces ~12 µs per byte. A 64-deep FIFO gives ~750 µs of buffering against parser stalls. A 16-deep FIFO would only give ~190 µs, which isn't enough margin once the production parser is in.

LUT cost is ~8 LUTs for the wider RAM (distributed RAM, not BRAM — we save the BRAM tiles for the feature memory in LH2-F). Effectively free against the 63 400-LUT budget on the 100T.

---

## Why `feature_bram` needs an explicit `rst_n` even though `mem` is already initialized

**Question:** The signal declaration `signal mem : mem_t := (others => (others => '0'));` already gives every byte a value of zero at simulation start. Why does the BRAM also need a synchronous reset that clears `mem` again?

**Answer:** Default values on `signal mem` work in *some* simulators and *most* synthesis tools, but Vivado xsim treats them inconsistently. In LH2-F's first run, every fresh read of an as-yet-unwritten BRAM row returned a stale non-zero value (the value most recently written to a *different* row), even though `mem` was supposedly all-zero. Adding `rst_n` and an explicit `if rst_n='0' then mem <= ...` clause forces all 256 rows to clear at a known time, the registered read outputs to clear, and the BRAM process to be idle through the testbench reset window.

After the fix, the very first read of any address is deterministically 0 and the read-modify-write sequence increments cleanly: 0→1→2 for three frames of beacon 0x01, 0→1 for two frames of beacon 0x02, 0 for one frame of beacon 0xFF.

Practical rule: **anywhere a BRAM-style signal array has a meaningful initial state, declare an explicit reset that establishes it in clocked logic** rather than relying on the signal-declaration default. Synthesis usually tolerates either; simulation tools (especially Vivado xsim) do not.

---
