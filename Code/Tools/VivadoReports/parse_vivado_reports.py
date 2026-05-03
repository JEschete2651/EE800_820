"""LH2-H Step 6 --- Parse Vivado implementation reports into impl_summary.json.

Reads the post-implementation utilization, timing, and power reports that
Vivado writes into ingest_top.runs/impl_1/ and extracts the LUT, FF, BRAM,
DSP, WNS, TNS, dynamic power, and total power numbers. Writes the result
to ingest_top/impl_summary.json so the Module 5 spec-table script (and
the Table~2 row in the final report) can read it directly.

Run from the repo root:
    python "Code/Tools/VivadoReports/parse_vivado_reports.py"
"""
import json
import re
import sys
from pathlib import Path


REPO_ROOT  = Path(__file__).resolve().parents[3]
IMPL_DIR   = REPO_ROOT / "Code" / "ingest_top" / "ingest_top.runs" / "impl_1"
SYNTH_DIR  = REPO_ROOT / "Code" / "ingest_top" / "ingest_top.runs" / "synth_1"
OUT_PATH   = REPO_ROOT / "Code" / "ingest_top" / "impl_summary.json"

# Vivado's default report filenames in the .runs/ subtree.
UTIL_RPT_IMPL  = IMPL_DIR  / "ingest_top_utilization_placed.rpt"
UTIL_RPT_SYNTH = SYNTH_DIR / "ingest_top_utilization_synth.rpt"
TIMING_RPT     = IMPL_DIR  / "ingest_top_timing_summary_routed.rpt"
POWER_RPT      = IMPL_DIR  / "ingest_top_power_routed.rpt"


def parse_util(rpt: str) -> dict:
    patterns = {
        "lut":  r"Slice LUTs[* ]*\s*\|\s*(\d+)",
        "ff":   r"Slice Registers\s*\|\s*(\d+)",
        "bram": r"Block RAM Tile\s*\|\s*(\d+)",
        "dsp":  r"DSPs\s*\|\s*(\d+)",
    }
    result = {}
    for key, pat in patterns.items():
        m = re.search(pat, rpt)
        result[key] = int(m.group(1)) if m else None
    return result


def parse_timing(rpt: str) -> dict:
    # Match the Design Timing Summary header, then the first row of numbers.
    m = re.search(
        r"WNS\(ns\)\s+TNS\(ns\).*?\n[-\s]+\n\s*"
        r"([-\d.]+)\s+([-\d.]+)\s+\d+\s+\d+\s+"
        r"([-\d.]+)\s+([-\d.]+)",
        rpt, re.S
    )
    if not m:
        return {"wns_ns": None, "tns_ns": None,
                "whs_ns": None, "ths_ns": None}
    return {
        "wns_ns": float(m.group(1)),
        "tns_ns": float(m.group(2)),
        "whs_ns": float(m.group(3)),
        "ths_ns": float(m.group(4)),
    }


def parse_power(rpt: str) -> dict:
    fields = {
        "total_power_w":   r"Total On-Chip Power \(W\)\s*\|\s*([\d.]+)",
        "dynamic_power_w": r"Dynamic \(W\)\s*\|\s*([\d.]+)",
        "static_power_w":  r"Device Static \(W\)\s*\|\s*([\d.]+)",
        "junction_temp_c": r"Junction Temperature \(C\)\s*\|\s*([\d.]+)",
    }
    result = {}
    for key, pat in fields.items():
        m = re.search(pat, rpt)
        result[key] = float(m.group(1)) if m else None
    return result


def read_or_warn(path: Path) -> str | None:
    if not path.exists():
        print(f"  warning: {path.name} not found at {path}", file=sys.stderr)
        return None
    return path.read_text(errors="replace")


def main() -> int:
    summary = {"module": "Module2_ingest_top"}

    # Prefer the post-implementation utilization report; fall back to synth.
    util_text = read_or_warn(UTIL_RPT_IMPL)
    if util_text is None:
        util_text = read_or_warn(UTIL_RPT_SYNTH)
        summary["util_source"] = "synth"
    else:
        summary["util_source"] = "impl"
    if util_text is not None:
        summary.update(parse_util(util_text))

    timing_text = read_or_warn(TIMING_RPT)
    if timing_text is not None:
        summary.update(parse_timing(timing_text))

    power_text = read_or_warn(POWER_RPT)
    if power_text is not None:
        summary.update(parse_power(power_text))

    OUT_PATH.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
