library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity uart_rx is
    generic (
        CLK_FREQ_HZ : integer := 100_000_000;
        BAUD        : integer := 115_200
    );
    port (
        clk        : in  std_logic;
        rst_n      : in  std_logic;
        rx         : in  std_logic;
        rx_data    : out std_logic_vector(7 downto 0);
        rx_strobe  : out std_logic
    );
end uart_rx;

architecture rtl of uart_rx is
    constant DIV16 : integer := CLK_FREQ_HZ / (BAUD * 16);  -- 54 at defaults
    signal os_cnt  : unsigned(15 downto 0) := (others => '0');
    signal os_tick : std_logic := '0';

    type state_t is (S_IDLE, S_START, S_DATA, S_STOP);
    signal state    : state_t := S_IDLE;
    signal bit_idx  : unsigned(2 downto 0) := (others => '0');
    signal sub_cnt  : unsigned(3 downto 0) := (others => '0');
    signal shifter  : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_sync1, rx_sync2 : std_logic := '1';
begin
    process (clk) begin
        if rising_edge(clk) then
            rx_sync1 <= rx;
            rx_sync2 <= rx_sync1;
        end if;
    end process;

    process (clk) begin
        if rising_edge(clk) then
            if rst_n = '0' then
                os_cnt  <= (others => '0');
                os_tick <= '0';
            elsif os_cnt = to_unsigned(DIV16 - 1, os_cnt'length) then
                os_cnt  <= (others => '0');
                os_tick <= '1';
            else
                os_cnt  <= os_cnt + 1;
                os_tick <= '0';
            end if;
        end if;
    end process;

    process (clk) begin
        if rising_edge(clk) then
            rx_strobe <= '0';
            if rst_n = '0' then
                state   <= S_IDLE;
                sub_cnt <= (others => '0');
                bit_idx <= (others => '0');
            elsif os_tick = '1' then
                case state is
                    when S_IDLE =>
                        if rx_sync2 = '0' then
                            state   <= S_START;
                            sub_cnt <= to_unsigned(0, 4);
                        end if;
                    when S_START =>
                        if sub_cnt = to_unsigned(7, 4) then
                            if rx_sync2 = '0' then
                                state   <= S_DATA;
                                sub_cnt <= (others => '0');
                                bit_idx <= (others => '0');
                            else
                                state <= S_IDLE;
                            end if;
                        else
                            sub_cnt <= sub_cnt + 1;
                        end if;
                    when S_DATA =>
                        if sub_cnt = to_unsigned(15, 4) then
                            shifter <= rx_sync2 & shifter(7 downto 1);
                            sub_cnt <= (others => '0');
                            if bit_idx = to_unsigned(7, 3) then
                                state <= S_STOP;
                            else
                                bit_idx <= bit_idx + 1;
                            end if;
                        else
                            sub_cnt <= sub_cnt + 1;
                        end if;
                    when S_STOP =>
                        if sub_cnt = to_unsigned(15, 4) then
                            rx_data   <= shifter;
                            rx_strobe <= '1';
                            state     <= S_IDLE;
                        else
                            sub_cnt <= sub_cnt + 1;
                        end if;
                end case;
            end if;
        end if;
    end process;
end rtl;
