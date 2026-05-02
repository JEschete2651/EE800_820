library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use STD.TEXTIO.ALL;

entity tb_ingest_top is
end tb_ingest_top;

architecture sim of tb_ingest_top is
    constant CLK_PERIOD   : time   := 10 ns;
    constant BIT_PERIOD   : time   := 8680 ns;
    constant CAPTURE_FILE : string := "../../../../data/capture_mixed.bin";
    constant DUMP_FILE    : string := "../../../../data/dump_mixed.txt";
    constant LOG_FILE     : string := "../../../../data/events_mixed.txt";

    signal clk         : std_logic := '0';
    signal cpu_resetn  : std_logic := '0';
    signal uart_rx_pin : std_logic := '1';
    signal uart_rxd_out : std_logic;
    signal sw          : std_logic_vector(15 downto 0) := (others => '0');

    signal ca, cb, cc, cd, ce, cf, cg : std_logic;
    signal dp                          : std_logic;
    signal an                          : std_logic_vector(7 downto 0);
    signal led                         : std_logic_vector(15 downto 0);

    type charfile is file of character;

    procedure send_byte (signal s : out std_logic;
                         b : in std_logic_vector(7 downto 0)) is
    begin
        s <= '0'; wait for BIT_PERIOD;
        for i in 0 to 7 loop
            s <= b(i); wait for BIT_PERIOD;
        end loop;
        s <= '1'; wait for BIT_PERIOD;
    end procedure;

    -- VHDL-2008 external name reaches the internal 256-bit BRAM readback
    -- signal inside ingest_top so the testbench can dump the full feature row.
    alias host_rd_data_int is
        << signal .tb_ingest_top.dut.host_rd_data_int :
           std_logic_vector(255 downto 0) >>;
begin
    clk <= not clk after CLK_PERIOD / 2;

    dut : entity work.ingest_top
        port map (CLK100MHZ => clk, CPU_RESETN => cpu_resetn,
                  uart_rx_pin => uart_rx_pin,
                  UART_RXD_OUT => uart_rxd_out,
                  SW => sw,
                  CA => ca, CB => cb, CC => cc, CD => cd,
                  CE => ce, CF => cf, CG => cg,
                  DP => dp, AN => an, LED => led);

    -- Event log: timestamped frame_valid / frame_reject pulses.
    -- led(1) = frame_valid, led(4) = frame_reject (per LH2-F ingest_top).
    process
        file     fh        : text open write_mode is LOG_FILE;
        variable l         : line;
        variable t_ns      : integer;
        variable prev_fv   : std_logic := '0';
        variable prev_fr   : std_logic := '0';
    begin
        loop
            wait until rising_edge(clk);
            if led(1) = '1' and prev_fv = '0' then
                t_ns := now / 1 ns;
                write(l, string'("VALID @ "));
                write(l, t_ns);
                writeline(fh, l);
            end if;
            if led(4) = '1' and prev_fr = '0' then
                t_ns := now / 1 ns;
                write(l, string'("REJECT @ "));
                write(l, t_ns);
                writeline(fh, l);
            end if;
            prev_fv := led(1);
            prev_fr := led(4);
        end loop;
    end process;

    process
        file     fh   : charfile;
        file     fh_d : text open write_mode is DUMP_FILE;
        variable ch   : character;
        variable b    : std_logic_vector(7 downto 0);
        variable l    : line;
        variable open_status : file_open_status;
    begin
        wait for 200 ns;
        cpu_resetn <= '1';
        wait for 1 us;

        file_open(open_status, fh, CAPTURE_FILE, read_mode);
        assert open_status = open_ok
            report "Could not open " & CAPTURE_FILE severity failure;

        while not endfile(fh) loop
            read(fh, ch);
            b := std_logic_vector(to_unsigned(character'pos(ch), 8));
            send_byte(uart_rx_pin, b);
        end loop;
        file_close(fh);

        -- Drain time: allow last frame to traverse parser + extractor + BRAM.
        wait for 500 us;

        -- Walk every row of the BRAM and dump as hex strings. SW(7:0) drives
        -- the row address inside ingest_top; SW(12:8) is unused for the dump
        -- (the testbench reads the full 256-bit row via the external name).
        for row in 0 to 255 loop
            sw(7 downto 0) <= std_logic_vector(to_unsigned(row, 8));
            wait until rising_edge(clk);
            wait until rising_edge(clk);             -- 1-cycle BRAM read latency
            write(l, string'("ROW "));
            hwrite(l, std_logic_vector(to_unsigned(row, 8)));
            write(l, string'(" "));
            hwrite(l, host_rd_data_int);
            writeline(fh_d, l);
        end loop;

        report "tb_ingest_top: dump complete" severity note;
        std.env.finish;
    end process;
end sim;
