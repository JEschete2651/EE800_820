library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity frame_detector is
    port (
        clk         : in  std_logic;
        rst_n       : in  std_logic;
        -- byte_fifo read interface
        fifo_empty  : in  std_logic;
        fifo_data   : in  std_logic_vector(7 downto 0);
        fifo_rd_en  : out std_logic;
        -- Outputs
        beacon_id   : out std_logic_vector(7 downto 0);  -- frame byte 12
        new_frame   : out std_logic                       -- 1-cycle pulse on full frame
    );
end frame_detector;

architecture rtl of frame_detector is
    type state_t is (S_HUNT, S_REQ, S_WAIT, S_CAPTURE);
    signal state     : state_t := S_HUNT;
    signal byte_idx  : integer range 0 to 63 := 0;
    signal beacon_r  : std_logic_vector(7 downto 0) := (others => '0');
begin
    beacon_id <= beacon_r;

    process (clk) begin
        if rising_edge(clk) then
            new_frame  <= '0';
            fifo_rd_en <= '0';

            if rst_n = '0' then
                state    <= S_HUNT;
                byte_idx <= 0;
                beacon_r <= (others => '0');
            else
                case state is
                    when S_HUNT =>
                        -- Pop bytes one at a time until we see 0x7E.
                        if fifo_empty = '0' then
                            fifo_rd_en <= '1';
                            state      <= S_WAIT;
                            byte_idx   <= 0;
                        end if;
                    when S_REQ =>
                        -- Issue a read for the next byte of the frame.
                        if fifo_empty = '0' then
                            fifo_rd_en <= '1';
                            state      <= S_WAIT;
                        end if;
                    when S_WAIT =>
                        -- One-cycle latency: rd_data is valid this cycle.
                        state <= S_CAPTURE;
                    when S_CAPTURE =>
                        if byte_idx = 0 then
                            -- Hunting for the start delimiter.
                            if fifo_data = x"7E" then
                                byte_idx <= 1;
                                state    <= S_REQ;
                            else
                                state <= S_HUNT;          -- still hunting
                            end if;
                        else
                            -- Frame in progress.
                            if byte_idx = 12 then
                                beacon_r <= fifo_data;    -- radio packet byte 2
                            end if;
                            if byte_idx = 42 then
                                new_frame <= '1';
                                state     <= S_HUNT;
                                byte_idx  <= 0;
                            else
                                byte_idx <= byte_idx + 1;
                                state    <= S_REQ;
                            end if;
                        end if;
                end case;
            end if;
        end if;
    end process;
end rtl;
