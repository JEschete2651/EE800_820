#ifndef DIAGNOSTIC_H
#define DIAGNOSTIC_H

#include "stm32l4xx_hal.h"
#include <stdint.h>

#define DIAG_FW_VERSION "1.0"

typedef struct {
    UART_HandleTypeDef *uart;
    ADC_HandleTypeDef  *adc;
    GPIO_TypeDef       *led_port;
    uint16_t            led_pin;
    GPIO_TypeDef       *btn_port;
    uint16_t            btn_pin;
    uint8_t             btn_active_low;
} Diag_Config_t;

void Diag_Init(const Diag_Config_t *cfg);
void Diag_RunAll(void);
void Diag_Heartbeat(void);

#endif
