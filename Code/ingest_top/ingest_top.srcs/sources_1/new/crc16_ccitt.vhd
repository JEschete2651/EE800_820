library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity crc16_ccitt is
    port (
        clk      : in  std_logic;
        rst_n    : in  std_logic;
        crc_init : in  std_logic;                           -- pulse high to load 0xFFFF
        byte_en  : in  std_logic;
        byte_in  : in  std_logic_vector(7 downto 0);
        crc_out  : out std_logic_vector(15 downto 0)
    );
end crc16_ccitt;

architecture rtl of crc16_ccitt is
    signal crc_r : std_logic_vector(15 downto 0) := (others => '1');

    function update16 (crc : std_logic_vector(15 downto 0);
                       d   : std_logic_vector(7 downto 0)) return std_logic_vector is
        variable c  : std_logic_vector(15 downto 0) := crc;
        variable fb : std_logic;
    begin
        for i in 7 downto 0 loop
            fb := c(15) xor d(i);
            c  := c(14 downto 0) & '0';
            if fb = '1' then
                c := c xor x"1021";
            end if;
        end loop;
        return c;
    end function;
begin
    crc_out <= crc_r;
    process (clk) begin
        if rising_edge(clk) then
            if rst_n = '0' then
                crc_r <= (others => '1');
            elsif crc_init = '1' then
                crc_r <= (others => '1');
            elsif byte_en = '1' then
                crc_r <= update16(crc_r, byte_in);
            end if;
        end if;
    end process;
end rtl;
