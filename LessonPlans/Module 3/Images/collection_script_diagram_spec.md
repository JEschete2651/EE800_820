# Figure: Host-Side Data Collection Script Architecture

**Target filename:** `collection_script.png` (or `.pdf`) in `LessonPlans/Module 3/Images/`
**Used by:** `Module3.tex`, `\label{fig:collection_script}`
**Aspect:** wide landscape, roughly 16:5 — sized to span ~85% of an 8.5" letter text column.

## Caption (already in the .tex, for reference)

> Host-side data collection script architecture. The campaign configuration JSON provides ground-truth labels (experiment ID, sweep variable setting, physical distance) that are attached to each received feature vector.

## Layout

Five boxes in a left-to-right row, plus one box below the fourth feeding up into it. All arrows point left-to-right except the config arrow which points up.

```
 ┌──────────┐    ┌──────────┐    ┌───────────────┐    ┌──────────┐    ┌──────────┐
 │  USB-    │    │ PySerial │    │ Feature       │    │  Label   │    │ CSV File │
 │  UART    │──▶│  Reader  │──▶│ Vector Parser │──▶│ Attacher │──▶│ (Dataset)│
 │ (COM     │    │          │    │               │    │          │    │          │
 │  port)   │    │          │    │               │    │          │    │          │
 └──────────┘    └──────────┘    └───────────────┘    └──────────┘    └──────────┘
   raw bytes       32 B vectors     parsed fields       labeled rows
                                                            ▲
                                                            │ ground-truth
                                                            │ labels
                                                       ┌──────────┐
                                                       │ Campaign │
                                                       │  Config  │
                                                       │  (JSON)  │
                                                       └──────────┘
```

## Box specs

| Box | Type | Fill | Border | Label (two lines allowed) |
|-----|------|------|--------|----------------------------|
| 1 | I/O | very light blue (`#EAF1F9`) | dark blue (`#1E508C`) | **USB-UART**<br>(COM port) |
| 2 | Block | light gray (`#F0F0F0`) | Stevens red (`#A31F34`) | **PySerial**<br>Reader |
| 3 | Block | light gray (`#F0F0F0`) | Stevens red (`#A31F34`) | **Feature Vector**<br>Parser |
| 4 | Block | light gray (`#F0F0F0`) | Stevens red (`#A31F34`) | **Label**<br>Attacher |
| 5 | I/O | very light blue (`#EAF1F9`) | dark blue (`#1E508C`) | **CSV File**<br>(Dataset) |
| 6 | I/O | very light blue (`#EAF1F9`) | dark blue (`#1E508C`) | **Campaign Config**<br>(JSON) |

All boxes: rounded corners (~4 pt), ~2 pt border, centered text, same height (~1.1 in), width to fit label comfortably. Boxes 1–5 are vertically aligned on one row; box 6 sits below box 4 with a ~0.4 in gap.

## Arrow specs

- **Arrow style:** solid, ~1.5 pt, dark gray (`#3C3C3C`), filled-triangle arrowhead ("Stealth" in tikz terms).
- **Arrow labels:** small italic, dark blue (`#1E508C`), placed above the arrow (below for the vertical one).

| From | To | Label |
|------|----|----|
| Box 1 USB-UART | Box 2 PySerial Reader | *raw bytes* |
| Box 2 PySerial Reader | Box 3 Feature Vector Parser | *32 B vectors* |
| Box 3 Feature Vector Parser | Box 4 Label Attacher | *parsed fields* |
| Box 4 Label Attacher | Box 5 CSV File | *labeled rows* |
| Box 6 Campaign Config | Box 4 Label Attacher (enters from below) | *ground-truth labels* |

## Color palette (matches the rest of the module)

- Stevens red: `#A31F34` (box 2–4 borders, accent)
- Accent blue: `#1E508C` (box 1/5/6 borders, arrow labels)
- Dark gray: `#3C3C3C` (arrow shafts, body text)
- Light gray: `#F0F0F0` (block fills)
- Light blue: `#EAF1F9` (I/O fills — ~5% tint of accent blue)

## Font suggestions

- Box labels: any clean sans-serif (Calibri, Segoe UI, Inter), 12–14 pt bold.
- Arrow labels: same family, 9–10 pt italic.

## When exporting

1. Size the slide to match your desired export aspect (e.g., 10 × 3 in).
2. File → Export → PNG at 300 dpi, or "Save as PDF" for a vector version.
3. Save as `collection_script.png` in this `Images/` folder.
4. In `Module3.tex`, replace the `\fbox{\parbox…}` placeholder at `\label{fig:collection_script}` with:

   ```latex
   \includegraphics[width=0.85\textwidth]{collection_script}
   ```
