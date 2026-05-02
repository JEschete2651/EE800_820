"""Raw byte capture from a serial port to a .bin file.

Reads bytes off a COM port and writes them verbatim to disk. Used to
produce the capture_clean.bin and capture_mixed.bin files required by
the Module 2 testbenches when no separate USB-to-UART adapter is
available and the Threat's USART3 stream is being passed through the
Nexys A7's onboard FT2232 (see ingest_top.vhd UART_RXD_OUT line).

LH2-A capture commands (run from the repo root, substitute your COM
port for COM7):

    Clean capture (no button presses, DATA + ACK only):
        python "Code/Tools/RawCapture/raw_capture.py" COM7 115200 "Code/ingest_top/data/capture_clean.bin" --frames 1500

    Mixed capture (hold Threat B1 for ~5s about 30s into the run so
    the file contains DATA, ACK, AND PAUSE frames):
        python "Code/Tools/RawCapture/raw_capture.py" COM7 115200 "Code/ingest_top/data/capture_mixed.bin" --frames 1500

Usage:
    python raw_capture.py <port> <baud> <out_bin> [--frames N | --seconds S]

Stops after N start delimiters seen OR S seconds, whichever comes first.
Prints a one-line progress update every 100 frames.
"""
import argparse
import sys
import time
from pathlib import Path

import serial


FRAME_LEN = 43
START_DELIM = 0x7E


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("baud", type=int)
    ap.add_argument("out_bin", type=Path)
    ap.add_argument("--frames", type=int, default=2000,
                    help="stop after this many start-delimiters seen (default 2000)")
    ap.add_argument("--seconds", type=float, default=1800.0,
                    help="hard timeout in seconds (default 30 min)")
    args = ap.parse_args()

    print(f"Opening {args.port} @ {args.baud} 8N1")
    ser = serial.Serial(args.port, args.baud, timeout=1.0)

    frames = 0
    bytes_written = 0
    t_start = time.monotonic()
    deadline = t_start + args.seconds

    with args.out_bin.open("wb") as f:
        while frames < args.frames and time.monotonic() < deadline:
            chunk = ser.read(256)
            if not chunk:
                continue
            f.write(chunk)
            bytes_written += len(chunk)
            frames += chunk.count(START_DELIM.to_bytes(1, "little"))
            if frames and frames % 100 == 0:
                elapsed = time.monotonic() - t_start
                print(f"  {frames} start delimiters / {bytes_written} bytes / {elapsed:.1f}s",
                      end="\r")

    elapsed = time.monotonic() - t_start
    print()
    print(f"Wrote {bytes_written} bytes ({frames} start delimiters) "
          f"to {args.out_bin} in {elapsed:.1f}s")
    ser.close()


if __name__ == "__main__":
    sys.exit(main())
