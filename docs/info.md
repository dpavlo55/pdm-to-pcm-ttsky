<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

The PDM-to-PCM Converter accepts a stereo Pulse Density Modulation (PDM) stream from a digital MEMS microphone, decimates it through dual-channel Cascaded Integrator-Comb (CIC) filters, and outputs standard I²S stereo PCM audio. An SPI slave interface (Mode 0) provides register-level control over the PDM clock frequency and converter enable.

**Key Parameters:**
- System clock: 50 MHz
- PDM clock: Programmable via NCO (typ. 1–4 MHz)
- CIC filter: 3rd order, decimation ratio 32
- PCM output: 8-bit per channel, 16-bit I²S word
- Control: SPI Mode 0, 8-bit registers

For the full architecture and programming reference, see [detailed_info.md](detailed_info.md).

## How to test

1. Connect a PDM MEMS microphone (DATA → `ui_in[3]`, CLK ← `uo_out[0]`)
2. Connect an SPI master (SCK → `ui_in[0]`, MOSI → `ui_in[1]`, CS_N → `ui_in[2]`, MISO ← `uio[0]`)
3. Apply 50 MHz clock, assert reset for ≥16 cycles, then de-assert
4. Read VERSION register (address `0x05`) — expected `0xDA`
5. Write NCO_CONTROL_LOW (`0x01`) and NCO_CONTROL_HIGH (`0x02`) to set PDM clock frequency
6. Set CONTROL.enable (`0x00`, bit 0) to `1`
7. Read PCM data from DATA_LEFT (`0x04`) and DATA_RIGHT (`0x03`), or capture I²S output on `uo_out[3:1]`

## External hardware

- **PDM MEMS Microphone** with stereo output
- **SPI Master MCU** (Raspberry Pi, Arduino, or similar)
- **I²S DAC / Audio Codec** (optional)
