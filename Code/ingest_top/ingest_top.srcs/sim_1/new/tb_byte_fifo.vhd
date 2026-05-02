library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_byte_fifo is
end tb_byte_fifo;

architecture sim of tb_byte_fifo is
    constant CLK_PERIOD : time := 10 ns;

    signal clk     : std_logic := '0';
    signal rst_n   : std_logic := '0';
    signal wr_en   : std_logic := '0';
    signal wr_data : std_logic_vector(7 downto 0) := (others => '0');
    signal rd_en   : std_logic := '0';
    signal rd_data : std_logic_vector(7 downto 0);
    signal empty   : std_logic;
    signal full    : std_logic;

    signal mismatch_cnt : integer := 0;
begin
    clk <= not clk after CLK_PERIOD / 2;

    dut : entity work.byte_fifo
        port map (clk => clk, rst_n => rst_n,
                  wr_en => wr_en, wr_data => wr_data,
                  rd_en => rd_en, rd_data => rd_data,
                  empty => empty, full => full);

    process
        variable expected : std_logic_vector(7 downto 0);
    begin
        wait for 100 ns;
        rst_n <= '1';
        wait until rising_edge(clk);

        -- Write 16 ascending bytes 0x10..0x1F.
        for i in 0 to 15 loop
            wr_data <= std_logic_vector(to_unsigned(16#10# + i, 8));
            wr_en   <= '1';
            wait until rising_edge(clk);
        end loop;
        wr_en <= '0';
        wait until rising_edge(clk);

        assert empty = '0' report "FIFO should not be empty after 16 writes" severity failure;
        assert full  = '0' report "FIFO should not be full at depth 16 of 64" severity failure;

        -- Read 16 bytes and compare. Account for 1-cycle read latency by
        -- comparing rd_data on the cycle AFTER each rd_en pulse.
        for i in 0 to 15 loop
            rd_en <= '1';
            wait until rising_edge(clk);
            rd_en <= '0';
            wait until rising_edge(clk);                -- registered output appears now
            expected := std_logic_vector(to_unsigned(16#10# + i, 8));
            if rd_data /= expected then
                mismatch_cnt <= mismatch_cnt + 1;
            end if;
        end loop;

        assert mismatch_cnt = 0
            report "tb_byte_fifo: " & integer'image(mismatch_cnt) & " byte mismatch(es)"
            severity failure;
        assert empty = '1' report "FIFO should be empty after 16 reads" severity failure;
        report "tb_byte_fifo PASS" severity note;
        std.env.finish;
    end process;
end sim;
