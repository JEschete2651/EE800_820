# LH1-G Forwarding-Frame Parser

Validates and decodes the 43-byte UART frames produced by the Threat
(Interceptor) firmware on USART3.

## Frame layout

| Offset | Field                                    | Length |
| -----: | ---------------------------------------- | -----: |
|      0 | Start delimiter (`0x7E`)                 |      1 |
|      1 | Frame length (always `0x29` = 41)        |      1 |
|    2-5 | RX timestamp (uint32, LE, ms)            |      4 |
|      6 | RSSI (int8, dBm)                         |      1 |
|      7 | SNR (int8, 0.25 dB resolution)           |      1 |
|    8-9 | Frequency error (int16, LE, Hz)          |      2 |
|  10-41 | Radio packet (32 bytes: DATA/ACK/PAUSE)  |     32 |
|     42 | Frame CRC-8/ITU (poly `0x07`) over 1..41 |      1 |

The embedded radio-packet CRC-16/CCITT (packet bytes 30..31) is validated
independently of the frame CRC-8.

## Setup

```powershell
cd "D:\judee\Google Drive\School\Classes\EE800_820\Code\Tools\LH1G_Parser"
python -m pip install -r requirements.txt
```

## Run

```powershell
python lh1g_parser.py <port> <baud> <out_csv>
python lh1g_parser.py COM7 115200 LH1G_capture.csv
```

Decoded rows print to stdout; framing/CRC failures print to stderr as
`DROP {...} raw=...`. The CSV columns are:

```
t_ms, sender, pkt_type, mod_kind, seq, rssi, snr_db, freq_err
```

## Validation expectations

- Target A/B ping-pong source at ~1 Hz: interleaved `0x01`/DATA and
  `0x02`/ACK rows with matching sequence numbers, every row CRC-clean.
- 5-minute run: zero dropped frames, zero CRC failures.
