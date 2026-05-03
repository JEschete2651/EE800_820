#include "lh1f_defs.h"
#include "main.h"

extern volatile uint32_t ms_count;
extern uint8_t g_lora_sf;

/* CRC-16/CCITT-FALSE: poly=0x1021, init=0xFFFF, no reflect, xorout=0x0000.
 * Verified against the standard test vector: crc16_ccitt("123456789", 9)
 * must equal 0x29B1.
 */
uint16_t crc16_ccitt(const uint8_t *buf, uint32_t len)
{
    uint16_t crc = 0xFFFFu;
    for (uint32_t i = 0; i < len; i++) {
        crc ^= ((uint16_t)buf[i]) << 8;
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u)
                                  : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

void build_packet(uint8_t out[32], uint8_t my_id, uint16_t seq,
                  uint8_t pkt_type, uint8_t mod_kind)
{
    out[0] = 0xAEu;
    out[1] = 0x5Au;
    out[2] = my_id;
    out[3] = (uint8_t)(seq & 0xFFu);
    out[4] = (uint8_t)((seq >> 8) & 0xFFu);
    out[5] = 14u;
    out[6] = (uint8_t)((mod_kind << 2) | (pkt_type & 0x03u));
    out[7] = (mod_kind == MOD_KIND_LORA) ? g_lora_sf : 0u;
    out[8] = 0u;

    uint32_t t = ms_count;
    out[9]  = (uint8_t)(t      );
    out[10] = (uint8_t)(t >>  8);
    out[11] = (uint8_t)(t >> 16);
    out[12] = (uint8_t)(t >> 24);

    for (int i = 13; i < 30; i++) out[i] = 0xAAu;

    uint16_t crc = crc16_ccitt(out, 30);
    out[30] = (uint8_t)(crc >> 8);
    out[31] = (uint8_t)(crc);
}
