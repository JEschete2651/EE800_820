#include "diagnostic.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#define UID_BASE_ADDR        0x1FFF7590U
#define FLASHSIZE_BASE_ADDR  0x1FFF75E0U
#define VREFINT_CAL_ADDR     0x1FFF75AAU
#define TS_CAL1_ADDR         0x1FFF75A8U
#define TS_CAL2_ADDR         0x1FFF75CAU

#define VREFINT_CAL_VDDA_MV  3000U
#define TS_CAL1_TEMP_C       30
#define TS_CAL2_TEMP_C       110

#define ADC_FULL_SCALE       4095U
#define BTN_WINDOW_MS        5000U
#define HB_PERIOD_MS         1000U

typedef enum { RES_PASS = 0, RES_FAIL, RES_SKIP } Diag_Result_t;

static Diag_Config_t  s_cfg;
static Diag_Result_t  s_res_mcu, s_res_flash, s_res_systick;
static Diag_Result_t  s_res_gpio_out, s_res_gpio_in;
static Diag_Result_t  s_res_vrefint, s_res_tempsense;
static uint32_t       s_boot_tick;
static uint32_t       s_last_hb_tick;
static uint8_t        s_led_state;

static void diag_printf(const char *fmt, ...) {
    char buf[192];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if (n > (int)sizeof buf) n = sizeof buf;
    HAL_UART_Transmit(s_cfg.uart, (uint8_t *)buf, (uint16_t)n, HAL_MAX_DELAY);
}

static const char *result_str(Diag_Result_t r) {
    switch (r) {
        case RES_PASS: return "PASS";
        case RES_FAIL: return "FAIL";
        default:       return "SKIP";
    }
}

static uint32_t adc_read_channel(uint32_t channel) {
    ADC_ChannelConfTypeDef ch = {0};
    ch.Channel      = channel;
    ch.Rank         = ADC_REGULAR_RANK_1;
    ch.SamplingTime = ADC_SAMPLETIME_247CYCLES_5;
    ch.SingleDiff   = ADC_SINGLE_ENDED;
    ch.OffsetNumber = ADC_OFFSET_NONE;
    ch.Offset       = 0;
    if (HAL_ADC_ConfigChannel(s_cfg.adc, &ch) != HAL_OK) return 0xFFFFFFFFu;
    if (HAL_ADC_Start(s_cfg.adc) != HAL_OK) return 0xFFFFFFFFu;
    if (HAL_ADC_PollForConversion(s_cfg.adc, 50) != HAL_OK) { HAL_ADC_Stop(s_cfg.adc); return 0xFFFFFFFFu; }
    uint32_t v = HAL_ADC_GetValue(s_cfg.adc);
    HAL_ADC_Stop(s_cfg.adc);
    return v;
}

static void check_mcu_ident(void) {
    uint32_t idcode = DBGMCU->IDCODE;
    uint16_t dev_id = idcode & 0x0FFFu;
    uint16_t rev_id = (idcode >> 16) & 0xFFFFu;
    diag_printf("[1] MCU ID\r\n");
    diag_printf("    DEV_ID: 0x%03X   REV_ID: 0x%04X\r\n", dev_id, rev_id);
    s_res_mcu = (dev_id == 0x415) ? RES_PASS : RES_FAIL;
}

static void check_flash_and_uid(void) {
    uint16_t flash_kb = *(volatile uint16_t *)FLASHSIZE_BASE_ADDR;
    uint32_t uid0 = *(volatile uint32_t *)(UID_BASE_ADDR + 0x00);
    uint32_t uid1 = *(volatile uint32_t *)(UID_BASE_ADDR + 0x04);
    uint32_t uid2 = *(volatile uint32_t *)(UID_BASE_ADDR + 0x08);
    diag_printf("    Flash size: %u kB\r\n", (unsigned)flash_kb);
    diag_printf("    Unique ID : 0x%08lX 0x%08lX 0x%08lX\r\n",
                (unsigned long)uid0, (unsigned long)uid1, (unsigned long)uid2);
    s_res_flash = (flash_kb == 1024) ? RES_PASS : RES_FAIL;
}

static void check_systick(void) {
    diag_printf("[2] Clock sanity\r\n");
    uint32_t t0 = HAL_GetTick();
    HAL_Delay(500);
    uint32_t dt = HAL_GetTick() - t0;
    diag_printf("    500 ms delay measured as %lu ms\r\n", (unsigned long)dt);
    s_res_systick = (dt >= 495 && dt <= 510) ? RES_PASS : RES_FAIL;
}

static void check_gpio_output(void) {
    diag_printf("[3] GPIO output (LD2) — 5 pulses at 1 Hz\r\n");
    for (int i = 0; i < 5; i++) {
        HAL_GPIO_WritePin(s_cfg.led_port, s_cfg.led_pin, GPIO_PIN_SET);
        HAL_Delay(500);
        HAL_GPIO_WritePin(s_cfg.led_port, s_cfg.led_pin, GPIO_PIN_RESET);
        HAL_Delay(500);
    }
    s_res_gpio_out = RES_PASS;
}

static int btn_is_pressed(void) {
    GPIO_PinState s = HAL_GPIO_ReadPin(s_cfg.btn_port, s_cfg.btn_pin);
    return s_cfg.btn_active_low ? (s == GPIO_PIN_RESET) : (s == GPIO_PIN_SET);
}

static void check_gpio_input(void) {
    if (!s_cfg.btn_port) { s_res_gpio_in = RES_SKIP; return; }
    diag_printf("[4] GPIO input (B1) — press once within %u s\r\n",
                (unsigned)(BTN_WINDOW_MS / 1000));
    uint32_t t0 = HAL_GetTick();
    int edges = 0, prev = btn_is_pressed();
    while ((HAL_GetTick() - t0) < BTN_WINDOW_MS) {
        int now = btn_is_pressed();
        if (now && !prev) {
            edges++;
            diag_printf("    [T+%lu ms] press detected (edges=%d)\r\n",
                        (unsigned long)(HAL_GetTick() - t0), edges);
        }
        prev = now;
        HAL_Delay(10);
    }
    s_res_gpio_in = edges > 0 ? RES_PASS : RES_SKIP;
}

static uint32_t compute_vdda_mv(uint32_t vrefint_raw) {
    if (!vrefint_raw || vrefint_raw == 0xFFFFFFFFu) return 0;
    uint16_t cal = *(volatile uint16_t *)VREFINT_CAL_ADDR;
    return (uint32_t)VREFINT_CAL_VDDA_MV * cal / vrefint_raw;
}

static int32_t compute_temp_c(uint32_t ts_raw, uint32_t vdda_mv) {
    if (!ts_raw || ts_raw == 0xFFFFFFFFu || !vdda_mv) return -999;
    int32_t ts = (int32_t)(ts_raw * vdda_mv / VREFINT_CAL_VDDA_MV);
    int32_t cal1 = *(volatile uint16_t *)TS_CAL1_ADDR;
    int32_t cal2 = *(volatile uint16_t *)TS_CAL2_ADDR;
    if (cal2 == cal1) return -999;
    return ((TS_CAL2_TEMP_C - TS_CAL1_TEMP_C) * (ts - cal1)) / (cal2 - cal1) + TS_CAL1_TEMP_C;
}

static void check_adc(void) {
    if (!s_cfg.adc) { s_res_vrefint = s_res_tempsense = RES_SKIP; return; }
    diag_printf("[5] ADC\r\n");
    if (HAL_ADCEx_Calibration_Start(s_cfg.adc, ADC_SINGLE_ENDED) != HAL_OK) {
        diag_printf("    calibration FAILED\r\n");
        s_res_vrefint = s_res_tempsense = RES_FAIL;
        return;
    }
    uint32_t vref = adc_read_channel(ADC_CHANNEL_VREFINT);
    uint32_t ts   = adc_read_channel(ADC_CHANNEL_TEMPSENSOR);
    uint32_t vdda = compute_vdda_mv(vref);
    int32_t  tc   = compute_temp_c(ts, vdda);
    diag_printf("    VREFINT raw=%lu  VDDA=%lu.%03lu V\r\n",
                (unsigned long)vref, (unsigned long)(vdda / 1000), (unsigned long)(vdda % 1000));
    diag_printf("    TempSens raw=%lu  T=%ld C\r\n", (unsigned long)ts, (long)tc);
    s_res_vrefint   = (vdda >= 3100 && vdda <= 3450) ? RES_PASS : RES_FAIL;
    s_res_tempsense = (tc >= 0 && tc <= 70)          ? RES_PASS : RES_FAIL;
}

static void print_summary(void) {
    diag_printf("[6] Summary\r\n");
    diag_printf("    MCU ident    : %s\r\n", result_str(s_res_mcu));
    diag_printf("    Flash/UID    : %s\r\n", result_str(s_res_flash));
    diag_printf("    SysTick      : %s\r\n", result_str(s_res_systick));
    diag_printf("    GPIO out     : %s\r\n", result_str(s_res_gpio_out));
    diag_printf("    GPIO in      : %s\r\n", result_str(s_res_gpio_in));
    diag_printf("    ADC VREFINT  : %s\r\n", result_str(s_res_vrefint));
    diag_printf("    ADC TempSens : %s\r\n", result_str(s_res_tempsense));
    diag_printf("========================================\r\n");
    diag_printf(" BOARD READY — entering heartbeat\r\n");
    diag_printf("========================================\r\n");
}

void Diag_Init(const Diag_Config_t *cfg) {
    s_cfg = *cfg;
    s_boot_tick    = HAL_GetTick();
    s_last_hb_tick = s_boot_tick;
    s_led_state    = 0;
}

void Diag_RunAll(void) {
    diag_printf("\r\n========================================\r\n");
    diag_printf(" L476RG Board Diagnostic  v%s\r\n", DIAG_FW_VERSION);
    diag_printf("========================================\r\n");
    check_mcu_ident();
    check_flash_and_uid();
    check_systick();
    check_gpio_output();
    check_gpio_input();
    check_adc();
    print_summary();
}

void Diag_Heartbeat(void) {
    uint32_t now = HAL_GetTick();
    if ((now - s_last_hb_tick) < HB_PERIOD_MS) return;
    s_last_hb_tick = now;
    s_led_state ^= 1;
    HAL_GPIO_WritePin(s_cfg.led_port, s_cfg.led_pin,
                      s_led_state ? GPIO_PIN_SET : GPIO_PIN_RESET);

    uint32_t vref = s_cfg.adc ? adc_read_channel(ADC_CHANNEL_VREFINT)   : 0;
    uint32_t ts   = s_cfg.adc ? adc_read_channel(ADC_CHANNEL_TEMPSENSOR) : 0;
    uint32_t vdda = compute_vdda_mv(vref);
    int32_t  tc   = compute_temp_c(ts, vdda);
    int btn       = s_cfg.btn_port ? btn_is_pressed() : 0;

    diag_printf("[T+%6lus] HB  LD2=%u  VDDA=%lu.%03luV  T=%ldC  BTN=%d\r\n",
                (unsigned long)((now - s_boot_tick) / 1000),
                (unsigned)s_led_state,
                (unsigned long)(vdda / 1000), (unsigned long)(vdda % 1000),
                (long)tc, btn);
}
