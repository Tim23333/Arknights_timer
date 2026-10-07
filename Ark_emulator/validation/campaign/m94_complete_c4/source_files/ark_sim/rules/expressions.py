"""Small, bounded AST interpreter. Expressions have no Python execution access."""
import ast
import math
import operator
from collections.abc import Mapping

from .errors import ExpressionError

ROOTS = frozenset({"inputs", "params", "nodes", "context", "ctx"})
FUNCTIONS = frozenset({"max", "min", "sum", "abs", "floor", "ceil", "round", "sqrt", "clamp"})
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
          ast.Mod: operator.mod, ast.Pow: operator.pow}
CMPOPS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
          ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
          ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
ALLOWED = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.Attribute,
           ast.Subscript, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
           ast.IfExp, ast.Call, ast.List, ast.Tuple, ast.Dict,
           ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
           ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or,
           ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExpressionError(f"Expected numeric operand, got {type(value).__name__}")
    if not math.isfinite(value) or (isinstance(value, int) and value.bit_length() > 1024):
        raise ExpressionError("Numeric operand is non-finite or exceeds scalar budget")
    return value


class Expression:
    def __init__(self, source):
        if not isinstance(source, str) or not source.strip() or len(source) > 16384:
            raise ExpressionError("Expression must be a nonempty bounded string")
        try:
            self.tree = ast.parse(source, mode="eval")
        except (SyntaxError, RecursionError) as exc:
            raise ExpressionError(f"Invalid expression: {source!r}") from exc
        self.source = source
        walked = list(ast.walk(self.tree))
        if len(walked) > 512:
            raise ExpressionError("Expression exceeds 512 AST nodes")
        for node in walked:
            if not isinstance(node, ALLOWED):
                raise ExpressionError(f"Unsupported expression syntax: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id not in ROOTS | FUNCTIONS:
                raise ExpressionError(f"Unknown expression name: {node.id}")
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                raise ExpressionError("Private attributes are forbidden")
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS or node.keywords:
                    raise ExpressionError("Only declared pure functions with positional arguments are allowed")
            if isinstance(node, ast.Constant) and not isinstance(node.value, (str, int, float, bool, type(None))):
                raise ExpressionError("Unsupported literal")
            if isinstance(node, ast.Dict) and any(key is None for key in node.keys):
                raise ExpressionError("Mapping unpacking is forbidden")
        self.node_references = frozenset(self._references("nodes"))

    def _references(self, root):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == root:
                yield node.attr
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == root:
                if not isinstance(node.slice, ast.Constant) or not isinstance(node.slice.value, str):
                    raise ExpressionError(f"{root} references must use literal node IDs")
                yield node.slice.value

    def evaluate(self, env):
        try:
            return self._run(self.tree.body, env)
        except ExpressionError:
            raise
        except (ArithmeticError, KeyError, TypeError, ValueError, IndexError, RecursionError) as exc:
            raise ExpressionError(f"Expression {self.source!r} failed: {exc}") from exc

    def _run(self, node, env):
        run = lambda n: self._run(n, env)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in FUNCTIONS:
                raise ExpressionError("Function names can only appear in calls")
            return env[node.id]
        if isinstance(node, ast.Attribute):
            owner = run(node.value)
            if not isinstance(owner, Mapping):
                raise ExpressionError("Field access only reads mapping fields")
            return owner[node.attr]
        if isinstance(node, ast.Subscript):
            owner, key = run(node.value), run(node.slice)
            if not isinstance(owner, (Mapping, tuple, list)):
                raise ExpressionError("Indexing only reads mappings and sequences")
            if isinstance(key, str) and key.startswith("_"):
                raise ExpressionError("Private fields are forbidden")
            return owner[key]
        if isinstance(node, (ast.List, ast.Tuple)):
            return tuple(run(n) for n in node.elts)
        if isinstance(node, ast.Dict):
            if any(k is None for k in node.keys):
                raise ExpressionError("Mapping unpacking is forbidden")
            return {run(k): run(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.BinOp):
            left, right = _number(run(node.left)), _number(run(node.right))
            if isinstance(node.op, ast.Pow) and abs(right) > 1024:
                raise ExpressionError("Exponent exceeds calculation budget")
            return _number(BINOPS[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp):
            value = run(node.operand)
            if isinstance(node.op, ast.Not):
                if not isinstance(value, bool):
                    raise ExpressionError("Boolean operators require boolean values")
                return not value
            return _number(value) if isinstance(node.op, ast.UAdd) else -_number(value)
        if isinstance(node, ast.BoolOp):
            value = True if isinstance(node.op, ast.And) else False
            for item in node.values:
                value = run(item)
                if not isinstance(value, bool):
                    raise ExpressionError("Boolean operators require boolean values")
                if (isinstance(node.op, ast.And) and not value) or (isinstance(node.op, ast.Or) and value):
                    return value
            return value
        if isinstance(node, ast.Compare):
            left = run(node.left)
            for op, next_node in zip(node.ops, node.comparators):
                right = run(next_node)
                if not CMPOPS[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            test = run(node.test)
            if not isinstance(test, bool):
                raise ExpressionError("Conditional expression requires a boolean condition")
            return run(node.body if test else node.orelse)
        if isinstance(node, ast.Call):
            args = [run(n) for n in node.args]
            name = node.func.id
            if name in ("max", "min"):
                values = args[0] if len(args) == 1 and isinstance(args[0], (list, tuple)) else args
                if not values:
                    raise ExpressionError(f"{name} requires numeric arguments")
                return (max if name == "max" else min)(_number(x) for x in values)
            if name == "sum":
                if len(args) != 1 or not isinstance(args[0], (tuple, list)):
                    raise ExpressionError("sum expects one numeric sequence")
                return _number(sum(_number(x) for x in args[0]))
            if name == "round":
                if len(args) not in (1, 2):
                    raise ExpressionError("round expects one or two arguments")
                if len(args) == 2 and (type(args[1]) is not int or abs(args[1]) > 15):
                    raise ExpressionError("round precision must be an integer between -15 and 15")
                return round(_number(args[0]), *args[1:])
            if name == "clamp":
                if len(args) != 3:
                    raise ExpressionError("clamp expects value, minimum, maximum")
                value, minimum, maximum = (_number(arg) for arg in args)
                if minimum > maximum:
                    raise ExpressionError("clamp minimum cannot exceed maximum")
                return min(maximum, max(minimum, value))
            if len(args) != 1:
                raise ExpressionError(f"{name} expects one argument")
            return {"abs": abs, "floor": math.floor, "ceil": math.ceil, "sqrt": math.sqrt}[name](_number(args[0]))
        raise ExpressionError(f"Unhandled syntax: {type(node).__name__}")


def evaluate_expression(expression, inputs, params=None, context=None, nodes=None):
    """Shared read-only entry point for domain conditions and state graphs."""
    from ark_sim.contracts.models import freeze
    from .numeric import validate_data
    data = {"inputs": inputs, "params": params or {}, "context": context or {}, "nodes": nodes or {}}
    validate_data(data)
    env = freeze(data)
    result = Expression(expression).evaluate({**env, "ctx": env["context"]})
    validate_data(result, "expression result")
    return freeze(result)
