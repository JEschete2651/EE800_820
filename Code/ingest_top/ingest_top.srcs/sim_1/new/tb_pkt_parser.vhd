library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_pkt_parser is
end tb_pkt_parser;

architecture sim of tb_pkt_parser is
    constant CLK_PERIOD : time := 10 ns;

    signal clk          : std_logic := '0';
    signal rst_n        : std_logic := '0';

    -- Behavioural byte source acts as a 1-deep FIFO.
    signal src_data     : std_logic_vector(7 downto 0) := (others => '0');
    signal src_empty    : std_logic := '1';
    signal rd_en        : std_logic;
    signal pending_byte : std_logic_vector(7 downto 0) := (others => '0');
    signal has_pending  : std_logic := '0';

    signal metadata     : std_logic_vector(63 downto 0);
    signal payload      : std_logic_vector(255 downto 0);
    signal rx_crc       : std_logic_vector(7 downto 0);
    signal frame_valid  : std_logic;
    signal frame_reject : std_logic;

    signal valid_count  : integer := 0;
    signal reject_count : integer := 0;
    signal last_id      : std_logic_vector(7 downto 0) := (others => '0');

    -- Build a 43-byte frame with a given Beacon ID, length byte, and a
    -- placeholder CRC (parser doesn't check CRC until LH2-E).
    type byte_array_t is array (natural range <>) of std_logic_vector(7 downto 0);

    function make_frame (beacon : std_logic_vector(7 downto 0);
                         len    : std_logic_vector(7 downto 0)) return byte_array_t is
        variable f : byte_array_t(0 to 42) := (others => (others => '0'));
    begin
        f(0)  := x"7E";
        f(1)  := len;
        -- bytes 2..9 metadata, leave zero
        -- byte 10 = radio packet byte 0, byte 12 = radio packet byte 2 = Beacon ID
        f(12) := beacon;
        -- bytes 13..41 payload, leave zero
        f(42) := x"AA";                                  -- placeholder CRC
        return f;
    end function;

    procedure push_frame (signal pend : out std_logic_vector(7 downto 0);
                          signal hp   : out std_logic;
                          signal r    : in  std_logic;
                          frame       : byte_array_t) is
    begin
        for i in frame'range loop
            pend <= frame(i);
            hp   <= '1';
            -- Wait until parser consumes this byte.
            wait until rising_edge(clk) and r = '1';
            hp <= '0';
            wait until rising_edge(clk);
        end loop;
    end procedure;
begin
    clk <= not clk after CLK_PERIOD / 2;

    -- Behavioural byte source: when has_pending is high, src_empty is low and
    -- src_data is the pending byte. The DUT pulses rd_en; the stimulus
    -- process clears has_pending in response.
    src_empty <= not has_pending;
    src_data  <= pending_byte;

    dut : entity work.pkt_parser
        port map (clk => clk, rst_n => rst_n,
                  fifo_empty => src_empty, fifo_data => src_data,
                  fifo_rd_en => rd_en,
                  feat_busy => '0',
                  metadata => metadata, payload => payload, rx_crc => rx_crc,
                  frame_valid => frame_valid, frame_reject => frame_reject);

    process (clk) begin
        if rising_edge(clk) then
            if frame_valid = '1' then
                valid_count <= valid_count + 1;
                last_id     <= payload(23 downto 16);    -- radio byte 2 = Beacon ID
            end if;
            if frame_reject = '1' then
                reject_count <= reject_count + 1;
            end if;
        end if;
    end process;

    process
    begin
        wait for 100 ns;
        rst_n <= '1';
        wait for 200 ns;

        -- Frame 1: valid, Beacon ID = 0x01.
        push_frame(pending_byte, has_pending, rd_en, make_frame(x"01", x"29"));
        wait for 500 ns;
        assert valid_count = 1
            report "frame 1 should have produced frame_valid" severity failure;
        assert last_id = x"01" report "frame 1 Beacon ID mismatch" severity failure;

        -- Frame 2: bad length byte.
        push_frame(pending_byte, has_pending, rd_en, make_frame(x"02", x"30"));
        wait for 500 ns;
        assert reject_count = 1
            report "frame 2 should have produced frame_reject" severity failure;

        -- Frame 3: valid, Beacon ID = 0x02.
        push_frame(pending_byte, has_pending, rd_en, make_frame(x"02", x"29"));
        wait for 500 ns;
        assert valid_count = 2
            report "frame 3 should have produced second frame_valid" severity failure;
        assert last_id = x"02" report "frame 3 Beacon ID mismatch" severity failure;

        report "tb_pkt_parser PASS" severity note;
        std.env.finish;
        wait;
    end process;
end sim;
