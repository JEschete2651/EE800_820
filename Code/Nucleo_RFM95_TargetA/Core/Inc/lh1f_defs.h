#ifndef LH1F_DEFS_H
#define LH1F_DEFS_H

#include <stdint.h>

/* --- Beacon IDs (same in all three firmware projects) --- */
#define BEACON_ID_A       0x01u
#define BEACON_ID_B       0x02u
#define BEACON_ID_THREAT  0xFFu

/* --- Packet types (low 2 bits of Modulation Code byte) --- */
#define PKT_TYPE_DATA     0x00u
#define PKT_TYPE_ACK      0x01u
#define PKT_TYPE_PAUSE    0x02u

/* --- Modulation kinds (high 6 bits of Modulation Code byte, pre-shift) --- */
#define MOD_KIND_LORA     0x01u
#define MOD_KIND_FSK      0x02u
#define MOD_KIND_OOK      0x03u

/* --- LoRa carrier register triple for 906.5 MHz on 32 MHz TCXO --- */
#define RFM_FRF_MSB       0xE2u   /* RegFrfMsb  (0x06) */
#define RFM_FRF_MID       0xA0u   /* RegFrfMid  (0x07) */
#define RFM_FRF_LSB       0x00u   /* RegFrfLsb  (0x08) */

/* --- Radio helpers (defined in main.c) --- */
uint8_t  rfm_read_reg(uint8_t addr);
void     rfm_write_reg(uint8_t addr, uint8_t value);
void     rfm_set_mode_standby(void);
void     rfm_set_mode_rx(void);
void     lora_init(void);

/* --- New helpers introduced by LH1-F (defined in lh1f_packet.c) --- */
uint16_t crc16_ccitt(const uint8_t *buf, uint32_t len);
void     build_packet(uint8_t out[32], uint8_t my_id, uint16_t seq,
                      uint8_t pkt_type, uint8_t mod_kind);

#endif /* LH1F_DEFS_H */
