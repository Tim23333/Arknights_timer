"""CLI for author validation, dependencies, rule previews and simulation."""
import argparse
import json
import math
import sys
from pathlib import Path

from ..content import Compiler
from ..contracts import thaw
from .authoring import preview_calculation, preview_rule
from .inspect import inspect_program


def _json(value, label):
    if value is None:
        return None
    try:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return json.loads(Path(value).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON or a readable JSON file: {exc}") from exc


def _write(value, output=None):
    raw = json.dumps(thaw(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw, encoding="utf-8")
    else:
        print(raw, end="")


def _quantize(program, seconds):
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Simulation seconds must be nonnegative and finite")
    return preview_calculation(program, "time.quantize", {
        "seconds": seconds, "quantum": program.ruleset["quantum"],
        "rounding": {"mode": "ceil"}}).value


def _compile(args):
    packages = list(args.package or [])
    if args.scenario in {"ark-00-01", "0-1"}:
        from ..adapters.imports.ark_level import import_ark_level
        package = import_ark_level(args.pack)
        if args.content:
            packages.append(args.content)
        packages.append(package)
        selection = "scenario/ark_00_01"
    elif args.scenario:
        if args.content:
            packages.append(args.content)
        selection = args.scenario
    elif args.content:
        selection = args.content
    else:
        raise ValueError("Supply a content JSON/directory or --scenario ark-00-01")
    overrides = []
    for entry in args.override or []:
        if "=" not in entry:
            raise ValueError("Each --override must be CALCULATION_ID=RULE_ID")
        calculation, rule = entry.split("=", 1)
        if not calculation or not rule:
            raise ValueError("Each --override must name a calculation and a rule")
        overrides.append({calculation: rule})
    return Compiler().compile(selection, packages=packages, ruleset=args.ruleset,
                              overrides=overrides or None)


def parser():
    root = argparse.ArgumentParser(prog="python -m ark_sim", description="V2 通用模拟底座作者工具")
    commands = root.add_subparsers(dest="command", required=True)
    for name, help_text in (("validate", "编译内容并检查依赖与能力"),
                            ("explain", "解释内容依赖及所有规则作用域"),
                            ("preview", "用完整规则契约试算公式"),
                            ("run", "运行编译后的场景"),
                            ("replay", "按锁定的种子、时间与身份重放记录")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("content", nargs="?", help="内容包 JSON 或目录")
        command.add_argument("--scenario", help="场景 ID；ark-00-01 使用离线0-1导入器")
        command.add_argument("--package", action="append", help="额外内容包 JSON 或目录，可重复")
        command.add_argument("--pack", help="0-1导入器使用的固定源 JSON")
        command.add_argument("--ruleset", help="显式选择规则集 ID")
        command.add_argument("--override", action="append", help="CALCULATION_ID=RULE_ID，可重复")
        command.add_argument("--output", help="把 JSON 结果写到文件")
        if name == "preview":
            selection = command.add_mutually_exclusive_group(required=True)
            selection.add_argument("--rule", help="按规则 ID 试算")
            selection.add_argument("--calculation", help="按计算契约和作用域试算")
            command.add_argument("--inputs", required=True, help="输入 JSON 字符串或 JSON 文件")
            command.add_argument("--scope", help="作用域绑定 JSON 字符串或 JSON 文件")
        if name == "run":
            duration = command.add_mutually_exclusive_group()
            duration.add_argument("--ticks", type=int, help="推进整数逻辑时间数")
            duration.add_argument("--seconds", type=float, default=None, help="推进模拟秒数，默认10秒")
            command.add_argument("--seed", type=int, default=0, help="确定随机种子")
            command.add_argument("--commands", help="额外指令列表 JSON，包含 at 或 at_seconds")
            command.add_argument("--replay-output", help="保存版本锁定的输入回放")
        if name == "replay":
            command.add_argument("--record", required=True, help="回放记录 JSON 字符串或 JSON 文件")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        program = _compile(args)
        if args.command == "validate":
            result = {"valid": True, "scenario": program.scenario["id"], "fingerprint": program.fingerprint,
                      "definitions": len(program.definitions), "rules": len(program.rules),
                      "provider_versions": {name: record["version"] for name, record in program.metadata["providers"].items()}}
        elif args.command == "explain":
            result = inspect_program(program)
        elif args.command == "preview":
            inputs = _json(args.inputs, "--inputs")
            if args.rule:
                evaluation = preview_rule(program, args.rule, inputs, scope=_json(args.scope, "--scope"))
            else:
                evaluation = preview_calculation(program, args.calculation, inputs, scope=_json(args.scope, "--scope"))
            result = {"rule_id": evaluation.rule_id, "value": thaw(evaluation.value), "trace": thaw(evaluation.trace)}
        elif args.command == "replay":
            from .replay import replay
            result = replay(program, _json(args.record, "--record")).snapshot()
        else:
            from ..adapters.api import Engine
            simulation = Engine.create(program, seed=args.seed)
            commands = _json(args.commands, "--commands") or []
            if not isinstance(commands, list):
                raise ValueError("--commands must contain a JSON array")
            for index, command in enumerate(commands):
                if not isinstance(command, dict):
                    raise ValueError(f"Command {index} must be an object")
                action = dict(command)
                at = action.pop("at", None)
                seconds = action.pop("at_seconds", None)
                if at is not None and seconds is not None:
                    raise ValueError(f"Command {index} must choose at or at_seconds")
                if seconds is not None:
                    at = _quantize(program, seconds)
                simulation.submit(action, at=0 if at is None else at)
            if args.ticks is not None:
                ticks = args.ticks
            else:
                seconds = 10 if args.seconds is None else args.seconds
                ticks = _quantize(program, seconds)
            if ticks < 0:
                raise ValueError("--ticks must be nonnegative")
            simulation.advance(ticks)
            result = simulation.snapshot()
            if args.replay_output:
                _write(simulation.export_replay(), args.replay_output)
        _write(result, args.output)
        return 0
    except (ValueError, TypeError, KeyError, OSError, ImportError) as exc:
        print(f"ark_sim: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
