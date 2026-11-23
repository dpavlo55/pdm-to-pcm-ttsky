# SPDX-License-Identifier: Apache-2.0
"""Reference models for the cocotb test: a PDM source and the CIC decimator."""

import math


class CicModel:
    """Bit-accurate model of one channel of the CIC decimation filter.

    Recursive form of H(z) = ((1 - z^-32) / (1 - z^-1))^4, decimated by 32, with
    PDM bits counted as 0 and 1. The RTL computes the same filter in FIR form.
    The filter sum S lies in [0, 2^20]; the output is floor(S / 16) - 32768,
    saturated at +32767.
    """

    N = 4
    R = 32
    W = 21  # wide enough to hold 2^20 exactly
    MASK = (1 << W) - 1

    def __init__(self):
        self.integ = [0] * self.N
        self.comb_dly = [0] * self.N
        self.count = 0

    def step(self, bit):
        """Process one PDM bit. Returns the PCM sample every R-th bit, else None."""
        self.integ[0] = (self.integ[0] + bit) & self.MASK
        for i in range(1, self.N):
            self.integ[i] = (self.integ[i] + self.integ[i - 1]) & self.MASK
        self.count += 1
        if self.count < self.R:
            return None
        self.count = 0
        v = self.integ[-1]
        for i in range(self.N):
            v, self.comb_dly[i] = (v - self.comb_dly[i]) & self.MASK, v
        return min(v >> 4, 0xFFFF) - 32768

    @classmethod
    def run(cls, bits):
        """Return all PCM samples produced by the bit sequence."""
        model = cls()
        return [y for y in map(model.step, bits) if y is not None]


def sigma_delta(signal):
    """Second-order sigma-delta modulator: samples in [-1, 1] -> PDM bits."""
    i1 = i2 = 0.0
    y = 1.0
    bits = []
    for x in signal:
        i1 += x - y
        i2 += i1 - y
        y = 1.0 if i2 >= 0 else -1.0
        bits.append(1 if y > 0 else 0)
    return bits


def sine(n, cycles_per_sample, amplitude, phase=0.0):
    return [amplitude * math.sin(2 * math.pi * cycles_per_sample * k + phase) for k in range(n)]
