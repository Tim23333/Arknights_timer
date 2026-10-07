"""Logic-time configuration, with no fixed game frequency."""
import math

from ._data import integer


def quantum_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("quantum must be a finite positive number of seconds")
    return value


class Clock:
    def __init__(self, quantum=1 / 30, time=0):
        self.quantum = quantum_value(quantum)
        self.time = integer(time, "logical time", 0)

    @property
    def seconds(self):
        return self.time * self.quantum
