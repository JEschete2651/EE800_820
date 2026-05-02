library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_byte_fifo_overflow is
end tb_byte_fifo_overflow;

architecture sim of tb_byte_fifo_overflow is
    constant CLK_PERIOD : time := 10 ns;

    signal clk     : std_logic := '0';
    signal rst_n   : std_logic := '0';
    signal wr_en   : std_logic := '0';
    signal wr_data : std_logic_vector(7 downto 0) := (others => '0');
    signal rd_en   : std_logic := '0';
    signal rd_data : std_logic_vector(7 downto 0);
    signal empty   : std_logic;
    signal full    : std_logic;

    signal full_seen_at : integer := -1;
begin
    clk <= not clk after CLK_PERIOD / 2;

    dut : entity work.byte_fifo
        port map (clk => clk, rst_n => rst_n,
                  wr_en => wr_en, wr_data => wr_data,
                  rd_en => rd_en, rd_data => rd_data,
                  empty => empty, full => full);

    process
    begin
        wait for 100 ns;
        rst_n <= '1';
        wait until rising_edge(clk);

        for i in 0 to 64 loop
            wr_data <= std_logic_vector(to_unsigned(i, 8));
            wr_en   <= '1';
            wait until rising_edge(clk);
            if full = '1' and full_seen_at = -1 then
                full_seen_at <= i;
            end if;
        end loop;
        wr_en <= '0';
        wait until rising_edge(clk);

        assert full = '1'
            report "FIFO should still be full after 65 writes" severity failure;
        assert full_seen_at = 64
            report "full should first assert when count reaches 64, observed at "
                   & integer'image(full_seen_at) severity failure;

        -- Reset and confirm the pointers/count return to a clean state.
        rst_n <= '0';
        wait until rising_edge(clk);
        rst_n <= '1';
        wait until rising_edge(clk);
        wait until rising_edge(clk);
        assert empty = '1' report "FIFO should be empty after reset" severity failure;
        assert full  = '0' report "FIFO should not be full after reset" severity failure;

        report "tb_byte_fifo_overflow PASS" severity note;
        std.env.finish;
    end process;
end sim;
