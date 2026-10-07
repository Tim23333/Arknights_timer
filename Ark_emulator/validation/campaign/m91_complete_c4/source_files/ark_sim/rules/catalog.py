"""Named calculation contracts packaged with the runtime, extensible per program."""
import json
from collections.abc import Mapping
from pathlib import Path

from ark_sim.contracts.models import freeze, thaw
from .errors import RuleError, RuleTypeError
from .numeric import validate_data

DEFAULT_CATALOG = freeze(json.loads(Path(__file__).with_name("contracts.json").read_text(encoding="utf-8")))
NUMERIC_TYPES = {"number", "duration", "ratio", "attribute_value", "attribute_delta",
                 "damage_amount", "defense_value", "resource_amount", "speed", "distance"}
LIST_TYPES = {"record_list", "entity_list", "allocation_plan", "action_list", "buff_plan", "event_order", "phase_plan"}
DATA_PLAN_TYPES = {"path_plan", "displacement_plan", "trajectory_plan", "collision_result",
                   "region", "lifecycle_plan", "transition_plan"}


def load_catalog(catalog=None):
    if catalog is None:
        raw = DEFAULT_CATALOG
    elif isinstance(catalog, (str, Path)):
        raw = json.loads(Path(catalog).read_text(encoding="utf-8"))
    elif isinstance(catalog, Mapping):
        raw = catalog
    else:
        raise RuleError("catalog must be a mapping or JSON path")
    items = raw.get("contracts", raw)
    if isinstance(items, Mapping):
        contracts = {key: dict(value) for key, value in items.items()}
    elif isinstance(items, (tuple, list)):
        contracts = {}
        for contract in items:
            if not isinstance(contract, Mapping) or not isinstance(contract.get("id"), str):
                raise RuleError("Every contract requires an ID")
            if contract["id"] in contracts:
                raise RuleError(f"Duplicate calculation contract: {contract['id']}")
            contracts[contract["id"]] = dict(contract)
    else:
        raise RuleError("catalog contracts must be a mapping or sequence")
    for key, contract in contracts.items():
        contract.setdefault("id", key)
        if contract["id"] != key:
            raise RuleError(f"Contract ID differs from catalog key: {key}")
        if contract.get("owner", "owner") not in ("source", "target", "owner", "scenario", "ability", "effect"):
            raise RuleError(f"Invalid contract owner: {key}")
    types = {**DEFAULT_CATALOG["types"], **raw.get("types", {})}
    return freeze({"contracts": contracts, "types": types})


def check_type(value, schema, types=None, path="value"):
    """Validate both named types and optional explicit field/item schema."""
    validate_data(value, path)
    return _check_type(value, schema, types or DEFAULT_CATALOG["types"], path)


def _check_type(value, schema, types, path):
    """Structural checks on a tree whose entire JSON boundary was checked."""
    if isinstance(schema, str):
        schema = {"type": schema}
    if not isinstance(schema, Mapping):
        raise RuleTypeError(f"{path}: invalid type schema")
    name = schema.get("type", "record")
    if value is None and schema.get("nullable"):
        return
    valid = True
    if name in NUMERIC_TYPES:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif name in ("integer", "logic_time"):
        valid = type(value) is int
    elif name == "boolean":
        valid = type(value) is bool
    elif name == "string":
        valid = isinstance(value, str)
    elif name in ("record", "value_map", "entity_snapshot", "position"):
        valid = isinstance(value, Mapping)
    elif name == "entity_ref":
        valid = (type(value) is int and value >= 0) or isinstance(value, str)
    elif name in LIST_TYPES:
        valid = isinstance(value, (tuple, list))
        if valid and name == "record_list":
            valid = all(isinstance(item, Mapping) for item in value)
    elif name in DATA_PLAN_TYPES:
        valid = isinstance(value, (Mapping, tuple, list))
    elif name in types:
        representation = types[name].get("representation")
        if representation == "NumericProfile scalar":
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        elif representation == "integer":
            valid = type(value) is int
        elif representation == "boolean":
            valid = type(value) is bool
        elif representation == "string":
            valid = isinstance(value, str)
        elif representation in ("mapping of schema-typed values", "coordinate record", "read-only component snapshot"):
            valid = isinstance(value, Mapping)
        elif representation == "ordered schema-validated records":
            valid = isinstance(value, (tuple, list)) and all(isinstance(item, Mapping) for item in value)
        elif representation == "ordered entity references":
            valid = isinstance(value, (tuple, list))
        elif representation == "battle-local entity identity":
            valid = (type(value) is int and value >= 0) or isinstance(value, str)
        elif representation == "enum":
            valid = value in types[name]["values"]
        elif representation == "record" or "fields" in types[name]:
            valid = isinstance(value, Mapping)
        else:
            raise RuleTypeError(f"{path}: named type {name!r} needs an explicit schema")
    else:
        raise RuleTypeError(f"{path}: unknown named type {name!r}")
    if not valid:
        raise RuleTypeError(f"{path}: expected {name}, got {type(value).__name__}")
    fields = schema.get("fields", types.get(name, {}).get("fields", {}))
    if fields:
        if not isinstance(value, Mapping):
            raise RuleTypeError(f"{path}: expected fields mapping")
        for key, field in fields.items():
            required = not isinstance(field, Mapping) or field.get("required", True)
            if key not in value:
                if required:
                    raise RuleTypeError(f"{path}: missing required field {key!r}")
                continue
            _check_type(value[key], field, types, f"{path}.{key}")
    if "items" in schema:
        if not isinstance(value, (tuple, list)):
            raise RuleTypeError(f"{path}: item schema requires a sequence")
        for index, item in enumerate(value):
            _check_type(item, schema["items"], types, f"{path}[{index}]")
    if "enum" in schema and value not in schema["enum"]:
        raise RuleTypeError(f"{path}: not one of {schema['enum']!r}")


def check_inputs(inputs, contract, types=None):
    if not isinstance(inputs, Mapping):
        raise RuleTypeError("Calculation inputs must be a mapping")
    validate_data(inputs, "inputs")
    declarations = contract.get("inputs", ())
    if isinstance(declarations, Mapping):
        declarations = ({"name": name, **(dict(spec) if isinstance(spec, Mapping) else {"type": spec})}
                        for name, spec in declarations.items())
    for item in declarations:
        name = item["name"]
        if name not in inputs:
            if item.get("required", True):
                raise RuleTypeError(f"{contract['id']}: missing required input {name!r}")
        else:
            _check_type(inputs[name], item, types or DEFAULT_CATALOG["types"], f"inputs.{name}")
