import argparse
import json
import os
import shutil
from typing import List

import sys
from . import SCHEMA_VERSION
from .ai import apply_suggestions
from .converter import ConversionError, convert
from .exporter import export_rules
from .validator import validate


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authoring CLI for GovOpen AutoAudit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert_parser = subparsers.add_parser("convert", help="Convert Excel/text to rulepack")
    convert_parser.add_argument("input", help="Path to raw excel/text")
    convert_parser.add_argument("rule_pack_id", help="Rule pack id (will become directory name)")
    convert_parser.add_argument("name", help="Rule pack name")
    convert_parser.add_argument("region_tag", help="Region tag")
    convert_parser.add_argument("scope", help="Scope e.g. 部门/区县/市级")
    convert_parser.add_argument("version", help="Rule pack version")
    convert_parser.add_argument("generated_from", help="Source description")
    convert_parser.add_argument("output_root", nargs="?", default="rulepacks", help="Root directory for rule packs")
    convert_parser.add_argument("--allow-empty", action="store_true", dest="allow_empty", help="Allow empty rules")

    suggest_parser = subparsers.add_parser("ai-suggest", help="Apply AI suggestions to rules")
    suggest_parser.add_argument("rulepack_dir", help="Rulepack directory containing rules.json")

    validate_parser = subparsers.add_parser("validate", help="Validate a rulepack directory")
    validate_parser.add_argument("rulepack_dir", help="Rulepack directory to validate")
    validate_parser.add_argument("--allow-empty", action="store_true", dest="allow_empty", help="Allow empty rules file")

    export_parser = subparsers.add_parser("export", help="Export rules to multiple formats")
    export_parser.add_argument("rulepack_dir", help="Rulepack directory containing rules.json")
    export_parser.add_argument("--formats", nargs="*", default=["json", "csv", "yaml"], help="Formats to export")

    build_parser = subparsers.add_parser("build", help="Build final rulepack from workdir")
    build_parser.add_argument("workdir", help="Working directory (input)")
    build_parser.add_argument("output", help="Final rulepack output path")

    return parser.parse_args()


def _save_rules(rulepack_dir: str, rules: List[dict]):
    with open(os.path.join(rulepack_dir, "rules.json"), "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def cmd_convert(args: argparse.Namespace):
    output_dir = os.path.join(args.output_root, args.rule_pack_id)
    try:
        result = convert(
            input_path=args.input,
            output_dir=output_dir,
            rule_pack_id=args.rule_pack_id,
            name=args.name,
            region_tag=args.region_tag,
            scope=args.scope,
            version=args.version,
            generated_from=args.generated_from,
            allow_empty=args.allow_empty,
        )
        print(json.dumps({"ok": True, "output": output_dir, "rules": len(result["rules"]), "schema_version": SCHEMA_VERSION}, ensure_ascii=False, indent=2))
    except ConversionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))


def cmd_ai_suggest(args: argparse.Namespace):
    rules_path = os.path.join(args.rulepack_dir, "rules.json")
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    updated = apply_suggestions(rules)
    _save_rules(args.rulepack_dir, updated)
    print(json.dumps({"ok": True, "updated": len(updated)}))


def cmd_validate(args: argparse.Namespace):
    result = validate(args.rulepack_dir, allow_empty=args.allow_empty)
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    if not result.ok:
        sys.exit(1)


def cmd_export(args: argparse.Namespace):
    outputs = export_rules(args.rulepack_dir, args.formats)
    print(json.dumps({"ok": True, "outputs": outputs}, ensure_ascii=False, indent=2))


def cmd_build(args: argparse.Namespace):
    workdir = args.workdir
    output = args.output
    
    if not os.path.isdir(workdir):
        print(json.dumps({"ok": False, "error": f"Workdir not found: {workdir}"}))
        return

    # Validate before build (optional but good practice, though instructions imply separate steps)
    # We will just copy for now
    try:
        if os.path.exists(output):
            shutil.rmtree(output)
        shutil.copytree(workdir, output)
        print(json.dumps({"ok": True, "output": output}, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))


def main():
    args = _parse_args()
    if args.command == "convert":
        cmd_convert(args)
    elif args.command == "ai-suggest":
        cmd_ai_suggest(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "build":
        cmd_build(args)
    else:
        raise SystemExit(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
