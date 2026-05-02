library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use STD.TEXTIO.ALL;

entity tb_uart_rx is
end tb_uart_rx;

architecture sim of tb_uart_rx is
    constant CLK_PERIOD : time    := 10 ns;          -- 100 MHz
    constant BIT_PERIOD : time    := 8680 ns;        -- 1/115200

    signal clk       : std_logic := '0';
    signal rst_n     : std_logic := '0';
    signal rx        : std_logic := '1';             -- idle high
    signal rx_data   : std_logic_vector(7 downto 0);
    signal rx_strobe : std_logic;

    signal strobe_count : integer := 0;
    signal last_byte    : std_logic_vector(7 downto 0) := (others => '0');

    function slv_to_hex (v : std_logic_vector(7 downto 0)) return string is
        constant HEX : string(1 to 16) := "0123456789ABCDEF";
        variable hi  : integer := to_integer(unsigned(v(7 downto 4)));
        variable lo  : integer := to_integer(unsigned(v(3 downto 0)));
    begin
        return HEX(hi + 1) & HEX(lo + 1);
    end function;

    procedure send_byte (signal s : out std_logic; b : in std_logic_vector(7 downto 0)) is
    begin
        s <= '0'; wait for BIT_PERIOD;                -- start
        for i in 0 to 7 loop
            s <= b(i); wait for BIT_PERIOD;           -- LSB first
        end loop;
        s <= '1'; wait for BIT_PERIOD;                -- stop
    end procedure;
begin
    -- Clock generator
    clk <= not clk after CLK_PERIOD / 2;

    -- DUT
    dut : entity work.uart_rx
        port map (clk => clk, rst_n => rst_n,
                  rx => rx, rx_data => rx_data, rx_strobe => rx_strobe);

    -- Strobe counter / capture
    process (clk) begin
        if rising_edge(clk) then
            if rx_strobe = '1' then
                strobe_count <= strobe_count + 1;
                last_byte    <= rx_data;
            end if;
        end if;
    end process;

    -- Stimulus
    process
    begin
        wait for 100 ns;
        rst_n <= '1';
        wait for 1 us;

        send_byte(rx, x"A5");
        wait for 200 us;                              -- generous settle

        assert strobe_count = 1
            report "expected exactly one rx_strobe pulse, got "
                   & integer'image(strobe_count) severity failure;
        assert last_byte = x"A5"
            report "expected rx_data=0xA5, got 0x"
                   & slv_to_hex(last_byte) severity failure;

        report "tb_uart_rx PASS" severity note;
        std.env.finish;
    end process;
end sim;
