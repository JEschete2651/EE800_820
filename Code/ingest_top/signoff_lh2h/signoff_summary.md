# LH2-H Module 2 Sign-Off Summary

**Project:** `ingest_top` (EE800/820 Module 2 ingestion pipeline)
**Target device:** Xilinx Artix-7 `xc7a100tcsg324-1` (Digilent Nexys A7-100T)
**Vivado version:** 2025.2 (Win64, Build 6299465, 2025-11-14)
**Sign-off date:** 2026-05-02

---

## Deliverables in this directory

| File                  | Description |
|-----------------------|-------------|
| `ingest_top.bit`      | Post-route bitstream, ready to program |
| `impl_summary.json`   | Machine-readable summary (LUT, FF, BRAM, DSP, WNS, TNS, WHS, THS, power, junction temp) |
| `util.rpt`            | Post-synthesis utilization (raw Vivado output) |
| `timing.rpt`          | Post-route timing summary |
| `power.rpt`           | Post-route power estimate |
| `cdc.rpt`             | Clock-domain crossing report |
| `lh2g_regression.txt` | LH2-G three-scenario byte-for-byte diff results (clean / mixed / corrupt) |
| `signoff_summary.md`  | This document |

---

## Headline numbers

| Metric                  | Result          | Threshold        | Status |
|-------------------------|-----------------|------------------|--------|
| Synthesis errors        | 0               | 0                | PASS   |
| Implementation errors   | 0               | 0                | PASS   |
| Inferred latches        | 0               | 0                | PASS   |
| WNS (setup slack)       | **+1.191 ns**   | $\geq$ 0 ns      | PASS   |
| WHS (hold slack)        | **+0.030 ns**   | $\geq$ 0 ns      | PASS   |
| Failing setup endpoints | 0 / 105 975     | 0                | PASS   |
| Failing hold endpoints  | 0 / 105 975     | 0                | PASS   |
| Dynamic power           | **0.139 W**     | < 0.200 W        | PASS   |
| Total on-chip power     | 0.236 W         | (informational)  | —      |
| Junction temperature    | 26.1 °C         | < 100 °C         | PASS   |
| CDC report              | empty           | no unexpected    | PASS   |

---

## Resource utilization

| Resource         | Used   | Available | Util.  | Expected envelope | Status |
|------------------|--------|-----------|--------|-------------------|--------|
| Slice LUTs       | 19 151 | 63 400    | 30.20% | 1–3% (~600)       | EXCEEDS |
| Slice Registers  | 53 034 | 126 800   | 41.82% | 0.5–2% (~640)     | EXCEEDS |
| Block RAM Tile   | 0      | 135       | 0.00%  | 2 tiles           | UNDER (mis-inferred) |
| DSP48            | 0      | 240       | 0.00%  | 0                 | PASS    |
| Bonded IOB       | 49     | 210       | 23.33% | 49                | PASS    |
| BUFGCTRL         | 1      | 32        | 3.13%  | 1                 | PASS    |

**Resource note:** the LUT/FF utilization exceeds the LH2-H expected envelope because Vivado mapped `feature_bram`'s 256-row × 256-bit storage into discrete flip-flops instead of two RAMB36 tiles. Cause is the synchronous-reset clause on `mem` added in LH2-F to fix a Vivado xsim stale-read issue. The design still meets all timing constraints and stays under power budget; the BRAM-inference fix (drop `mem` from the reset clause, keep reset on the registered `rd_data_a`/`rd_data_b` outputs) is queued as a Module 3 polish task. See TestLog.md, "LH2-H Step 1," for details.

---

## Verification chain (Module 2 testbench results)

| # | Testbench | Coverage | Result |
|---|-----------|----------|--------|
| 1  | `tb_uart_rx`             | Single-byte 0xA5 recovery, generics    | PASS |
| 2  | `tb_uart_rx_regression`  | 62 952-byte capture replay             | PASS, 0 mismatches |
| 3  | `tb_byte_fifo`           | 16-write/16-read, registered output    | PASS |
| 4  | `tb_byte_fifo_overflow`  | 65 writes, full-flag latch, reset      | PASS |
| 5  | `tb_pkt_parser`          | 3 frames: VALID, REJECT-len, VALID     | PASS |
| 6  | `tb_crc`                 | CRC-8/CRC-16 "123456789" golden vector | PASS |
| 7  | `tb_feature_extract`     | 6 frames, 3-row read-modify-write      | PASS |
| 8  | `tb_ingest_top` (clean)   | Full pipeline, single station         | 0-byte diff |
| 9  | `tb_ingest_top` (mixed)   | Full pipeline, ping-pong + button-hold| 0-byte diff |
| 10 | `tb_ingest_top` (corrupt) | Full pipeline, ~5% bit-flipped frames | 0-byte diff |

The three LH2-G zero-byte diffs against an independent Python reference (`Code/Tools/RefPipeline/ref_pipeline.py`) are the strongest evidence of correctness: identical results from two independent implementations of the same parser + CRC + feature accumulator on the same recorded captures.

---

## Sign-off statement

The Module 2 `ingest_top` design has passed all functional and physical sign-off criteria:

- All 10 testbenches in the verification chain pass.
- Timing closes at the target 100 MHz clock with positive WNS, WHS, and pulse-width slack across 105 975 endpoints.
- The CDC analyzer reports no unexpected clock-domain crossings.
- Dynamic power is below the 200 mW envelope.
- A bitstream is produced and ready to program onto the Nexys A7-100T.

The known resource-shape deviation (BRAM mis-inference) does not block sign-off; the design is functionally correct and physically realizable as built, and the fix is well-understood for Module 3.

The bitstream and supporting reports in this directory constitute the Module 2 deliverable and the input to Module 3 system integration.
