library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_feature_extract is
end tb_feature_extract;

architecture sim of tb_feature_extract is
    constant CLK_PERIOD : time := 10 ns;

    signal clk     : std_logic := '0';
    signal rst_n   : std_logic := '0';

    signal frame_valid : std_logic := '0';
    signal metadata    : std_logic_vector(63 downto 0)  := (others => '0');
    signal payload     : std_logic_vector(255 downto 0) := (others => '0');
    signal feat_busy   : std_logic;

    signal wr_en   : std_logic;
    signal wr_addr : std_logic_vector(7 downto 0);
    signal wr_data : std_logic_vector(255 downto 0);
    signal rd_a    : std_logic_vector(7 downto 0);
    signal rd_da   : std_logic_vector(255 downto 0);
    signal rd_b    : std_logic_vector(7 downto 0) := (others => '0');
    signal rd_db   : std_logic_vector(255 downto 0);

    procedure inject_frame (signal fv : out std_logic;
                            signal m  : out std_logic_vector(63 downto 0);
                            signal p  : out std_logic_vector(255 downto 0);
                            beacon  : std_logic_vector(7 downto 0);
                            mod_b6  : std_logic_vector(7 downto 0);
                            ts      : unsigned(31 downto 0);
                            rssi    : signed(7 downto 0);
                            snr     : signed(7 downto 0);
                            tgt     : std_logic_vector(7 downto 0);
                            dur     : std_logic_vector(7 downto 0)) is
        variable mv : std_logic_vector(63 downto 0)  := (others => '0');
        variable pv : std_logic_vector(255 downto 0) := (others => '0');
    begin
        -- metadata bytes 0..3 = timestamp LE; byte 4 = rssi; byte 5 = snr.
        mv(31 downto 0)  := std_logic_vector(ts);
        mv(39 downto 32) := std_logic_vector(rssi);
        mv(47 downto 40) := std_logic_vector(snr);

        -- payload byte 2 = beacon; byte 6 = mod/pkt_type; byte 7 = SF;
        -- payload bytes 13,14 = pause target/duration.
        pv(23 downto 16)   := beacon;
        pv(55 downto 48)   := mod_b6;
        pv(63 downto 56)   := x"07";
        pv(111 downto 104) := tgt;
        pv(119 downto 112) := dur;

        m <= mv;
        p <= pv;
        fv <= '1';
        wait until rising_edge(clk);
        fv <= '0';
        wait until feat_busy = '0';
        wait until rising_edge(clk);
    end procedure;
begin
    clk <= not clk after CLK_PERIOD / 2;

    u_feat : entity work.feature_extract
        port map (clk => clk, rst_n => rst_n,
                  frame_valid => frame_valid,
                  metadata => metadata, payload => payload,
                  feat_busy => feat_busy,
                  bram_wr_en => wr_en, bram_wr_addr => wr_addr, bram_wr_data => wr_data,
                  bram_rd_addr => rd_a, bram_rd_data => rd_da);

    u_bram : entity work.feature_bram
        port map (clk => clk, rst_n => rst_n,
                  wr_en => wr_en, wr_addr => wr_addr, wr_data => wr_data,
                  rd_addr_a => rd_a, rd_data_a => rd_da,
                  rd_addr_b => rd_b, rd_data_b => rd_db);

    process
    begin
        wait for 100 ns;
        rst_n <= '1';
        wait for 200 ns;

        -- 3 DATA frames from ID 0x01: mod_code = 0x04 (mod_kind=1 LoRa, pkt_type=0).
        inject_frame(frame_valid, metadata, payload,
                     x"01", x"04", x"00000064", to_signed(-50, 8),
                     to_signed(20, 8), x"00", x"00");
        inject_frame(frame_valid, metadata, payload,
                     x"01", x"04", x"00000078", to_signed(-48, 8),
                     to_signed(21, 8), x"00", x"00");
        inject_frame(frame_valid, metadata, payload,
                     x"01", x"04", x"0000008C", to_signed(-49, 8),
                     to_signed(22, 8), x"00", x"00");

        -- 2 ACK frames from ID 0x02: mod_code = 0x05 (pkt_type=1).
        inject_frame(frame_valid, metadata, payload,
                     x"02", x"05", x"00000070", to_signed(-55, 8),
                     to_signed(18, 8), x"00", x"00");
        inject_frame(frame_valid, metadata, payload,
                     x"02", x"05", x"00000098", to_signed(-54, 8),
                     to_signed(19, 8), x"00", x"00");

        -- 1 PAUSE frame from ID 0xFF: mod_code = 0x06 (pkt_type=2), target=0x01, dur=0x05.
        inject_frame(frame_valid, metadata, payload,
                     x"FF", x"06", x"000000C0", to_signed(-30, 8),
                     to_signed(25, 8), x"01", x"05");

        -- Read back row 0x01 via host port and check.
        rd_b <= x"01";
        wait until rising_edge(clk);
        wait until rising_edge(clk);
        assert rd_db(95 downto 64) = x"00000003"
            report "row 0x01 frame_count expected 3" severity failure;
        assert rd_db(31 downto 24) = x"00"
            report "row 0x01 pkt_type expected 0x00 (DATA)" severity failure;

        rd_b <= x"02";
        wait until rising_edge(clk);
        wait until rising_edge(clk);
        assert rd_db(95 downto 64) = x"00000002"
            report "row 0x02 frame_count expected 2" severity failure;
        assert rd_db(31 downto 24) = x"01"
            report "row 0x02 pkt_type expected 0x01 (ACK)" severity failure;

        rd_b <= x"FF";
        wait until rising_edge(clk);
        wait until rising_edge(clk);
        assert rd_db(95 downto 64) = x"00000001"
            report "row 0xFF frame_count expected 1" severity failure;
        assert rd_db(31 downto 24) = x"02"
            report "row 0xFF pkt_type expected 0x02 (PAUSE)" severity failure;
        assert rd_db(231 downto 224) = x"01"
            report "row 0xFF target_id_if_pause expected 0x01" severity failure;
        assert rd_db(239 downto 232) = x"05"
            report "row 0xFF pause_duration_units expected 0x05" severity failure;

        report "tb_feature_extract PASS" severity note;
        std.env.finish;
        wait;
    end process;
end sim;
