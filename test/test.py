# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0
"""cocotb tests for the PDM-to-PCM converter, driven through the chip pins only.

* test_registers   SPI access: reset values, read/write, read-only registers, MISO enable
* test_pdm_clock   PDM clock frequency set by nco_control, and clock stop when disabled
* test_audio       stereo PDM sine in, I2S samples and data registers out, compared
                   sample by sample against a bit-accurate model of the CIC filter

The tests use only the top-level pins, so they also run on the gate-level netlist.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge, Timer
from cocotb.utils import get_sim_time

from pdm_model import CicModel, sigma_delta, sine

CLK_NS = 20          # 50 MHz project clock
SPI_HALF_NS = 500    # 1 MHz SPI clock
PDM_DELAY_NS = 40    # microphone data-valid delay after the PDM clock edge

# Register addresses
CONTROL = 0x00
NCO_LOW = 0x01
NCO_HIGH = 0x02
RIGHT_LOW = 0x03
RIGHT_HIGH = 0x04
LEFT_LOW = 0x05
LEFT_HIGH = 0x06
ID = 0x07

RESET_VALUES = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xDA]


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

async def start(dut):
    """Start the clock, set all inputs to their idle levels and reset the design."""
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.spi_sck.value = 0
    dut.spi_mosi.value = 0
    dut.spi_cs_n.value = 1
    dut.pdm_data.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 20)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


class SpiMaster:
    """SPI mode 0, MSB first, two-byte transactions."""

    def __init__(self, dut):
        self.dut = dut

    async def transfer(self, byte0, byte1):
        """Send two bytes; return the byte received on MISO during the second one."""
        dut = self.dut
        assert int(dut.spi_miso_oe.value) == 0, "MISO driven while CS_N is high"
        dut.spi_cs_n.value = 0
        await Timer(SPI_HALF_NS, unit="ns")
        assert int(dut.spi_miso_oe.value) == 1, "MISO not driven while CS_N is low"
        rx = 0
        for index, byte in enumerate((byte0, byte1)):
            for bit in range(7, -1, -1):
                dut.spi_mosi.value = (byte >> bit) & 1
                await Timer(SPI_HALF_NS, unit="ns")
                if index == 1:  # MISO is valid only in the second byte
                    rx = (rx << 1) | int(dut.spi_miso.value)
                dut.spi_sck.value = 1
                await Timer(SPI_HALF_NS, unit="ns")
                dut.spi_sck.value = 0
        await Timer(SPI_HALF_NS, unit="ns")
        dut.spi_cs_n.value = 1
        await Timer(2 * SPI_HALF_NS, unit="ns")  # gap between transactions
        return rx

    async def write(self, addr, value):
        await self.transfer(0x10 | addr, value)

    async def read(self, addr):
        return await self.transfer(addr, 0x00)

    async def read_sample(self, addr_low):
        """Read a 16-bit sample: low byte first, then the buffered high byte."""
        low = await self.read(addr_low)
        high = await self.read(addr_low + 1)
        return to_signed((high << 8) | low)


def to_signed(value):
    return value - 0x10000 if value & 0x8000 else value


class PdmMicrophones:
    """Two PDM microphones sharing PDM_DATA: the left one drives the half period that ends
    with the rising PDM_CLK edge, the right one the half period that ends with the falling
    edge. Counts the bits the converter has sampled from each."""

    def __init__(self, dut, left_bits, right_bits):
        self.dut = dut
        self.left_bits = left_bits
        self.right_bits = right_bits
        self.left_sampled = 0
        self.right_sampled = 0

    def _bit(self, bits, index):
        return bits[index] if index < len(bits) else 0

    async def run(self):
        dut = self.dut
        dut.pdm_data.value = self._bit(self.left_bits, 0)
        while True:
            await RisingEdge(dut.pdm_clk)   # left bit sampled at this edge
            self.left_sampled += 1
            await Timer(PDM_DELAY_NS, unit="ns")
            dut.pdm_data.value = self._bit(self.right_bits, self.right_sampled)
            await FallingEdge(dut.pdm_clk)  # right bit sampled at this edge
            self.right_sampled += 1
            await Timer(PDM_DELAY_NS, unit="ns")
            dut.pdm_data.value = self._bit(self.left_bits, self.left_sampled)


class I2sReceiver:
    """Philips I2S receiver: samples on rising BCLK edges; a word's MSB follows the LRCLK
    edge by one BCLK. Collects signed 16-bit words per channel (0 = left, 1 = right)."""

    def __init__(self, dut):
        self.dut = dut
        self.words = ([], [])

    async def run(self):
        dut = self.dut
        prev_lr = None
        channel = None
        word = count = 0
        while True:
            await RisingEdge(dut.i2s_bclk)
            lr = int(dut.i2s_lrclk.value)
            sd = int(dut.i2s_sdata.value)
            if channel is not None:
                word = (word << 1) | sd
                count += 1
                if count == 16:
                    self.words[channel].append(to_signed(word))
                    channel = None
            if prev_lr is not None and lr != prev_lr:
                channel, word, count = lr, 0, 0
            prev_lr = lr


async def count_edges(signal, counter):
    while True:
        await RisingEdge(signal)
        counter[0] += 1


def find_in(sequence, part):
    """Index at which part occurs in sequence, or None."""
    for offset in range(len(sequence) - len(part) + 1):
        if sequence[offset:offset + len(part)] == part:
            return offset
    return None


# ---------------------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------------------

@cocotb.test(timeout_time=5, timeout_unit="ms")
async def test_registers(dut):
    """Reset values, read/write registers, read-only registers."""
    await start(dut)
    spi = SpiMaster(dut)

    values = [await spi.read(addr) for addr in range(8)]
    assert values == RESET_VALUES, f"reset values {[hex(v) for v in values]}"

    await spi.write(NCO_LOW, 0xA5)
    await spi.write(NCO_HIGH, 0x5A)
    assert await spi.read(NCO_LOW) == 0xA5
    assert await spi.read(NCO_HIGH) == 0x5A

    # step = 0 keeps the PDM clock stopped, so the data registers stay at their reset values
    await spi.write(NCO_LOW, 0x00)
    await spi.write(NCO_HIGH, 0x00)
    await spi.write(CONTROL, 0xFF)
    assert await spi.read(CONTROL) == 0x01, "control: reserved bits must read as 0"
    await spi.write(CONTROL, 0x00)
    assert await spi.read(CONTROL) == 0x00

    for addr in (RIGHT_LOW, RIGHT_HIGH, LEFT_LOW, LEFT_HIGH, ID):
        await spi.write(addr, 0x3C)
        assert await spi.read(addr) == RESET_VALUES[addr], f"register {addr} must be read-only"


@cocotb.test(timeout_time=5, timeout_unit="ms")
async def test_pdm_clock(dut):
    """f_PDM = f_clk * step / 2^17; the clock stops while the converter is disabled."""
    await start(dut)
    spi = SpiMaster(dut)

    async def edge_times(n):
        times = []
        for _ in range(n + 1):
            await RisingEdge(dut.pdm_clk)
            times.append(get_sim_time(unit="ns"))
        return times

    # step = 4096: exactly 32 clk per period, no jitter
    await spi.write(NCO_LOW, 0x00)
    await spi.write(NCO_HIGH, 0x10)
    await spi.write(CONTROL, 0x01)
    times = await edge_times(16)
    periods = {round(b - a) for a, b in zip(times, times[1:])}
    assert periods == {32 * CLK_NS}, f"step 4096: periods {periods} ns"

    # step = 4027 (1.536 MHz): periods of 32 or 33 clk, average 2^17 / 4027 clk
    await spi.write(CONTROL, 0x00)
    await spi.write(NCO_LOW, 0xBB)
    await spi.write(NCO_HIGH, 0x0F)
    await spi.write(CONTROL, 0x01)
    times = await edge_times(128)
    periods = {round(b - a) for a, b in zip(times, times[1:])}
    assert periods <= {32 * CLK_NS, 33 * CLK_NS}, f"step 4027: periods {periods} ns"
    expected = 128 * CLK_NS * 2**17 / 4027
    assert abs((times[-1] - times[0]) - expected) <= CLK_NS, "step 4027: wrong average frequency"

    # disabled: no edges
    await spi.write(CONTROL, 0x00)
    edges = [0]
    counter = cocotb.start_soon(count_edges(dut.pdm_clk, edges))
    await Timer(20, unit="us")
    counter.cancel()
    assert edges[0] == 0, "PDM clock runs while disabled"


@cocotb.test(timeout_time=5, timeout_unit="ms")
async def test_audio(dut):
    """Stereo sine through PDM -> CIC -> I2S and the data registers, checked against the model."""
    await start(dut)
    spi = SpiMaster(dut)

    n_bits = 2400  # per channel, more than the test consumes
    # Left: sine with a full-scale burst (all ones) to exercise output saturation
    left_signal = sine(n_bits, 1 / 640, 0.5)
    left_signal[700:960] = [1.0] * 260
    left_bits = sigma_delta(left_signal)
    left_bits[700:960] = [1] * 260
    right_bits = sigma_delta(sine(n_bits, 1 / 400, 0.4, phase=1.0))
    model = (CicModel.run(left_bits), CicModel.run(right_bits))

    mics = PdmMicrophones(dut, left_bits, right_bits)
    i2s = I2sReceiver(dut)
    cocotb.start_soon(mics.run())
    cocotb.start_soon(i2s.run())

    # step = 8192: 3.125 MHz PDM clock, 97.66 kHz samples
    await spi.write(NCO_LOW, 0x00)
    await spi.write(NCO_HIGH, 0x20)
    await spi.write(CONTROL, 0x01)
    while len(i2s.words[1]) < 48:
        await RisingEdge(dut.i2s_lrclk)

    for channel, name in enumerate(("left", "right")):
        words = i2s.words[channel]
        offset = find_in(model[channel], words)
        assert offset is not None, f"{name} I2S words do not match the model: {words}"
        assert offset <= 1, f"{name}: first {offset} samples missing from the I2S stream"
        settled = words[4:]  # the first outputs after enabling are partial sums
        dut._log.info(f"{name}: {len(words)} I2S samples match the model, "
                      f"settled range {min(settled)} .. {max(settled)}")
        assert max(settled) - min(settled) > 20000, f"{name}: signal too small to be a meaningful test"
    assert 32767 in i2s.words[0], "left: full-scale burst did not saturate the output"

    # Freeze the converter, then read the latest samples through SPI
    await spi.write(CONTROL, 0x00)
    await ClockCycles(dut.clk, 100)
    left = await spi.read_sample(LEFT_LOW)
    right = await spi.read_sample(RIGHT_LOW)
    expected_left = model[0][mics.left_sampled // CicModel.R - 1]
    expected_right = model[1][mics.right_sampled // CicModel.R - 1]
    assert (left, right) == (expected_left, expected_right), \
        f"data registers ({left}, {right}), model ({expected_left}, {expected_right})"
    dut._log.info(f"data registers after {mics.left_sampled} PDM periods: left {left}, right {right}")
