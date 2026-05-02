library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity seg7_driver is
    port (
        clk        : in  std_logic;                      -- 100 MHz
        rst_n      : in  std_logic;
        beacon_id  : in  std_logic_vector(7 downto 0);
        new_frame  : in  std_logic;
        seg        : out std_logic_vector(6 downto 0);   -- CA..CG, active low
        dp         : out std_logic;
        an         : out std_logic_vector(7 downto 0)    -- 8 anodes, active low
    );
end seg7_driver;

architecture rtl of seg7_driver is
    -- 17-bit refresh counter: top 2 bits select the digit (~750 Hz/digit at 100 MHz).
    signal refresh_cnt : unsigned(16 downto 0) := (others => '0');
    signal digit_sel   : unsigned(1 downto 0);

    signal frame_cnt   : unsigned(15 downto 0) := (others => '0');
    signal nibble      : std_logic_vector(3 downto 0);
    signal seg_n       : std_logic_vector(6 downto 0);
begin
    dp <= '1';                                  -- decimal point off

    process (clk) begin
        if rising_edge(clk) then
            if rst_n = '0' then
                refresh_cnt <= (others => '0');
                frame_cnt   <= (others => '0');
            else
                refresh_cnt <= refresh_cnt + 1;
                if new_frame = '1' then
                    frame_cnt <= frame_cnt + 1;
                end if;
            end if;
        end if;
    end process;

    digit_sel <= refresh_cnt(refresh_cnt'high downto refresh_cnt'high - 1);

    process (digit_sel, beacon_id, frame_cnt) begin
        case digit_sel is
            when "00"   => nibble <= beacon_id(3 downto 0);
            when "01"   => nibble <= beacon_id(7 downto 4);
            when "10"   => nibble <= std_logic_vector(frame_cnt(3 downto 0));
            when others => nibble <= std_logic_vector(frame_cnt(7 downto 4));
        end case;
    end process;

    process (nibble) begin
        case nibble is
            when x"0" => seg_n <= "1000000";
            when x"1" => seg_n <= "1111001";
            when x"2" => seg_n <= "0100100";
            when x"3" => seg_n <= "0110000";
            when x"4" => seg_n <= "0011001";
            when x"5" => seg_n <= "0010010";
            when x"6" => seg_n <= "0000010";
            when x"7" => seg_n <= "1111000";
            when x"8" => seg_n <= "0000000";
            when x"9" => seg_n <= "0010000";
            when x"A" => seg_n <= "0001000";
            when x"B" => seg_n <= "0000011";
            when x"C" => seg_n <= "1000110";
            when x"D" => seg_n <= "0100001";
            when x"E" => seg_n <= "0000110";
            when others => seg_n <= "0001110";  -- F
        end case;
    end process;
    seg <= seg_n;

    process (digit_sel) begin
        an <= (others => '1');
        case digit_sel is
            when "00"   => an(0) <= '0';
            when "01"   => an(1) <= '0';
            when "10"   => an(2) <= '0';
            when others => an(3) <= '0';
        end case;
    end process;
end rtl;
