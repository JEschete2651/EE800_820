library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity feature_bram is
    port (
        clk      : in  std_logic;
        rst_n    : in  std_logic;
        -- Write port (driven by feature_extract).
        wr_en    : in  std_logic;
        wr_addr  : in  std_logic_vector(7 downto 0);
        wr_data  : in  std_logic_vector(255 downto 0);
        -- Read port (driven by feature_extract for read-modify-write,
        -- and by the Module 3 host interface for readback).
        rd_addr_a : in  std_logic_vector(7 downto 0);
        rd_data_a : out std_logic_vector(255 downto 0);
        rd_addr_b : in  std_logic_vector(7 downto 0);
        rd_data_b : out std_logic_vector(255 downto 0)
    );
end feature_bram;

architecture rtl of feature_bram is
    type mem_t is array (0 to 255) of std_logic_vector(255 downto 0);
    signal mem : mem_t := (others => (others => '0'));
begin
    process (clk) begin
        if rising_edge(clk) then
            if rst_n = '0' then
                mem       <= (others => (others => '0'));
                rd_data_a <= (others => '0');
                rd_data_b <= (others => '0');
            else
                if wr_en = '1' then
                    mem(to_integer(unsigned(wr_addr))) <= wr_data;
                end if;
                rd_data_a <= mem(to_integer(unsigned(rd_addr_a)));
                rd_data_b <= mem(to_integer(unsigned(rd_addr_b)));
            end if;
        end if;
    end process;
end rtl;
