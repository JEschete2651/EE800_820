/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include "lh1f_defs.h"

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/* Beacon IDs, packet types, modulation kinds live in lh1f_defs.h */

#ifndef MY_BEACON_ID
#define MY_BEACON_ID       BEACON_ID_B
#endif
#ifndef ROLE_RESPONDER
#define ROLE_RESPONDER
#endif

/* --- Campaign-configurable radio parameters --------------------------------
 * Edit these two defines between campaign runs; do not change register
 * addresses or any other values in lora_init().
 *
 * LORA_SF:         Spreading factor 7-12
 * LORA_TX_PWR_DBM: TX output power in dBm (+2, +8, +14, or +20)
 * -------------------------------------------------------------------------- */
#define LORA_SF          7
#define LORA_TX_PWR_DBM  14

/* Derived register values -- do not edit below this line */
#define REG_MODEM_CONFIG2_VAL  ((LORA_SF << 4) | 0x04)
#define REG_PA_CONFIG_VAL      (0x80 | ((LORA_TX_PWR_DBM - 2) & 0x0F))

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
SPI_HandleTypeDef hspi1;

TIM_HandleTypeDef htim2;

UART_HandleTypeDef huart2;
UART_HandleTypeDef huart3;
DMA_HandleTypeDef hdma_usart3_tx;

/* USER CODE BEGIN PV */
volatile uint32_t ms_count = 0;
uint8_t g_lora_sf = LORA_SF;

typedef struct {
  uint8_t  raw[32];
  uint32_t rx_ts_ms;
  int8_t   rssi_dbm;
  int8_t   snr_q025;
} pkt_rx_t;

volatile pkt_rx_t rx_slot;
volatile uint8_t  rx_ready = 0;
volatile uint32_t paused_until_ms = 0;
volatile uint32_t pause_print_until_ms = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_SPI1_Init(void);
static void MX_USART3_UART_Init(void);
static void MX_TIM2_Init(void);
/* USER CODE BEGIN PFP */
int __io_putchar(int ch);
uint32_t rfm_frf_to_hz(uint8_t msb, uint8_t mid, uint8_t lsb);
/* radio + packet helper prototypes come from lh1f_defs.h */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART2_UART_Init();
  MX_SPI1_Init();
  MX_USART3_UART_Init();
  MX_TIM2_Init();
  /* USER CODE BEGIN 2 */
  const uint8_t *uid = (const uint8_t *)0x1FFF7590U;
  char uid_str[25];
  snprintf(uid_str, sizeof(uid_str),
           "%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X",
           uid[0], uid[1], uid[2], uid[3],
           uid[4], uid[5], uid[6], uid[7],
           uid[8], uid[9], uid[10], uid[11]);

  const char *board_name = "Unknown";
  if (strcmp(uid_str, "500022000350453151313620") == 0) board_name = "Board 3";
  else if (strcmp(uid_str, "400052001750563042313320") == 0) board_name = "Board 2";
  else if (strcmp(uid_str, "360020000350453151313620") == 0) board_name = "Board 1";

  printf("UID: %s --> %s\r\n", uid_str, board_name);

  /* CRC-16/CCITT-FALSE self-test (LH1-F deliverable) */
  {
    const uint8_t vec[9] = {'1','2','3','4','5','6','7','8','9'};
    uint16_t got = crc16_ccitt(vec, 9);
    if (got != 0x29B1u) {
      printf("CRC16 SELFTEST FAIL: expected 0x29B1 got 0x%04X\r\n", got);
      while (1) { /* hang on failure */ }
    } else {
      printf("CRC16 SELFTEST PASS (0x29B1)\r\n");
    }
  }

  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_SET);

  HAL_GPIO_WritePin(RFM_RST_GPIO_Port, RFM_RST_Pin, GPIO_PIN_RESET);
  HAL_Delay(1);
  HAL_GPIO_WritePin(RFM_RST_GPIO_Port, RFM_RST_Pin, GPIO_PIN_SET);
  HAL_Delay(10);

  uint8_t version = rfm_read_reg(0x42);
  printf("RegVersion = 0x%02X\r\n", version);

  lora_init();

  /* Start the 1 ms TIM2 tick driving ms_count */
  HAL_TIM_Base_Start_IT(&htim2);

  /* PB10 instrumentation pulse (TX-entry scope trigger) */
  __HAL_RCC_GPIOB_CLK_ENABLE();
  {
    GPIO_InitTypeDef trig = {0};
    trig.Pin   = GPIO_PIN_10;
    trig.Mode  = GPIO_MODE_OUTPUT_PP;
    trig.Pull  = GPIO_NOPULL;
    trig.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &trig);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_RESET);
  }

  rfm_set_mode_rx();

  printf("Target B responder ready (id=0x%02X)\r\n", (unsigned)MY_BEACON_ID);

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  typedef enum {
    ST_IDLE, ST_BUILD_DATA, ST_BUILD_ACK, ST_TX,
    ST_WAIT_ACK, ST_LOG, ST_FAULT
  } state_t;

  state_t  state = ST_IDLE;
  uint16_t seq = 0;
  uint16_t pending_ack_seq = 0;
  uint32_t t_tx_ms = 0;
  uint8_t  pkt[32];
  uint8_t  log_was_acked = 0;
  int16_t  log_ack_rssi = 0;
  uint32_t log_rtt_ms = 0;
  uint32_t next_tx_ms = ms_count + 1000;
  uint16_t data_rx = 0;
  uint16_t acks_sent = 0;
  (void)seq; (void)t_tx_ms; (void)log_was_acked;
  (void)log_ack_rssi; (void)log_rtt_ms; (void)next_tx_ms;

  while (1)
  {
    /* Honor PAUSE: suppress scheduled DATA TX (initiator only). The
     * responder still processes incoming RX so PAUSE refreshes can extend
     * the hold-off, and ACKs are still allowed (they are responses to a
     * real DATA reception, not scheduled traffic).                        */
    uint8_t paused_now = (ms_count < paused_until_ms);

    /* Throttled "I'm Jammed" print: at most once per pause window */
    if (paused_now && pause_print_until_ms < paused_until_ms) {
      printf("I'm Jammed (by ID=0x%02X, until t=%lu)\r\n",
             (unsigned)BEACON_ID_THREAT,
             (unsigned long)paused_until_ms);
      pause_print_until_ms = paused_until_ms;
    }

    switch (state) {
    case ST_IDLE:
#ifdef ROLE_INITIATOR
      if (!paused_now && ms_count >= next_tx_ms) {
        state = ST_BUILD_DATA;
        break;
      }
#endif
      if (rx_ready) {
        rx_ready = 0;
        uint8_t pkt_type = rx_slot.raw[6] & 0x03;
        uint8_t sender   = rx_slot.raw[2];
#ifdef ROLE_RESPONDER
        if (pkt_type == PKT_TYPE_DATA && sender == BEACON_ID_A) {
          pending_ack_seq = (uint16_t)rx_slot.raw[3]
                          | ((uint16_t)rx_slot.raw[4] << 8);
          data_rx++;
          printf("RX DATA seq=%u rssi=%d snr=%d\r\n",
                 (unsigned)pending_ack_seq,
                 (int)rx_slot.rssi_dbm,
                 (int)(rx_slot.snr_q025 / 4));
          state = ST_BUILD_ACK;
          break;
        }
#endif
        (void)pkt_type; (void)sender;
      }
      break;

    case ST_BUILD_DATA:
      build_packet(pkt, MY_BEACON_ID, seq,
                   PKT_TYPE_DATA, MOD_KIND_LORA);
      state = ST_TX;
      break;

    case ST_BUILD_ACK:
      build_packet(pkt, MY_BEACON_ID, pending_ack_seq,
                   PKT_TYPE_ACK, MOD_KIND_LORA);
      state = ST_TX;
      break;

    case ST_TX: {
      rfm_set_mode_standby();
      rfm_write_reg(0x0D, rfm_read_reg(0x0E));
      for (int i = 0; i < 32; i++) rfm_write_reg(0x00, pkt[i]);
      rfm_write_reg(0x22, 32);
      t_tx_ms = ms_count;
      rfm_write_reg(0x12, 0xFF);

      HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_SET);
      rfm_write_reg(0x01, 0x83);  /* TX */

      uint32_t tx_deadline = ms_count + 500;
      uint8_t ok = 0;
      while (ms_count < tx_deadline) {
        if (rfm_read_reg(0x12) & 0x08) { ok = 1; break; }
      }
      rfm_write_reg(0x12, 0xFF);
      HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_RESET);

      if (!ok) { state = ST_FAULT; break; }

#ifdef ROLE_RESPONDER
      acks_sent++;
#endif
      rfm_set_mode_rx();
#ifdef ROLE_INITIATOR
      state = ST_WAIT_ACK;
#else
      state = ST_LOG;
#endif
      break;
    }

#ifdef ROLE_INITIATOR
    case ST_WAIT_ACK: {
      uint32_t deadline = ms_count + 200;
      log_was_acked = 0;
      while (ms_count < deadline) {
        if (rx_ready) {
          rx_ready = 0;
          uint8_t pkt_type = rx_slot.raw[6] & 0x03;
          uint8_t sender   = rx_slot.raw[2];
          uint16_t rs = (uint16_t)rx_slot.raw[3]
                      | ((uint16_t)rx_slot.raw[4] << 8);
          if (pkt_type == PKT_TYPE_ACK
              && sender == BEACON_ID_B
              && rs == seq) {
            log_was_acked = 1;
            log_ack_rssi  = rx_slot.rssi_dbm;
            log_rtt_ms    = ms_count - t_tx_ms;
            break;
          }
        }
      }
      next_tx_ms = t_tx_ms + 1000;
      seq++;
      state = ST_LOG;
      break;
    }
#endif

    case ST_LOG:
#ifdef ROLE_INITIATOR
      if (log_was_acked) {
        printf("CSV,%u,%lu,%lu,%lu,%d\r\n",
               (unsigned)(seq - 1),
               (unsigned long)t_tx_ms,
               (unsigned long)(t_tx_ms + log_rtt_ms),
               (unsigned long)log_rtt_ms,
               (int)log_ack_rssi);
      } else {
        printf("CSV,%u,%lu,0,0,0  (no ACK)\r\n",
               (unsigned)(seq - 1),
               (unsigned long)t_tx_ms);
      }
#else
      printf("ACK seq=%u rssi=%d\r\n",
             (unsigned)pending_ack_seq, (int)rx_slot.rssi_dbm);
      if ((acks_sent % 10U) == 0U && acks_sent > 0U) {
        printf("# stats: data_rx=%u acks_sent=%u\r\n",
               (unsigned)data_rx,
               (unsigned)acks_sent);
      }
#endif
      state = ST_IDLE;
      break;

    case ST_FAULT:
      printf("FAULT --- TX timeout, reconfiguring radio\r\n");
      rfm_write_reg(0x12, 0xFF);
      lora_init();
      rfm_set_mode_rx();
      state = ST_IDLE;
      break;
    }
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 1;
  RCC_OscInitStruct.PLL.PLLN = 10;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV7;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief SPI1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_SPI1_Init(void)
{

  /* USER CODE BEGIN SPI1_Init 0 */

  /* USER CODE END SPI1_Init 0 */

  /* USER CODE BEGIN SPI1_Init 1 */

  /* USER CODE END SPI1_Init 1 */
  /* SPI1 parameter configuration*/
  hspi1.Instance = SPI1;
  hspi1.Init.Mode = SPI_MODE_MASTER;
  hspi1.Init.Direction = SPI_DIRECTION_2LINES;
  hspi1.Init.DataSize = SPI_DATASIZE_8BIT;
  hspi1.Init.CLKPolarity = SPI_POLARITY_LOW;
  hspi1.Init.CLKPhase = SPI_PHASE_1EDGE;
  hspi1.Init.NSS = SPI_NSS_SOFT;
  hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_32;
  hspi1.Init.FirstBit = SPI_FIRSTBIT_MSB;
  hspi1.Init.TIMode = SPI_TIMODE_DISABLE;
  hspi1.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
  hspi1.Init.CRCPolynomial = 7;
  hspi1.Init.CRCLength = SPI_CRC_LENGTH_DATASIZE;
  hspi1.Init.NSSPMode = SPI_NSS_PULSE_ENABLE;
  if (HAL_SPI_Init(&hspi1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN SPI1_Init 2 */

  /* USER CODE END SPI1_Init 2 */

}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 79;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 999;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  huart2.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart2.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief USART3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART3_UART_Init(void)
{

  /* USER CODE BEGIN USART3_Init 0 */

  /* USER CODE END USART3_Init 0 */

  /* USER CODE BEGIN USART3_Init 1 */

  /* USER CODE END USART3_Init 1 */
  huart3.Instance = USART3;
  huart3.Init.BaudRate = 115200;
  huart3.Init.WordLength = UART_WORDLENGTH_8B;
  huart3.Init.StopBits = UART_STOPBITS_1;
  huart3.Init.Parity = UART_PARITY_NONE;
  huart3.Init.Mode = UART_MODE_TX_RX;
  huart3.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart3.Init.OverSampling = UART_OVERSAMPLING_16;
  huart3.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart3.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart3) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART3_Init 2 */

  /* USER CODE END USART3_Init 2 */

}

/**
  * Enable DMA controller clock
  */
static void MX_DMA_Init(void)
{

  /* DMA controller clock enable */
  __HAL_RCC_DMA1_CLK_ENABLE();

  /* DMA interrupt init */
  /* DMA1_Channel2_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA1_Channel2_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(DMA1_Channel2_IRQn);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(RFM_RST_GPIO_Port, RFM_RST_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : RFM_DIO0_Pin */
  GPIO_InitStruct.Pin = RFM_DIO0_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(RFM_DIO0_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : RFM_RST_Pin */
  GPIO_InitStruct.Pin = RFM_RST_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(RFM_RST_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : RFM_CS_Pin */
  GPIO_InitStruct.Pin = RFM_CS_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(RFM_CS_GPIO_Port, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI9_5_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
int __io_putchar(int ch)
{
  uint8_t c = (uint8_t)ch;
  (void)HAL_UART_Transmit(&huart2, &c, 1, HAL_MAX_DELAY);
  return ch;
}

int _write(int file, char *ptr, int len)
{
  (void)file;
  (void)HAL_UART_Transmit(&huart2, (uint8_t *)ptr, len, HAL_MAX_DELAY);
  return len;
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance == TIM2) ms_count++;
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  if (GPIO_Pin != RFM_DIO0_Pin) return;

  uint8_t irq = rfm_read_reg(0x12);
  if ((irq & 0x40) == 0) {
    rfm_write_reg(0x12, 0xFF);
    return;
  }
  if (irq & 0x20) {  /* CRC error */
    rfm_write_reg(0x12, 0xFF);
    return;
  }

  uint8_t rx_addr = rfm_read_reg(0x10);
  rfm_write_reg(0x0D, rx_addr);
  for (int i = 0; i < 32; i++) {
    ((uint8_t *)rx_slot.raw)[i] = rfm_read_reg(0x00);
  }
  rx_slot.rx_ts_ms = ms_count;
  rx_slot.rssi_dbm = (int8_t)((int16_t)rfm_read_reg(0x1A) - 157);
  rx_slot.snr_q025 = (int8_t)rfm_read_reg(0x19);
  rfm_write_reg(0x12, 0xFF);

  /* Latch PAUSE addressed to us in the ISR for low latency.
   * The "I'm Jammed" print is deferred to the main loop.       */
  uint8_t sender   = rx_slot.raw[2];
  uint8_t pkt_type = rx_slot.raw[6] & 0x03;
  if (pkt_type == PKT_TYPE_PAUSE
      && sender == BEACON_ID_THREAT
      && rx_slot.raw[13] == MY_BEACON_ID) {
    uint8_t units = rx_slot.raw[14];
    paused_until_ms = ms_count + ((uint32_t)units * 100u);
  }

  rx_ready = 1;
}

uint8_t rfm_read_reg(uint8_t addr)
{
  uint8_t tx[2];
  uint8_t rx[2];

  tx[0] = addr & 0x7F;
  tx[1] = 0x00;

  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_RESET);
  (void)HAL_SPI_TransmitReceive(&hspi1, tx, rx, 2, HAL_MAX_DELAY);
  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_SET);

  return rx[1];
}

void rfm_write_reg(uint8_t addr, uint8_t val)
{
  uint8_t tx[2];

  tx[0] = addr | 0x80;
  tx[1] = val;

  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_RESET);
  (void)HAL_SPI_Transmit(&hspi1, tx, 2, HAL_MAX_DELAY);
  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_SET);
}

uint32_t rfm_frf_to_hz(uint8_t msb, uint8_t mid, uint8_t lsb)
{
  uint32_t frf = ((uint32_t)msb << 16) | ((uint32_t)mid << 8) | (uint32_t)lsb;
  uint64_t hz = ((uint64_t)frf * 32000000ULL) >> 19;
  return (uint32_t)hz;
}

void lora_init(void)
{
  rfm_write_reg(0x01, 0x80);
  HAL_Delay(10);

  rfm_write_reg(0x06, 0xE2);
  rfm_write_reg(0x07, 0xA0);
  rfm_write_reg(0x08, 0x00);

  rfm_write_reg(0x1D, 0x72);
  rfm_write_reg(0x1E, REG_MODEM_CONFIG2_VAL);

  rfm_write_reg(0x20, 0x00);
  rfm_write_reg(0x21, 0x08);

  rfm_write_reg(0x39, 0x34);

  rfm_write_reg(0x09, REG_PA_CONFIG_VAL);

  rfm_write_reg(0x0E, 0x80);
  rfm_write_reg(0x0F, 0x00);

  rfm_write_reg(0x01, 0x81);
  HAL_Delay(10);

  printf("lora_init done: SF=%d TxPwr=%d dBm\r\n", LORA_SF, LORA_TX_PWR_DBM);
}

void rfm_set_mode_standby(void)
{
  rfm_write_reg(0x01, 0x81);
}

void rfm_set_mode_rx(void)
{
  rfm_write_reg(0x0D, rfm_read_reg(0x0F));
  rfm_write_reg(0x12, 0xFF);
  rfm_write_reg(0x01, 0x85);
}

/* crc16_ccitt and build_packet now live in lh1f_packet.c */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
