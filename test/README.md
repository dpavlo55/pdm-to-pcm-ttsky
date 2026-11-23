# cocotb testbench

These tests drive the design through its Tiny Tapeout pins only (SPI, PDM and I²S), so the same tests run on the
RTL and on the gate-level netlist. They use [cocotb](https://docs.cocotb.org/en/stable/) and Icarus Verilog.

| Test | What it checks |
|------|----------------|
| `test_registers` | Register reset values over SPI, read/write of `control` and `nco_control`, reserved bits of `control` read as 0, writes to the read-only registers are ignored, SPI_MISO is driven only while SPI_CS_N is low |
| `test_pdm_clock` | PDM clock period for `step` = 4096 (exactly 32 clock cycles), average frequency and 32/33-cycle periods for `step` = 4027, no PDM clock while disabled |
| `test_audio` | Two PDM microphones play different sines (the left one with a full-scale burst) at 3.125 MHz. Every I²S word of both channels must match a bit-accurate model of the CIC filter, including the saturated full-scale samples. After the converter is disabled, the data registers read over SPI must hold the model's last sample of each channel |

| File | Contents |
|------|----------|
| [test.py](test.py) | The tests, an SPI master, the PDM microphones and an I²S receiver |
| [pdm_model.py](pdm_model.py) | Bit-accurate CIC filter model (N = 4, R = 32) and a second-order sigma-delta modulator |
| [tb.v](tb.v) | Verilog wrapper around `tt_um_top` with one signal per used pin |

The design is verified in much more depth by the UVM testbench in the separate verification repository; these
tests are a quick end-to-end check for CI and for the gate-level netlist.

## How to run

To run the RTL simulation:

```sh
make -B
```

To run the gate-level simulation, first harden the project and copy
`../runs/wokwi/results/final/verilog/gl/tt_um_top.v` to `gate_level_netlist.v`. Then run:

```sh
make -B GATES=yes
```

The results are in `results.xml`. `make` returns success even when a test fails, so check that file (CI runs
`! grep failure results.xml`).

## Waveforms

`tb.fst` holds the pin-level signals of `tb.v`. To dump the whole design, change `$dumpvars(1, tb)` to
`$dumpvars(0, tb)` in `tb.v`; the file then grows to several hundred MB.

```sh
gtkwave tb.fst tb.gtkw
surfer tb.fst
```
