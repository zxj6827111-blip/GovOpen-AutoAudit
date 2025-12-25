#!/usr/bin/env python3
import time
import threading
import sys
import logging
import zipfile
import json
from pathlib import Path

# Adjust path so we can import modules from root
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from autoaudit.sandbox_server import SandboxServer
from autoaudit.cli import cmd_import_rulepack, cmd_run_batch, cmd_import_sites
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ui_smoke_test")

def verify_artifacts(batch_dir: Path):
    export_dir = batch_dir / "export"
    logger.info(f"Verifying artifacts in {export_dir}")
    
    expected_files = ["summary.json", "issues.json", "failures.json", "evidence.zip"]
    for fname in expected_files:
        fpath = export_dir / fname
        if not fpath.exists():
            logger.error(f"Missing artifact: {fname}")
            return False
            
    # Check Zip
    try:
        with zipfile.ZipFile(export_dir / "evidence.zip", 'r') as zf:
            if zf.testzip() is not None:
                logger.error("evidence.zip is corrupted")
                return False
            # Optional: check if zip is not empty
            if not zf.namelist():
                logger.warning("evidence.zip is empty (might be valid if no evidence collected)")
    except Exception as e:
        logger.error(f"Failed to check zip: {e}")
        return False
        
    # Check Summary
    try:
        summary = json.loads((export_dir / "summary.json").read_text(encoding='utf-8'))
        if not summary.get("batch_id"):
             logger.error("Summary missing batch_id")
             return False
    except json.JSONDecodeError:
        logger.error("summary.json is invalid JSON")
        return False

    return True

def run_smoke_test():
    server = SandboxServer(port=8000)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logger.info("Sandbox server started on port 8000")
    
    # Wait for server to be ready
    time.sleep(1) 
    
    try:
        # 1. Import Sites (using sandbox sites)
        logger.info("Importing sandbox sites...")
        cmd_import_sites(argparse.Namespace(path=str(ROOT_DIR / "sandbox/sites.json")))
        
        # 2. Import RulePack (region_demo_1)
        rulepack_path = ROOT_DIR / "rulepacks" / "region_demo_1"
        if not rulepack_path.exists():
            logger.error(f"Rulepack not found: {rulepack_path}. Please run 'authoring build' first.")
            return False
            
        logger.info(f"Importing rulepack from {rulepack_path}...")
        cmd_import_rulepack(argparse.Namespace(path=str(rulepack_path)))
        
        # 3. Run Batch
        logger.info("Running batch...")
        # Capture output or return value? cmd_run_batch prints to stdout mostly, 
        # but we need to know the batch ID or find the latest run.
        # Modified idea: cmd_run_batch returns the result object if called directly? 
        # Checking cli.py: it prints. We might need to find the latest run dir manually.
        
        cmd_run_batch(argparse.Namespace(rulepack=str(rulepack_path)))
        
        # 4. Find latest batch
        runs_dir = ROOT_DIR / "runs"
        if not runs_dir.exists():
             logger.error("runs/ dir not found")
             return False
        
        # Filter for recent batch (modification time)
        batches = [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("batch_")]
        if not batches:
            logger.error("No batch directory generated")
            return False
            
        latest_batch = max(batches, key=lambda d: d.stat().st_mtime)
        logger.info(f"Latest batch detected: {latest_batch.name}")
        
        # 5. Verify Artifacts
        if verify_artifacts(latest_batch):
            logger.info("✅ UI Smoke Test PASSED")
            return True
        else:
            logger.error("❌ UI Smoke Test FAILED: Artifact verification failed")
            return False
            
    except Exception as e:
        logger.exception(f"Smoke test exception: {e}")
        return False
    finally:
        server.shutdown()
        server_thread.join(timeout=2)
        logger.info("Server shutdown")

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
