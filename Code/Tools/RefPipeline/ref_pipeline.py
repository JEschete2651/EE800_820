"""Module 2 reference pipeline.

Produces the same per-row hex dump that tb_ingest_top.vhd writes to
ingest_top/data/dump_*.txt. Diff the two files for a byte-for-byte
regression of the full Module 2 hardware pipeline.

LH2-G usage (run from the repo root):

    Generate the corrupted capture and its reference dump in one step:
        python "Code/Tools/RefPipeline/ref_pipeline.py" \
            --corrupt-from "Code/ingest_top/data/capture_mixed.bin" \
            --capture "Code/ingest_top/data/capture_corrupt.bin" \
            --out "Code/ingest_top/data/ref_corrupt.txt"

    Generate the clean and mixed reference dumps:
        python "Code/Tools/RefPipeline/ref_pipeline.py" \
            --capture "Code/ingest_top/data/capture_clean.bin" \
            --out "Code/ingest_top/data/ref_clean.txt"
        python "Code/Tools/RefPipeline/ref_pipeline.py" \
            --capture "Code/ingest_top/data/capture_mixed.bin" \
            --out "Code/ingest_top/data/ref_mixed.txt"
"""
import argparse
import struct
import random
import pathlib

CRC8_POLY  = 0x07
CRC16_POLY = 0x1021


def crc8(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ CRC8_POLY) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def crc16(data: bytes) -> int:
    c = 0xFFFF
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ CRC16_POLY) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def corrupt(src: pathlib.Path, dst: pathlib.Path,
            frac: float = 0.05, seed: int = 1):
    """Flip one random bit in roughly `frac` of frames."""
    rng  = random.Random(seed)
    data = bytearray(src.read_bytes())
    i = 0
    while i + 43 <= len(data):
        if data[i] == 0x7E and data[i + 1] == 0x29:
            if rng.random() < frac:
                off = rng.randrange(2, 42)         # don't touch delimiter or length
                bit = 1 << rng.randrange(8)
                data[i + off] ^= bit
            i += 43
        else:
            i += 1
    dst.write_bytes(data)


def parse(stream: bytes):
    """Yield 43-byte frames whose CRCs both check out."""
    i = 0
    while i + 43 <= len(stream):
        if stream[i] != 0x7E or stream[i + 1] != 0x29:
            i += 1
            continue
        frame = stream[i:i + 43]
        if crc8(frame[1:42]) != frame[42]:
            i += 43
            continue
        embedded = (frame[40] << 8) | frame[41]
        if crc16(frame[10:40]) != embedded:
            i += 43
            continue
        yield frame
        i += 43


def s8(b: int)  -> int: return b - 256 if b >= 128 else b
def s16(v: int) -> int: return v - 0x10000 if v >= 0x8000 else v


def process(stream: bytes):
    rows = {b: bytearray(32) for b in range(256)}
    state = {}                                     # beacon -> (ts_last, rssi_last, count)
    for f in parse(stream):
        ts   = struct.unpack("<I", f[2:6])[0]
        rssi = s8(f[6])
        snr  = s8(f[7])
        radio    = f[10:42]
        beacon   = radio[2]
        mod_code = radio[6]
        sf       = radio[7]
        pkt_type = mod_code & 0x03
        mod_kind = mod_code >> 2
        old_ts, old_rssi, old_count = state.get(beacon, (0, 0, 0))
        new_count = old_count + 1
        inter_arr = (ts - old_ts) & 0xFFFFFFFF
        rssi_delt = (rssi - old_rssi) & 0xFFFFFFFF
        priority  = ((rssi << 2) + snr + new_count) & 0xFFFFFFFF
        tgt = radio[13] if pkt_type == 2 else 0    # LH1-G buf[13]
        dur = radio[14] if pkt_type == 2 else 0    # LH1-G buf[14]
        v = bytearray(32)
        v[0]   = beacon
        v[1]   = mod_kind
        v[2]   = sf
        v[3]   = pkt_type
        struct.pack_into("<h", v, 4,  rssi)
        struct.pack_into("<h", v, 6,  snr)
        struct.pack_into("<I", v, 8,  new_count)
        struct.pack_into("<I", v, 12, ts)
        struct.pack_into("<I", v, 16, inter_arr)
        struct.pack_into("<I", v, 20, rssi_delt)
        struct.pack_into("<I", v, 24, priority)
        v[28] = tgt
        v[29] = dur
        rows[beacon] = v
        state[beacon] = (ts, rssi, new_count)
    return rows


def dump(rows, path: pathlib.Path):
    with path.open("w") as f:
        for r in range(256):
            # Hardware dump prints byte 31 first (MSB of the packed 256-bit
            # vector is byte 31). Match that ordering exactly.
            hex_be = rows[r][::-1].hex().upper()
            f.write(f"ROW {r:02X} {hex_be}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--corrupt-from")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    cap = pathlib.Path(args.capture)
    if args.corrupt_from:
        corrupt(pathlib.Path(args.corrupt_from), cap, seed=args.seed)
    rows = process(cap.read_bytes())
    dump(rows, pathlib.Path(args.out))
    print(f"wrote {args.out}")
