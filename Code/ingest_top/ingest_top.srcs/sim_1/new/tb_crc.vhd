library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_crc is
end tb_crc;

architecture sim of tb_crc is
    constant CLK_PERIOD : time := 10 ns;

    signal clk     : std_logic := '0';
    signal rst_n   : std_logic := '0';

    signal init8, en8   : std_logic := '0';
    signal byte8        : std_logic_vector(7 downto 0) := (others => '0');
    signal crc8         : std_logic_vector(7 downto 0);

    signal init16, en16 : std_logic := '0';
    signal byte16       : std_logic_vector(7 downto 0) := (others => '0');
    signal crc16        : std_logic_vector(15 downto 0);

    type byte_array_t is array (natural range <>) of std_logic_vector(7 downto 0);
    constant CHECK : byte_array_t := (
        x"31", x"32", x"33", x"34", x"35", x"36", x"37", x"38", x"39"
    );

    -- Local hex formatters. Vivado xsim does not always resolve to_hstring()
    -- for std_logic_vector under the default VHDL version, so build the hex
    -- strings by hand (same pattern used in LH2-B's tb_uart_rx).
    function slv_to_hex8 (v : std_logic_vector(7 downto 0)) return string is
        constant HEX : string(1 to 16) := "0123456789ABCDEF";
        variable hi  : integer := to_integer(unsigned(v(7 downto 4)));
        variable lo  : integer := to_integer(unsigned(v(3 downto 0)));
    begin
        return HEX(hi + 1) & HEX(lo + 1);
    end function;

    function slv_to_hex16 (v : std_logic_vector(15 downto 0)) return string is
    begin
        return slv_to_hex8(v(15 downto 8)) & slv_to_hex8(v(7 downto 0));
    end function;
begin
    clk <= not clk after CLK_PERIOD / 2;

    u_crc8  : entity work.crc8_serial
        port map (clk => clk, rst_n => rst_n,
                  crc_init => init8, byte_en => en8, byte_in => byte8, crc_out => crc8);

    u_crc16 : entity work.crc16_ccitt
        port map (clk => clk, rst_n => rst_n,
                  crc_init => init16, byte_en => en16, byte_in => byte16, crc_out => crc16);

    process
    begin
        wait for 100 ns;
        rst_n <= '1';
        wait until rising_edge(clk);

        init8  <= '1';
        init16 <= '1';
        wait until rising_edge(clk);
        init8  <= '0';
        init16 <= '0';

        for i in CHECK'range loop
            byte8  <= CHECK(i);
            byte16 <= CHECK(i);
            en8    <= '1';
            en16   <= '1';
            wait until rising_edge(clk);
        end loop;
        en8  <= '0';
        en16 <= '0';
        wait until rising_edge(clk);

        assert crc8 = x"F4"
            report "CRC-8 check failed: got 0x" & slv_to_hex8(crc8) severity failure;
        assert crc16 = x"29B1"
            report "CRC-16 check failed: got 0x" & slv_to_hex16(crc16) severity failure;

        report "tb_crc PASS" severity note;
        std.env.finish;
    end process;
end sim;
