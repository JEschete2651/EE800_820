library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity ingest_top is
    port (
        CLK100MHZ    : in  std_logic;
        CPU_RESETN   : in  std_logic;                       -- active-low pushbutton
        uart_rx_pin  : in  std_logic;                       -- PMOD JA pin 1 (C17)
        UART_RXD_OUT : out std_logic;                       -- onboard USB-UART (LH2-A)
        SW           : in  std_logic_vector(15 downto 0);
        CA, CB, CC, CD, CE, CF, CG : out std_logic;
        DP           : out std_logic;
        AN           : out std_logic_vector(7 downto 0);
        LED          : out std_logic_vector(15 downto 0)
    );
end ingest_top;

architecture rtl of ingest_top is
    signal rst_n      : std_logic;

    signal rx_data    : std_logic_vector(7 downto 0);
    signal rx_strobe  : std_logic;

    signal fifo_data  : std_logic_vector(7 downto 0);
    signal fifo_rd_en : std_logic;
    signal fifo_empty : std_logic;
    signal fifo_full  : std_logic;

    signal metadata     : std_logic_vector(63 downto 0);
    signal payload      : std_logic_vector(255 downto 0);
    signal rx_crc       : std_logic_vector(7 downto 0);
    signal frame_valid  : std_logic;
    signal frame_reject : std_logic;

    signal feat_busy    : std_logic;
    signal bram_wr_en   : std_logic;
    signal bram_wr_addr : std_logic_vector(7 downto 0);
    signal bram_wr_data : std_logic_vector(255 downto 0);
    signal bram_rd_addr : std_logic_vector(7 downto 0);
    signal bram_rd_data : std_logic_vector(255 downto 0);

    -- Module 3 host readback path. SW(7:0) selects the BRAM row;
    -- SW(12:8) selects which of 32 bytes within that row goes to LED(15:8).
    -- The LH2-G testbench reaches host_rd_data_int via VHDL-2008 external name.
    signal host_rd_data_int : std_logic_vector(255 downto 0);
    signal host_rd_byte     : std_logic_vector(7 downto 0);
begin
    rst_n <= CPU_RESETN;

    u_uart : entity work.uart_rx
        port map (clk => CLK100MHZ, rst_n => rst_n,
                  rx => uart_rx_pin,
                  rx_data => rx_data, rx_strobe => rx_strobe);

    u_fifo : entity work.byte_fifo
        port map (clk => CLK100MHZ, rst_n => rst_n,
                  wr_en => rx_strobe, wr_data => rx_data,
                  rd_en => fifo_rd_en, rd_data => fifo_data,
                  empty => fifo_empty, full => fifo_full);

    u_parser : entity work.pkt_parser
        port map (clk => CLK100MHZ, rst_n => rst_n,
                  fifo_empty => fifo_empty, fifo_data => fifo_data,
                  fifo_rd_en => fifo_rd_en,
                  feat_busy => feat_busy,
                  metadata => metadata, payload => payload, rx_crc => rx_crc,
                  frame_valid => frame_valid, frame_reject => frame_reject);

    u_feat : entity work.feature_extract
        port map (clk => CLK100MHZ, rst_n => rst_n,
                  frame_valid => frame_valid,
                  metadata => metadata, payload => payload,
                  feat_busy => feat_busy,
                  bram_wr_en => bram_wr_en, bram_wr_addr => bram_wr_addr,
                  bram_wr_data => bram_wr_data,
                  bram_rd_addr => bram_rd_addr, bram_rd_data => bram_rd_data);

    u_bram : entity work.feature_bram
        port map (clk => CLK100MHZ, rst_n => rst_n,
                  wr_en => bram_wr_en, wr_addr => bram_wr_addr, wr_data => bram_wr_data,
                  rd_addr_a => bram_rd_addr, rd_data_a => bram_rd_data,
                  rd_addr_b => SW(7 downto 0), rd_data_b => host_rd_data_int);

    -- Byte selector inside the 32-byte feature row.
    process (host_rd_data_int, SW)
        variable idx : integer range 0 to 31;
    begin
        idx := to_integer(unsigned(SW(12 downto 8)));
        host_rd_byte <= host_rd_data_int((idx * 8 + 7) downto (idx * 8));
    end process;

    -- Seven-segment display retired in this handout; force outputs inactive.
    -- (seg7_driver.vhd remains on disk for course-archive reference but is
    -- no longer instantiated.)
    CA <= '1'; CB <= '1'; CC <= '1'; CD <= '1';
    CE <= '1'; CF <= '1'; CG <= '1'; DP <= '1';
    AN <= (others => '1');

    LED(0)             <= rx_strobe;
    LED(1)             <= frame_valid;
    LED(2)             <= fifo_empty;
    LED(3)             <= fifo_full;
    LED(4)             <= frame_reject;
    LED(5)             <= feat_busy;
    LED(7 downto 6)    <= (others => '0');
    LED(15 downto 8)   <= host_rd_byte;

    -- Passthrough: forward the raw PMOD JA1 stream out the onboard USB-UART
    -- (added in LH2-A so the host can capture .bin files via the same USB
    -- cable that programs the board). Both ends are 115200 8N1.
    UART_RXD_OUT <= uart_rx_pin;
end rtl;
