`default_nettype none
`timescale 1ns / 1ps

/* Testbench wrapper for test.py: instantiates the design and gives every used
   pin its own signal, so that the cocotb coroutines driving SPI and PDM never
   have to share a bus.
*/
module tb ();

  // Dump the pin-level signals to a FST file. You can view it with gtkwave or surfer.
  // Only this module is dumped: the full hierarchy makes the file hundreds of MB.
  initial begin
    $dumpfile("tb.fst");
    $dumpvars(1, tb);
    #1;
  end

  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] uio_in;
  wire [7:0] ui_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;
`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  // Inputs, driven by test.py
  reg spi_sck;
  reg spi_mosi;
  reg spi_cs_n;
  reg pdm_data;
  assign ui_in = {4'b0000, pdm_data, spi_cs_n, spi_mosi, spi_sck};

  // Outputs, observed by test.py
  wire pdm_clk     = uo_out[0];
  wire i2s_bclk    = uo_out[1];
  wire i2s_lrclk   = uo_out[2];
  wire i2s_sdata   = uo_out[3];
  wire spi_miso    = uio_out[0];
  wire spi_miso_oe = uio_oe[0];

  tt_um_top dut (

      // Include power ports for the Gate Level test:
`ifdef GL_TEST
      .VPWR(VPWR),
      .VGND(VGND),
`endif

      .ui_in  (ui_in),    // Dedicated inputs
      .uo_out (uo_out),   // Dedicated outputs
      .uio_in (uio_in),   // IOs: Input path
      .uio_out(uio_out),  // IOs: Output path
      .uio_oe (uio_oe),   // IOs: Enable path (active high: 0=input, 1=output)
      .ena    (ena),      // enable - goes high when design is selected
      .clk    (clk),      // clock
      .rst_n  (rst_n)     // not reset
  );

endmodule
