library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use STD.TEXTIO.ALL;

entity tb_uart_rx_regression is
end tb_uart_rx_regression;

architecture sim of tb_uart_rx_regression is
    constant CLK_PERIOD   : time   := 10 ns;
    constant BIT_PERIOD   : time   := 8680 ns;
    constant CAPTURE_FILE : string := "../../../../data/capture_clean.bin";

    signal clk       : std_logic := '0';
    signal rst_n     : std_logic := '0';
    signal rx        : std_logic := '1';
    signal rx_data   : std_logic_vector(7 downto 0);
    signal rx_strobe : std_logic;

    signal expected_byte : std_logic_vector(7 downto 0) := (others => '0');
    signal byte_count    : integer := 0;
    signal mismatch_cnt  : integer := 0;

    type charfile is file of character;

    procedure send_byte (signal s : out std_logic; b : in std_logic_vector(7 downto 0)) is
    begin
        s <= '0'; wait for BIT_PERIOD;
        for i in 0 to 7 loop
            s <= b(i); wait for BIT_PERIOD;
        end loop;
        s <= '1'; wait for BIT_PERIOD;
    end procedure;
begin
    clk <= not clk after CLK_PERIOD / 2;

    dut : entity work.uart_rx
        port map (clk => clk, rst_n => rst_n,
                  rx => rx, rx_data => rx_data, rx_strobe => rx_strobe);

    -- Compare each strobed byte against the most recently transmitted byte.
    process (clk) begin
        if rising_edge(clk) then
            if rx_strobe = '1' then
                if rx_data /= expected_byte then
                    mismatch_cnt <= mismatch_cnt + 1;
                end if;
                byte_count <= byte_count + 1;
            end if;
        end if;
    end process;

    process
        file     fh   : charfile;
        variable ch   : character;
        variable byte : std_logic_vector(7 downto 0);
        variable open_status : file_open_status;
    begin
        wait for 100 ns;
        rst_n <= '1';
        wait for 1 us;

        file_open(open_status, fh, CAPTURE_FILE, read_mode);
        assert open_status = open_ok
            report "Could not open capture file " & CAPTURE_FILE severity failure;

        while not endfile(fh) loop
            read(fh, ch);
            byte := std_logic_vector(to_unsigned(character'pos(ch), 8));
            expected_byte <= byte;
            send_byte(rx, byte);
        end loop;

        file_close(fh);
        wait for 200 us;

        assert mismatch_cnt = 0
            report "regression: " & integer'image(mismatch_cnt)
                   & " byte mismatches over " & integer'image(byte_count) severity failure;
        report "tb_uart_rx_regression PASS: " & integer'image(byte_count) & " bytes" severity note;
        std.env.finish;
    end process;
end sim;
