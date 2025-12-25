import argparse
import asyncio
import json
import threading
import time
from pathlib import Path

from .batch_runner import BatchRunner
from .rulepack_importer import import_rulepack, RulepackImportError
from .rulepack_validator import validate_rulepack
from .site_importer import import_sites, SiteImportError, load_sites
from .site_importer import import_sites, SiteImportError, load_sites
from .sandbox_server import SandboxServer
from .report_generator import generate_markdown_report


def cmd_validate(args):
    result = validate_rulepack(Path(args.path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_import_rulepack(args):
    try:
        result = import_rulepack(Path(args.path))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except RulepackImportError as exc:
        print(exc)


def cmd_import_sites(args):
    try:
        result = import_sites(Path(args.path))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except SiteImportError as exc:
        print(str(exc))


async def cmd_run_batch(args):
    rulepack_path = Path(args.rulepack)
    sites = load_sites()
    runner = BatchRunner(rulepack_path, sites)
    result = await runner.run()  # 添加await
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=str))


async def cmd_regression(args):
    server = SandboxServer(port=8000)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    try:
        cmd_import_rulepack(argparse.Namespace(path="rulepacks/sandbox_mvp"))
        cmd_import_sites(argparse.Namespace(path="sandbox/sites.json"))
        await cmd_run_batch(argparse.Namespace(rulepack="rulepacks/sandbox_mvp"))  # 添加await
    finally:
        server.shutdown()


def cmd_report(args):
    """Report is auto-generated during batch run"""
    print(f"Report for batch {args.batch_id} should be at:")
    print(f"  runs/{args.batch_id}/export/report.md")



def build_parser():
    parser = argparse.ArgumentParser(description="GovOpen-AutoAudit Platform CLI")
    sub = parser.add_subparsers(dest="command")

    p_validate = sub.add_parser("validate_rulepack", help="validate a rulepack directory")
    p_validate.add_argument("path")
    p_validate.set_defaults(func=cmd_validate)

    p_import = sub.add_parser("import_rulepack", help="import a validated rulepack")
    p_import.add_argument("path")
    p_import.set_defaults(func=cmd_import_rulepack)

    p_sites = sub.add_parser("import_sites", help="import site library json")
    p_sites.add_argument("path")
    p_sites.set_defaults(func=cmd_import_sites)

    p_batch = sub.add_parser("run_batch", help="run batch with imported sites")
    p_batch.add_argument("rulepack")
    p_batch.set_defaults(func=cmd_run_batch)

    p_reg = sub.add_parser("regression", help="run sandbox regression")
    p_reg.set_defaults(func=cmd_regression)

    p_report = sub.add_parser("report", help="generate report for a batch")
    p_report.add_argument("batch_id")
    p_report.add_argument("--format", default="markdown", choices=["markdown"])
    p_report.add_argument("--output", help="save report to file")
    p_report.set_defaults(func=cmd_report)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    
    # 如果是async函数，使用asyncio.run
    import inspect
    if inspect.iscoroutinefunction(args.func):
        asyncio.run(args.func(args))
    else:
        args.func(args)


if __name__ == "__main__":
    main()
