#!/usr/bin/env python3
import argparse
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add root to sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from autoaudit.cli import cmd_import_rulepack, cmd_import_sites, cmd_run_batch, cmd_report


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("run_pilot")

def run_pilot(rulepack_path: str, sites_path: str, cap: int = None):
    rp_path = Path(rulepack_path).resolve()
    s_path = Path(sites_path).resolve()

    if not rp_path.exists():
        logger.error(f"RulePack not found: {rp_path}")
        return False
    if not s_path.exists():
        logger.error(f"Sites file not found: {s_path}")
        return False

    logger.info(f"Starting Pilot Run...")
    logger.info(f"RulePack: {rp_path.name}")
    logger.info(f"Sites: {s_path.name}")

    # 1. Import RulePack
    logger.info("Step 1: Importing RulePack...")
    try:
        args_rp = argparse.Namespace(path=str(rp_path))
        cmd_import_rulepack(args_rp)
    except Exception as e:
        logger.error(f"Failed to import RulePack: {e}")
        return False

    # 2. Import Sites
    logger.info("Step 2: Importing Sites...")
    try:
        args_sites = argparse.Namespace(path=str(s_path))
        cmd_import_sites(args_sites)
    except Exception as e:
        logger.error(f"Failed to import Sites: {e}")
        return False

    # 3. Run Batch
    logger.info("Step 3: Running Batch...")
    try:
        import asyncio
        args_batch = argparse.Namespace(rulepack=str(rp_path))
        asyncio.run(cmd_run_batch(args_batch))  # 使用asyncio.run
    except Exception as e:
        logger.error(f"Failed to run batch: {e}")
        return False

    # 4. Find Generated Batch ID & Export
    logger.info("Step 4: Exporting Deliverables...")
    runs_dir = ROOT_DIR / "runs"
    if not runs_dir.exists():
        logger.error("Runs directory not found.")
        return False
    
    # Find latest batch
    batches = [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("batch_")]
    if not batches:
        logger.error("No batch created.")
        return False
        
    latest_batch = max(batches, key=lambda d: d.stat().st_mtime)
    batch_id = latest_batch.name
    logger.info(f"Batch ID: {batch_id}")

    # Export Report (Markdown/HTML)
    try:
        report_path = latest_batch / "export" / f"report_{batch_id}.md"
        report_args = argparse.Namespace(
            batch_id=batch_id, 
            format="markdown", 
            output=str(report_path)
        )
        cmd_report(report_args)
        logger.info(f"Report exported to: {report_path}")
    except Exception as e:
        logger.error(f"Failed to export report: {e}")
    
    # Check Evidence Zip
    evidence_zip = latest_batch / "export" / "evidence.zip"
    if evidence_zip.exists():
        logger.info(f"Evidence Zip found at: {evidence_zip}")
    else:
        logger.error("Evidence Zip NOT found.")
        return False

    print(f"\n[OK] Pilot Run Completed Successfully!")
    print(f"Run ID: {batch_id}")
    print(f"Report: {report_path}")
    print(f"Evidence: {evidence_zip}")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Pilot Batch")
    parser.add_argument("--rulepack", required=True, help="Path to RulePack dir")
    parser.add_argument("--sites", required=True, help="Path to sites.json")
    parser.add_argument("--cap", type=int, help="Limit sites per run (optional)")
    
    args = parser.parse_args()
    
    success = run_pilot(args.rulepack, args.sites, args.cap)
    sys.exit(0 if success else 1)
