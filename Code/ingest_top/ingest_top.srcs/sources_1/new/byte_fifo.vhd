library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity byte_fifo is
    generic ( DEPTH : integer := 64 );
    port (
        clk     : in  std_logic;
        rst_n   : in  std_logic;
        wr_en   : in  std_logic;
        wr_data : in  std_logic_vector(7 downto 0);
        rd_en   : in  std_logic;
        rd_data : out std_logic_vector(7 downto 0);
        empty   : out std_logic;
        full    : out std_logic
    );
end byte_fifo;

architecture rtl of byte_fifo is
    type mem_t is array (0 to DEPTH - 1) of std_logic_vector(7 downto 0);
    signal mem   : mem_t := (others => (others => '0'));
    signal w_ptr : integer range 0 to DEPTH - 1 := 0;
    signal r_ptr : integer range 0 to DEPTH - 1 := 0;
    signal count : integer range 0 to DEPTH     := 0;
begin
    full  <= '1' when count = DEPTH else '0';
    empty <= '1' when count = 0     else '0';

    process (clk)
        variable do_wr, do_rd : boolean;
    begin
        if rising_edge(clk) then
            if rst_n = '0' then
                w_ptr <= 0; r_ptr <= 0; count <= 0;
            else
                do_wr := (wr_en = '1') and (count < DEPTH);
                do_rd := (rd_en = '1') and (count > 0);
                if do_wr then
                    mem(w_ptr) <= wr_data;
                    w_ptr <= (w_ptr + 1) mod DEPTH;
                end if;
                if do_rd then
                    r_ptr <= (r_ptr + 1) mod DEPTH;
                end if;
                if    do_wr and not do_rd then count <= count + 1;
                elsif do_rd and not do_wr then count <= count - 1;
                end if;
            end if;
            rd_data <= mem(r_ptr);    -- registered read; valid 1 cycle after rd_en
        end if;
    end process;
end rtl;
