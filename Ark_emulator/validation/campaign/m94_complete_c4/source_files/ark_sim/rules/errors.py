"""Explicit rule failures are part of the authoring/runtime contract."""


class RuleError(ValueError):
    """A definition, binding, input or calculation is invalid."""


class MissingRuleError(RuleError):
    pass


class RuleTypeError(RuleError):
    pass


class ExpressionError(RuleError):
    pass


class BindingConflictError(RuleError):
    pass
