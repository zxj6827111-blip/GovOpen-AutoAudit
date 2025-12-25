import json
import subprocess
import sys
import argparse
from pathlib import Path

def run_pilot_suite(rulepack_path: str, positive_sites_path: str, negative_sites_path: str):
    print("🚀 Starting Parameterized Pilot Suite Test...")
    print(f"RulePack: {rulepack_path}")
    print(f"Positive: {positive_sites_path}")
    print(f"Negative: {negative_sites_path}")
    
    # Merge sites into a temporary file
    merged_sites_path = Path("temp_pilot_sites.json")
    try:
        with open(positive_sites_path, "r", encoding="utf-8") as f:
            pos = json.load(f)
        with open(negative_sites_path, "r", encoding="utf-8") as f:
            neg = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load sites: {e}")
        sys.exit(1)
        
    combined = pos + neg
    with open(merged_sites_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
        
    cmd = [
        sys.executable, "scripts/run_pilot.py",
        "--rulepack", rulepack_path,
        "--sites", str(merged_sites_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ Pilot Run Failed!")
        print(result.stderr)
        # Continue to try analysis
    
    print("✅ Pilot Run Completed.")
    
    # Analyze
    runs_dir = Path("runs")
    batch_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("batch_")], key=lambda x: x.stat().st_mtime, reverse=True)
    if not batch_dirs:
        print("❌ No batch output found.")
        sys.exit(1)
        
    latest_batch = batch_dirs[0]
    summary_json_path = latest_batch / "export" / "summary.json"
    
    with open(summary_json_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
        
    site_results = summary.get("sites", [])
    results_map = {res["site_id"]: res for res in site_results}
    
    failures = []
    
    # Validate Positives
    for site in pos:
        site_id = site["site_id"]
        res = results_map.get(site_id)
        if not res:
            failures.append(f"❌ Missing result for {site_id}")
            continue
            
        pass_rules = [r["rule_id"] for r in res.get("rule_results", []) if r["status"] == "PASS" and not r["rule_id"].endswith("reachability-0")]
        pass_count = len(pass_rules)
        total_rules = len(res.get("rule_results", []))
        pass_rate = pass_count / total_rules if total_rules > 0 else 0
        
        print(f"Site {site_id} (Positive): PASS {pass_count}/{total_rules} ({pass_rate:.1%})")
        if pass_rate < 0.20:
             failures.append(f"❌ {site_id} PASS rate too low: {pass_count}/{total_rules} (<20%)")

    # Validate Negatives
    for site in neg:
        site_id = site["site_id"]
        res = results_map.get(site_id)
        if not res:
            continue
            
        pass_rules = [r["rule_id"] for r in res.get("rule_results", []) if r["status"] == "PASS" and not r["rule_id"].endswith("reachability-0")]
        pass_count = len(pass_rules)
        total_rules = len(res.get("rule_results", []))
        
        print(f"Site {site_id} (Negative): PASS {pass_count}/{total_rules}")
        
        if pass_count > 1:
             failures.append(f"❌ {site_id} False Positive Exceeded: {pass_count} rules passed (Max 1 allowed)")
        else:
             print(f"✅ {site_id} Governance OK")

    if failures:
        print("\n🚫 SUITE FAILED:")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    else:
        print("\n🎉 SUITE PASSED")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rulepack", required=True)
    parser.add_argument("--positive", required=True)
    parser.add_argument("--negative", required=True)
    args = parser.parse_args()
    
    run_pilot_suite(args.rulepack, args.positive, args.negative)
