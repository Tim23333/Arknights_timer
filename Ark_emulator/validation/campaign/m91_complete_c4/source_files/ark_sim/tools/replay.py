"""Version-locked command replay over the public Engine API."""
import json
from collections.abc import Mapping

from ..contracts.models import thaw


class ReplayError(ValueError):
    """A record cannot be replayed under the supplied compiled runtime."""


def _integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReplayError(f"{label} must be a nonnegative integer")
    return value


def _validated_record(program, record):
    if not isinstance(record, Mapping):
        raise ReplayError("Replay record must be an object")
    try:
        record = json.loads(json.dumps(thaw(record), ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ReplayError("Replay record must contain finite JSON values") from exc
    if record.get("schema") != "ark-sim/replay/v2":
        raise ReplayError("Unsupported replay schema")
    if record.get("program_fingerprint") != program.fingerprint:
        raise ReplayError("Replay program fingerprint does not match the compiled program")
    if not isinstance(record.get("runtime_fingerprint"), str) or not record["runtime_fingerprint"]:
        raise ReplayError("Replay runtime fingerprint is required")
    _integer(record.get("until"), "Replay end time")
    if "seed" not in record:
        raise ReplayError("Replay seed is required")
    if "random_algorithm" in record and (not isinstance(record["random_algorithm"], str) or not record["random_algorithm"]):
        raise ReplayError("Replay random algorithm must be a nonempty string")
    commands = record.get("commands")
    if not isinstance(commands, list):
        raise ReplayError("Replay commands must be an array")
    orders = set()
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            raise ReplayError(f"Replay command {index} must be an object")
        at = _integer(command.get("at"), f"Command {index} time")
        submitted_at = _integer(command.get("submitted_at", 0), f"Command {index} submission time")
        if submitted_at > at:
            raise ReplayError(f"Command {index} cannot execute before its submission time")
        if submitted_at > record["until"]:
            raise ReplayError(f"Command {index} was submitted after replay end time")
        command["submitted_at"] = submitted_at
        order = _integer(command.get("order"), f"Command {index} order")
        if order in orders:
            raise ReplayError(f"Duplicate replay command order: {order}")
        orders.add(order)
        if not isinstance(command.get("action"), dict):
            raise ReplayError(f"Command {index} action must be an object")
    submission_times = [command["submitted_at"] for command in sorted(commands, key=lambda item: item["order"])]
    if submission_times != sorted(submission_times):
        raise ReplayError("Command order must follow nondecreasing submission times")
    return record


def replay(program, record, **runtime_options):
    """Create and return a Simulation after replaying to ``record['until']``.

    Commands are submitted in recorded order at ``submitted_at`` (default 0).
    This preserves scheduler identities even for commands added interactively.
    A terminal scenario does not shorten the recorded clock.
    The Engine import stays local so its adapters can import replay utilities.
    """
    record = _validated_record(program, record)
    from ..adapters.api import Engine

    if "seed" in runtime_options:
        raise ReplayError("Replay seed is locked by the record")
    if "random_algorithm" in record:
        requested = runtime_options.get("random_algorithm")
        if requested is not None and requested != record["random_algorithm"]:
            raise ReplayError("Replay random algorithm disagrees with the requested runtime")
        runtime_options["random_algorithm"] = record["random_algorithm"]
    simulation = Engine.create(program, seed=record["seed"], **runtime_options)
    if simulation.checkpoint()["runtime_fingerprint"] != record["runtime_fingerprint"]:
        raise ReplayError("Replay runtime fingerprint does not match the current runtime")
    executor = simulation.session
    for command in sorted(record["commands"], key=lambda item: item["order"]):
        now = executor.time
        if now > command["submitted_at"]:
            raise ReplayError("Command submission precedes the runtime current time")
        executor.advance(command["submitted_at"] - now)
        simulation.submit(command["action"], at=command["at"])
    if executor.time > record["until"]:
        raise ReplayError("Replay end time precedes the runtime initial time")
    executor.advance(record["until"] - executor.time)
    return simulation
