library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity feature_extract is
    port (
        clk          : in  std_logic;
        rst_n        : in  std_logic;
        -- From pkt_parser
        frame_valid  : in  std_logic;
        metadata     : in  std_logic_vector(63 downto 0);
        payload      : in  std_logic_vector(255 downto 0);
        feat_busy    : out std_logic;
        -- BRAM ports
        bram_wr_en   : out std_logic;
        bram_wr_addr : out std_logic_vector(7 downto 0);
        bram_wr_data : out std_logic_vector(255 downto 0);
        bram_rd_addr : out std_logic_vector(7 downto 0);
        bram_rd_data : in  std_logic_vector(255 downto 0)
    );
end feature_extract;

architecture rtl of feature_extract is
    type state_t is (S_IDLE, S_READ, S_COMPUTE, S_WRITE);
    signal state : state_t := S_IDLE;

    -- Latched inputs (held stable through the three-cycle update).
    signal meta_l    : std_logic_vector(63 downto 0)  := (others => '0');
    signal payload_l : std_logic_vector(255 downto 0) := (others => '0');

    -- Helpers: byte slice from the packed payload (byte 0 in LSB).
    function pbyte (p : std_logic_vector(255 downto 0); idx : integer)
        return std_logic_vector is
    begin
        return p((idx * 8 + 7) downto (idx * 8));
    end function;

    function mbyte (m : std_logic_vector(63 downto 0); idx : integer)
        return std_logic_vector is
    begin
        return m((idx * 8 + 7) downto (idx * 8));
    end function;
begin
    feat_busy <= '0' when state = S_IDLE else '1';

    process (clk)
        variable beacon       : std_logic_vector(7 downto 0);
        variable mod_code     : std_logic_vector(7 downto 0);
        variable pkt_type     : std_logic_vector(7 downto 0);
        variable mod_kind     : std_logic_vector(7 downto 0);
        variable sf           : std_logic_vector(7 downto 0);
        variable rssi_s       : signed(15 downto 0);
        variable snr_s        : signed(15 downto 0);
        variable cur_ts       : unsigned(31 downto 0);
        variable old_ts       : unsigned(31 downto 0);
        variable old_rssi     : signed(15 downto 0);
        variable old_count    : unsigned(31 downto 0);
        variable new_count    : unsigned(31 downto 0);
        variable inter_arr    : unsigned(31 downto 0);
        variable rssi_delta   : signed(31 downto 0);
        variable priority     : signed(31 downto 0);
        variable target_id    : std_logic_vector(7 downto 0);
        variable pause_dur    : std_logic_vector(7 downto 0);
        variable vec          : std_logic_vector(255 downto 0);
    begin
        if rising_edge(clk) then
            bram_wr_en <= '0';

            if rst_n = '0' then
                state <= S_IDLE;
            else
                case state is
                    when S_IDLE =>
                        if frame_valid = '1' then
                            meta_l       <= metadata;
                            payload_l    <= payload;
                            bram_rd_addr <= pbyte(payload, 2);   -- Beacon ID
                            state        <= S_READ;
                        end if;
                    when S_READ =>
                        -- BRAM read latency = 1 cycle; read data appears next cycle.
                        state <= S_COMPUTE;
                    when S_COMPUTE =>
                        beacon    := pbyte(payload_l, 2);
                        mod_code  := pbyte(payload_l, 6);
                        sf        := pbyte(payload_l, 7);
                        pkt_type  := "000000" & mod_code(1 downto 0);
                        mod_kind  := "00" & mod_code(7 downto 2);

                        rssi_s    := resize(signed(mbyte(meta_l, 4)), 16);
                        snr_s     := resize(signed(mbyte(meta_l, 5)), 16);
                        cur_ts    := unsigned(mbyte(meta_l, 3) & mbyte(meta_l, 2)
                                              & mbyte(meta_l, 1) & mbyte(meta_l, 0));

                        -- Decode previously-stored fields from bram_rd_data.
                        old_ts    := unsigned(bram_rd_data(127 downto 96));   -- offsets 12..15
                        old_count := unsigned(bram_rd_data(95 downto 64));    -- offsets 8..11
                        old_rssi  := signed(bram_rd_data(47 downto 32));      -- offsets 4..5

                        new_count := old_count + 1;
                        inter_arr := cur_ts - old_ts;
                        rssi_delta := resize(rssi_s, 32) - resize(old_rssi, 32);
                        priority   := shift_left(resize(rssi_s, 32), 2)
                                      + resize(snr_s, 32)
                                      + signed(resize(new_count, 32));

                        if pkt_type = x"02" then
                            target_id := pbyte(payload_l, 13);   -- LH1-G buf[13]
                            pause_dur := pbyte(payload_l, 14);   -- LH1-G buf[14]
                        else
                            target_id := (others => '0');
                            pause_dur := (others => '0');
                        end if;

                        -- Pack the 32-byte feature vector. Byte 0 in LSB.
                        vec := (others => '0');
                        vec(7 downto 0)     := beacon;                                           -- 0
                        vec(15 downto 8)    := mod_kind;                                         -- 1
                        vec(23 downto 16)   := sf;                                               -- 2
                        vec(31 downto 24)   := pkt_type;                                         -- 3
                        vec(47 downto 32)   := std_logic_vector(rssi_s);                         -- 4-5
                        vec(63 downto 48)   := std_logic_vector(snr_s);                          -- 6-7
                        vec(95 downto 64)   := std_logic_vector(new_count);                      -- 8-11
                        vec(127 downto 96)  := std_logic_vector(cur_ts);                         -- 12-15
                        vec(159 downto 128) := std_logic_vector(inter_arr);                      -- 16-19
                        vec(191 downto 160) := std_logic_vector(rssi_delta);                     -- 20-23
                        vec(223 downto 192) := std_logic_vector(priority);                       -- 24-27
                        vec(231 downto 224) := target_id;                                        -- 28
                        vec(239 downto 232) := pause_dur;                                        -- 29
                        -- 30-31 left zero.

                        bram_wr_addr <= beacon;
                        bram_wr_data <= vec;
                        bram_wr_en   <= '1';
                        state        <= S_WRITE;
                    when S_WRITE =>
                        state <= S_IDLE;
                end case;
            end if;
        end if;
    end process;
end rtl;
