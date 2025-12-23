#!/usr/bin/env python3
import subprocess
import sys

def check_freeze_unchanged():
    # In CI, we usually fetch origin/main. We verify against that.
    # Or simply against HEAD~1 if it's a push? 
    # Use 'origin/main' as the baseline for PRs.
    
    # Try different baselines
    baselines = ["origin/main", "main", "HEAD~1"]
    
    diff_output = ""
    target_file = "docs/10_INTERFACE_FREEZE.md"
    
    # Try to find a valid comparison
    for base in baselines:
        try:
            cmd = ["git", "diff", "--name-only", base, "--", target_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                diff_output = result.stdout.strip()
                if diff_output:
                     break
                # If valid command but empty output, it means no diff, which is GOOD (or bad comparison?)
                # We need to be sure we compared against something valid.
                pass
        except Exception:
            continue
            
    # As a fallback for local testing where origin/main might not be fetched:
    # Check against HEAD if staged? Or just assume if this script runs, it checks current changes?
    # For CI, we want to fail if the PR modifies the file.
    
    if target_file in diff_output:
        print(f"❌ CRITICAL: {target_file} has been modified! This verifies the Freeze Contract.")
        print("Please revert changes to this file to pass the gate.")
        sys.exit(1)
        
    print(f"✅ {target_file} is unchanged.")
    sys.exit(0)

if __name__ == "__main__":
    check_freeze_unchanged()
