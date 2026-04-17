# Board Map — Physical STM32 ↔ Logical Role

Fill one row per physical Nucleo-L476RG. The Unique ID comes from the **Unique ID** line in the diagnostic serial output (phase 1). Once locked, future firmware can branch on UID at boot to auto-detect role.

| Logical role | Unique ID (0x…  0x…  0x…) | Acceptance date | Notes (LED color, sticker, ST-LINK FW rev) |
|---|---|---|---|
| Defender-A | `0x________ 0x________ 0x________` |  |  |
| Defender-B | `0x________ 0x________ 0x________` |  |  |
| Threat     | `0x________ 0x________ 0x________` |  |  |

## Procedure reminder

1. Flash diagnostic firmware to the board.
2. Let it run through phases 1–6; confirm the summary shows all `PASS`.
3. Copy the `Unique ID` line from the phase 1 output into the table above.
4. Label the physical board with a sticker that matches the logical role.
5. Save the serial log as `logs/<role>_<YYYY-MM-DD>.txt` (create `logs/` if needed).

## If a board fails

Record the failure in the Notes column and do not retire the row — replacing hardware means a new UID, and you'll want the history. Move the old UID into a strikethrough sub-row if you reassign the logical role to a new board.
