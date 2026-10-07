"""Explicit output quantization; no implicit game clamps or hidden rounding."""
import math
from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING, ROUND_DOWN, localcontext

from .errors import RuleError, RuleTypeError
from ark_sim.contracts.models import freeze

ROUNDINGS = {"half_even": ROUND_HALF_EVEN, "half_up": ROUND_HALF_UP,
             "floor": ROUND_FLOOR, "ceil": ROUND_CEILING, "trunc": ROUND_DOWN}


def validate_data(value, path="value"):
    """Allow immutable data only, and reject nonfinite values at every depth."""
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite or (isinstance(value, int) and value.bit_length() > 1024):
            raise RuleTypeError(f"{path}: nonfinite or oversized number")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise RuleTypeError(f"{path}: JSON mapping keys must be strings")
            validate_data(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_data(item, f"{path}[{index}]")
        return
    raise RuleTypeError(f"{path}: mutable objects and non-data values are forbidden ({type(value).__name__})")


class NumericProfile:
    def __init__(self, definition=None):
        self.definition = dict(definition or {})
        self.definition.setdefault("backend", "float")
        self.definition.setdefault("rounding", "half_even")
        if self.definition["backend"] not in ("float", "float64"):
            raise RuleError(f"Unsupported numeric backend: {self.definition['backend']}")
        if self.definition["rounding"] not in ROUNDINGS:
            raise RuleError(f"Unknown rounding mode: {self.definition['rounding']}")
        precision = self.definition.get("precision")
        if precision is not None and (type(precision) is not int or not -15 <= precision <= 15):
            raise RuleError("precision must be an integer from -15 to 15")
        quantum = self.definition.get("quantum")
        if quantum is not None and (isinstance(quantum, bool) or not isinstance(quantum, (int, float))
                                    or not math.isfinite(quantum) or quantum <= 0):
            raise RuleError("numeric quantum must be a positive finite number")
        for bound in ("minimum", "maximum"):
            value = self.definition.get(bound)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise RuleError(f"{bound} must be finite numeric")
        minimum, maximum = self.definition.get("minimum"), self.definition.get("maximum")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise RuleError("minimum cannot exceed maximum")
        self.definition = freeze(self.definition)

    def normalize(self, value, overrides=None):
        if overrides:
            return NumericProfile({**self.definition, **dict(overrides)}).normalize(value)
        validate_data(value)
        return self._normalize(value)

    def _normalize(self, value):
        """Normalize an already validated tree without rewalking every subtree."""
        if value is None or isinstance(value, (str, bool)):
            return value
        if isinstance(value, Mapping):
            return {k: self._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return tuple(self._normalize(v) for v in value)
        precision, quantum = self.definition.get("precision"), self.definition.get("quantum")
        result = value
        if precision is not None or quantum is not None:
            with localcontext() as decimal_context:
                decimal_context.prec = 340
                number = Decimal(str(value))
                if quantum is not None:
                    step = Decimal(str(quantum))
                    number = (number / step).to_integral_value(rounding=ROUNDINGS[self.definition["rounding"]]) * step
                if precision is not None:
                    number = number.quantize(Decimal(1).scaleb(-precision), rounding=ROUNDINGS[self.definition["rounding"]])
                result = float(number)
                if type(value) is int and result.is_integer():
                    result = int(result)
        if self.definition.get("minimum") is not None:
            result = max(result, self.definition["minimum"])
        if self.definition.get("maximum") is not None:
            result = min(result, self.definition["maximum"])
        validate_data(result)
        return result
