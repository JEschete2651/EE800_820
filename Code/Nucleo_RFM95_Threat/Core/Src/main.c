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
#include "stdio.h"
#include "string.h"

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
typedef struct {
    uint8_t  raw[32];          /* 32-byte radio packet as received */
    uint32_t rx_timestamp_ms;
    int8_t   rssi_dbm;
    int8_t   snr_q025;         /* 0.25 dB resolution */
    int16_t  freq_error_hz;
} intercepted_pkt_t;

typedef struct {
    int8_t   rssi_dbm;
    uint32_t last_seen_ms;
} rssi_obs_t;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define PKT_TYPE_DATA      0x00
#define PKT_TYPE_ACK       0x01
#define PKT_TYPE_PAUSE     0x02

#define MOD_KIND_LORA      0x01
#define MOD_KIND_FSK       0x02
#define MOD_KIND_OOK       0x03

#define BEACON_ID_A        0x01
#define BEACON_ID_B        0x02
#define BEACON_ID_THREAT   0xFF

#define RING_SIZE          16u                         /* power of two */
#define RING_MASK          (RING_SIZE - 1u)

#define RSSI_STALE_MS      5000u
#define PAUSE_PERIOD_MS    100u
#define PAUSE_HOLDOFF_UNITS 5u                         /* 5 * 100 ms = 500 ms */

/* --- Campaign-configurable radio parameters --------------------------------
 * Edit these two defines between campaign runs; do not change register
 * addresses or any other values in lora_init().
 *
 * LORA_SF:         Spreading factor 7-12 (must match Target A)
 * LORA_TX_PWR_DBM: TX output power in dBm (Threat jams at +20 dBm typically)
 * -------------------------------------------------------------------------- */
#define LORA_SF          7
#define LORA_TX_PWR_DBM  20

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
static intercepted_pkt_t ring[RING_SIZE];
volatile uint32_t ring_head = 0;                       /* writer (ISR)       */
volatile uint32_t ring_tail = 0;                       /* reader (main loop) */
volatile uint32_t dropped   = 0;
volatile uint32_t rx_count  = 0;

static volatile rssi_obs_t rssi_table[256];

static uint8_t   tx_frame[43];
volatile uint8_t tx_busy = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_SPI1_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_USART3_UART_Init(void);
static void MX_TIM2_Init(void);
/* USER CODE BEGIN PFP */
int __io_putchar(int ch);
uint8_t rfm_read_reg(uint8_t addr);
void rfm_write_reg(uint8_t addr, uint8_t val);
void lora_init(void);
void rfm_set_mode_rx(void);
void rfm_set_mode_standby(void);
uint16_t crc16_ccitt(const uint8_t *data, int len);
void build_packet(uint8_t *buf, uint8_t sender_id, uint16_t seq,
                  uint8_t pkt_type, uint8_t mod_kind);
static uint8_t crc8_itu(const uint8_t *buf, uint32_t len);
static void build_forwarding_frame(uint8_t out[43], const intercepted_pkt_t *pkt);
static int find_highest_rssi_id(uint8_t *out_id);
static int ring_push(const intercepted_pkt_t *src);
static int ring_pop(intercepted_pkt_t *dst);
static int16_t read_fei_hz(void);
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
  MX_SPI1_Init();
  MX_USART2_UART_Init();
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

  /* Reset the RFM95W */
  HAL_GPIO_WritePin(RFM_RST_GPIO_Port, RFM_RST_Pin, GPIO_PIN_RESET);
  HAL_Delay(1);
  HAL_GPIO_WritePin(RFM_RST_GPIO_Port, RFM_RST_Pin, GPIO_PIN_SET);
  HAL_Delay(10);

  uint8_t version = rfm_read_reg(0x42);
  printf("RegVersion = 0x%02X\r\n", version);

  lora_init();

  for (int i = 0; i < 256; i++) {
    rssi_table[i].rssi_dbm     = -128;
    rssi_table[i].last_seen_ms = 0;
  }

  rfm_set_mode_rx();

  uint32_t last_pause_tx_ms = 0;
  uint16_t pause_seq        = 0;
  uint32_t last_stats_ms    = HAL_GetTick();

  printf("Threat (Interceptor, ID=0x%02X) ready\r\n", BEACON_ID_THREAT);

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* --- Drain ring buffer and forward frames to FPGA over USART3 --- */
    intercepted_pkt_t pkt;
    while (ring_pop(&pkt))
    {
      /* Wait for any prior DMA TX to drain. 43 bytes @115200 = ~3.7 ms. */
      uint32_t deadline = HAL_GetTick() + 10u;
      while (tx_busy && HAL_GetTick() < deadline) { /* spin */ }
      if (tx_busy) { dropped++; continue; }

      build_forwarding_frame(tx_frame, &pkt);
      tx_busy = 1;
      HAL_UART_Transmit_DMA(&huart3, tx_frame, 43);

      uint16_t seq      = (uint16_t)pkt.raw[3] | ((uint16_t)pkt.raw[4] << 8);
      uint8_t  mod_byte = pkt.raw[6];
      uint8_t  pkt_type = mod_byte & 0x03u;
      uint8_t  mod_kind = (mod_byte >> 2) & 0x3Fu;

      printf("CSV,RX,%02X,%u,%u,%u,%lu,%d,%d\r\n",
             pkt.raw[2],
             (unsigned)pkt_type,
             (unsigned)mod_kind,
             (unsigned)seq,
             (unsigned long)pkt.rx_timestamp_ms,
             (int)pkt.rssi_dbm,
             (int)(pkt.snr_q025 / 4));
    }

    /* --- PAUSE TX scheduler (button-gated, ~10 Hz while held) --- */
    if (HAL_GPIO_ReadPin(B1_GPIO_Port, B1_Pin) == GPIO_PIN_RESET)
    {
      uint32_t now = HAL_GetTick();
      if ((now - last_pause_tx_ms) >= PAUSE_PERIOD_MS)
      {
        uint8_t target_id;
        if (find_highest_rssi_id(&target_id) == 0)
        {
          uint8_t pkt_buf[32];
          build_packet(pkt_buf, BEACON_ID_THREAT, pause_seq,
                       PKT_TYPE_PAUSE, MOD_KIND_LORA);
          pkt_buf[13] = target_id;
          pkt_buf[14] = PAUSE_HOLDOFF_UNITS;
          for (int i = 15; i < 30; i++) pkt_buf[i] = 0xAA;
          uint16_t crc = crc16_ccitt(pkt_buf, 30);
          pkt_buf[30] = (uint8_t)(crc >> 8);
          pkt_buf[31] = (uint8_t)(crc);

          /* Half-duplex: drop out of RX, TX, then return to RX. */
          rfm_set_mode_standby();
          rfm_write_reg(0x0D, rfm_read_reg(0x0E));
          for (int i = 0; i < 32; i++) rfm_write_reg(0x00, pkt_buf[i]);
          rfm_write_reg(0x22, 32);
          rfm_write_reg(0x12, 0xFF);
          rfm_write_reg(0x01, 0x83);

          uint32_t tx_deadline = HAL_GetTick() + 200u;
          while (HAL_GetTick() < tx_deadline
                 && (rfm_read_reg(0x12) & 0x08) == 0)
          {
            /* spin */
          }
          rfm_write_reg(0x12, 0xFF);
          rfm_set_mode_rx();

          int8_t rssi = rssi_table[target_id].rssi_dbm;
          printf("PAUSE -> ID=%02X (RSSI=%d dBm, seq=%u)\r\n",
                 target_id, (int)rssi, (unsigned)pause_seq);

          last_pause_tx_ms = now;
          pause_seq++;
        }
        else
        {
          /* Throttle the "no target" message to 1 Hz */
          if ((now - last_pause_tx_ms) >= 1000u)
          {
            printf("no PAUSE target available\r\n");
            last_pause_tx_ms = now;
          }
        }
      }
    }

    /* --- Periodic stats + per-ID RSSI snapshot (1 Hz) ---
     *
     * Three blocks of diagnostic output to USART2, gated to once per second
     * by last_stats_ms. The PAUSE TX scheduler only logs when it actually
     * emits a PAUSE, so without these snapshots there is no visibility into
     * what the Threat is hearing or why a particular target is (or isn't)
     * being selected. Each block answers a different question:
     *
     *   1. # stats:  ISR throughput (rx) vs. main-loop drop count (dropped).
     *      Used to detect ring-buffer overflow or USART3 TX backpressure.
     *
     *   2. # rssi[ID=...]:  one line per Beacon ID ever observed. Shows the
     *      most recent RSSI and the age of that observation. Entries older
     *      than RSSI_STALE_MS are flagged [STALE], meaning they will be
     *      excluded from find_highest_rssi_id(). This makes it obvious when
     *      a Target has gone quiet long enough to drop out of selection.
     *
     *   3. # target:  result of an unconditional find_highest_rssi_id()
     *      call. Shows who the Threat would jam right now if the button
     *      were pressed -- without actually pressing it. The whole point
     *      of this line is to make re-acquisition behavior observable
     *      ("does the target flip to ID=02 when I move A away?").
     */
    if ((HAL_GetTick() - last_stats_ms) >= 1000u)
    {
      uint32_t now = HAL_GetTick();
      last_stats_ms = now;

      /* Block 1: ISR throughput vs. main-loop drops. */
      printf("# stats: rx=%lu dropped=%lu\r\n",
             (unsigned long)rx_count,
             (unsigned long)dropped);

      /* Block 2: per-ID RSSI table dump. Skip never-seen entries
       * (last_seen_ms == 0) and the Threat's own beacon ID.             */
      for (int i = 1; i < 256; i++) {
        if (i == BEACON_ID_THREAT) continue;
        if (rssi_table[i].last_seen_ms == 0) continue;
        uint32_t age = now - rssi_table[i].last_seen_ms;
        const char *flag = (age > RSSI_STALE_MS) ? " [STALE]" : "";
        printf("# rssi[ID=0x%02X]=%d dBm age=%lu ms%s\r\n",
               (unsigned)i,
               (int)rssi_table[i].rssi_dbm,
               (unsigned long)age,
               flag);
      }

      /* Block 3: current PAUSE-target choice (if any non-stale entry). */
      uint8_t cur_id;
      if (find_highest_rssi_id(&cur_id) == 0) {
        printf("# target: ID=0x%02X RSSI=%d dBm\r\n",
               (unsigned)cur_id,
               (int)rssi_table[cur_id].rssi_dbm);
      } else {
        printf("# target: none (no fresh observations)\r\n");
      }
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
  HAL_UART_Transmit(&huart2, (uint8_t *)&ch, 1, HAL_MAX_DELAY);
  return ch;
}

uint8_t rfm_read_reg(uint8_t addr)
{
  uint8_t tx[2] = {addr & 0x7F, 0x00};
  uint8_t rx[2] = {0, 0};

  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_RESET);
  HAL_SPI_TransmitReceive(&hspi1, tx, rx, 2, HAL_MAX_DELAY);
  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_SET);

  return rx[1];
}

void rfm_write_reg(uint8_t addr, uint8_t val)
{
  uint8_t tx[2] = {addr | 0x80, val};

  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_RESET);
  HAL_SPI_Transmit(&hspi1, tx, 2, HAL_MAX_DELAY);
  HAL_GPIO_WritePin(RFM_CS_GPIO_Port, RFM_CS_Pin, GPIO_PIN_SET);
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

  /* Map DIO0 -> RxDone (bits 7:6 = 00 in RegDioMapping1) */
  rfm_write_reg(0x40, 0x00);

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

uint16_t crc16_ccitt(const uint8_t *data, int len)
{
  uint16_t crc = 0xFFFF;
  for (int i = 0; i < len; i++)
  {
    crc ^= ((uint16_t)data[i]) << 8;
    for (int b = 0; b < 8; b++)
    {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021)
                           : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

void build_packet(uint8_t *buf, uint8_t sender_id, uint16_t seq,
                  uint8_t pkt_type, uint8_t mod_kind)
{
  buf[0] = 0xAE;
  buf[1] = 0x5A;
  buf[2] = sender_id;
  buf[3] = (uint8_t)(seq);
  buf[4] = (uint8_t)(seq >> 8);
  buf[5] = 14;
  buf[6] = (uint8_t)((mod_kind << 2) | (pkt_type & 0x03));
  buf[7] = 7;
  buf[8] = 0x00;

  uint32_t ts = HAL_GetTick();
  buf[9]  = (uint8_t)(ts);
  buf[10] = (uint8_t)(ts >> 8);
  buf[11] = (uint8_t)(ts >> 16);
  buf[12] = (uint8_t)(ts >> 24);

  for (int i = 13; i < 30; i++)
  {
    buf[i] = 0xA5;
  }

  uint16_t crc = crc16_ccitt(buf, 30);
  buf[30] = (uint8_t)(crc >> 8);
  buf[31] = (uint8_t)(crc);
}

/* CRC-8/ITU: poly=0x07, init=0x00, no reflect, xorout=0x00. */
static uint8_t crc8_itu(const uint8_t *buf, uint32_t len)
{
  uint8_t crc = 0x00u;
  for (uint32_t i = 0; i < len; i++)
  {
    crc ^= buf[i];
    for (int b = 0; b < 8; b++)
    {
      crc = (crc & 0x80u) ? (uint8_t)((crc << 1) ^ 0x07u)
                          : (uint8_t)(crc << 1);
    }
  }
  return crc;
}

static void build_forwarding_frame(uint8_t out[43], const intercepted_pkt_t *pkt)
{
  out[0] = 0x7Eu;
  out[1] = 0x29u;                                      /* length = 41 */

  out[2] = (uint8_t)(pkt->rx_timestamp_ms      );
  out[3] = (uint8_t)(pkt->rx_timestamp_ms >>  8);
  out[4] = (uint8_t)(pkt->rx_timestamp_ms >> 16);
  out[5] = (uint8_t)(pkt->rx_timestamp_ms >> 24);

  out[6] = (uint8_t)pkt->rssi_dbm;
  out[7] = (uint8_t)pkt->snr_q025;

  out[8] = (uint8_t)(pkt->freq_error_hz      );
  out[9] = (uint8_t)(pkt->freq_error_hz >>  8);

  for (int i = 0; i < 32; i++) out[10 + i] = pkt->raw[i];

  out[42] = crc8_itu(&out[1], 41);                     /* over bytes 1..41 */
}

/* SX1276 frequency-error registers (RegFei[H/M/L] at 0x1D..0x1F).
 * 20-bit signed value; coarse Hz conversion ok at BW=125 kHz. */
static int16_t read_fei_hz(void)
{
  uint8_t h = rfm_read_reg(0x1Du);
  uint8_t m = rfm_read_reg(0x1Eu);
  uint8_t l = rfm_read_reg(0x1Fu);
  int32_t raw = ((int32_t)(h & 0x0Fu) << 16)
              |  ((int32_t)m            <<  8)
              |   (int32_t)l;
  if (raw & 0x00080000) raw |= 0xFFF00000;             /* sign-extend 20-bit */
  int32_t hz = (raw * 32) / 1000;
  if (hz >  32767) hz =  32767;
  if (hz < -32768) hz = -32768;
  return (int16_t)hz;
}

/* Producer: ISR context. Returns 1 on success, 0 on overflow. */
static int ring_push(const intercepted_pkt_t *src)
{
  uint32_t head = ring_head;
  uint32_t next = (head + 1u) & RING_MASK;
  if (next == ring_tail) {
    dropped++;
    return 0;
  }
  ring[head] = *src;
  __DMB();
  ring_head = next;
  return 1;
}

/* Consumer: main-loop context. Returns 1 if a packet was dequeued. */
static int ring_pop(intercepted_pkt_t *dst)
{
  uint32_t tail = ring_tail;
  if (tail == ring_head) return 0;
  *dst = ring[tail];
  __DMB();
  ring_tail = (tail + 1u) & RING_MASK;
  return 1;
}

static int find_highest_rssi_id(uint8_t *out_id)
{
  int8_t   best_rssi = -128;
  int      best_id   = -1;
  uint32_t now       = HAL_GetTick();
  for (int i = 1; i < 256; i++) {
    if (i == BEACON_ID_THREAT) continue;
    if (rssi_table[i].last_seen_ms == 0) continue;
    if ((now - rssi_table[i].last_seen_ms) > RSSI_STALE_MS) continue;
    if (rssi_table[i].rssi_dbm > best_rssi) {
      best_rssi = rssi_table[i].rssi_dbm;
      best_id   = i;
    }
  }
  if (best_id < 0) return -1;
  *out_id = (uint8_t)best_id;
  return 0;
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  if (GPIO_Pin != RFM_DIO0_Pin) return;

  uint8_t irq = rfm_read_reg(0x12u);
  if ((irq & 0x40u) == 0u) {                           /* not RxDone */
    rfm_write_reg(0x12u, 0xFFu);
    return;
  }
  if (irq & 0x20u) {                                   /* PayloadCrcError */
    rfm_write_reg(0x12u, 0xFFu);
    return;
  }

  intercepted_pkt_t pkt;
  uint8_t rx_addr = rfm_read_reg(0x10u);               /* RegFifoRxCurrentAddr */
  rfm_write_reg(0x0Du, rx_addr);
  for (int i = 0; i < 32; i++) pkt.raw[i] = rfm_read_reg(0x00u);

  pkt.rx_timestamp_ms = HAL_GetTick();
  pkt.rssi_dbm        = (int8_t)((int16_t)rfm_read_reg(0x1Au) - 157);
  pkt.snr_q025        = (int8_t)rfm_read_reg(0x19u);
  pkt.freq_error_hz   = read_fei_hz();

  uint8_t sender = pkt.raw[2];
  rssi_table[sender].rssi_dbm     = pkt.rssi_dbm;
  rssi_table[sender].last_seen_ms = pkt.rx_timestamp_ms;

  (void)ring_push(&pkt);
  rx_count++;
  rfm_write_reg(0x12u, 0xFFu);                         /* clear all IRQ flags */
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART3) tx_busy = 0;
}
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
