library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity pkt_parser is
    port (
        clk           : in  std_logic;
        rst_n         : in  std_logic;
        fifo_empty    : in  std_logic;
        fifo_data     : in  std_logic_vector(7 downto 0);
        fifo_rd_en    : out std_logic;
        feat_busy     : in  std_logic;
        metadata      : out std_logic_vector(63 downto 0);
        payload       : out std_logic_vector(255 downto 0);
        rx_crc        : out std_logic_vector(7 downto 0);
        frame_valid   : out std_logic;
        frame_reject  : out std_logic
    );
end pkt_parser;

architecture rtl of pkt_parser is
    type state_t is (S_HUNT, S_REQ, S_WAIT, S_CAPTURE, S_VALID, S_REJECT);
    signal state    : state_t := S_HUNT;
    signal byte_idx : integer range 0 to 63 := 0;

    signal meta_r    : std_logic_vector(63 downto 0)  := (others => '0');
    signal payload_r : std_logic_vector(255 downto 0) := (others => '0');
    signal crc_r     : std_logic_vector(7 downto 0)   := (others => '0');

    -- CRC-8 controls
    signal crc8_init : std_logic := '0';
    signal crc8_en   : std_logic := '0';
    signal crc8_byte : std_logic_vector(7 downto 0);
    signal crc8_val  : std_logic_vector(7 downto 0);

    -- CRC-16 controls
    signal crc16_init : std_logic := '0';
    signal crc16_en   : std_logic := '0';
    signal crc16_byte : std_logic_vector(7 downto 0);
    signal crc16_val  : std_logic_vector(15 downto 0);
begin
    metadata <= meta_r;
    payload  <= payload_r;
    rx_crc   <= crc_r;

    u_crc8 : entity work.crc8_serial
        port map (clk => clk, rst_n => rst_n,
                  crc_init => crc8_init, byte_en => crc8_en, byte_in => crc8_byte,
                  crc_out => crc8_val);

    u_crc16 : entity work.crc16_ccitt
        port map (clk => clk, rst_n => rst_n,
                  crc_init => crc16_init, byte_en => crc16_en, byte_in => crc16_byte,
                  crc_out => crc16_val);

    process (clk) begin
        if rising_edge(clk) then
            frame_valid  <= '0';
            frame_reject <= '0';
            fifo_rd_en   <= '0';
            crc8_init    <= '0';
            crc8_en      <= '0';
            crc16_init   <= '0';
            crc16_en     <= '0';

            if rst_n = '0' then
                state    <= S_HUNT;
                byte_idx <= 0;
            else
                case state is
                    when S_HUNT =>
                        if fifo_empty = '0' and feat_busy = '0' then
                            fifo_rd_en <= '1';
                            state      <= S_WAIT;
                            byte_idx   <= 0;
                        end if;
                    when S_REQ =>
                        if fifo_empty = '0' then
                            fifo_rd_en <= '1';
                            state      <= S_WAIT;
                        end if;
                    when S_WAIT =>
                        state <= S_CAPTURE;
                    when S_CAPTURE =>
                        if byte_idx = 0 then
                            if fifo_data = x"7E" then
                                -- Initialize both CRCs at the START of byte 1.
                                crc8_init  <= '1';
                                crc16_init <= '1';
                                byte_idx <= 1;
                                state    <= S_REQ;
                            else
                                state <= S_HUNT;
                            end if;
                        elsif byte_idx = 1 then
                            -- Length byte. Feed CRC-8 (covers bytes 1..41).
                            crc8_byte <= fifo_data;
                            crc8_en   <= '1';
                            if fifo_data = x"29" then
                                byte_idx <= 2;
                                state    <= S_REQ;
                            else
                                state <= S_REJECT;
                            end if;
                        elsif byte_idx >= 2 and byte_idx <= 9 then
                            meta_r(((byte_idx - 2) * 8 + 7) downto ((byte_idx - 2) * 8))
                                <= fifo_data;
                            crc8_byte <= fifo_data;
                            crc8_en   <= '1';
                            byte_idx  <= byte_idx + 1;
                            state     <= S_REQ;
                        elsif byte_idx >= 10 and byte_idx <= 41 then
                            payload_r(((byte_idx - 10) * 8 + 7) downto ((byte_idx - 10) * 8))
                                <= fifo_data;
                            crc8_byte <= fifo_data;
                            crc8_en   <= '1';
                            -- CRC-16 covers radio bytes 0..29 = frame bytes 10..39.
                            if byte_idx <= 39 then
                                crc16_byte <= fifo_data;
                                crc16_en   <= '1';
                            end if;
                            byte_idx <= byte_idx + 1;
                            state    <= S_REQ;
                        elsif byte_idx = 42 then
                            crc_r <= fifo_data;
                            -- CRC-8 check: captured trailing byte must equal running value.
                            --
                            -- CRC-16 reconstruction. The radio packet's embedded CRC-16
                            -- occupies radio bytes 30..31 = frame bytes 40..41. With byte 0
                            -- of the payload mapped to payload_r(7 downto 0), radio byte 30
                            -- lives in payload_r(247 downto 240) and radio byte 31 lives in
                            -- payload_r(255 downto 248). LH1-G transmits the high byte of
                            -- the CRC first (pkt_buf[30] = crc>>8, pkt_buf[31] = crc&0xFF),
                            -- so the original 16-bit value reconstructs as
                            --   (byte30 in MSByte) & (byte31 in LSByte)
                            -- = payload_r(247:240) & payload_r(255:248).
                            if (fifo_data = crc8_val) and
                               (payload_r(247 downto 240) & payload_r(255 downto 248) = crc16_val) then
                                state <= S_VALID;
                            else
                                state <= S_REJECT;
                            end if;
                        end if;
                    when S_VALID =>
                        frame_valid <= '1';
                        state       <= S_HUNT;
                        byte_idx    <= 0;
                    when S_REJECT =>
                        frame_reject <= '1';
                        state        <= S_HUNT;
                        byte_idx     <= 0;
                end case;
            end if;
        end if;
    end process;
end rtl;
