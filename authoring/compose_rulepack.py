import json
import argparse
from pathlib import Path

def compose(common_path: str, override_path: str, output_path: str, region_prefix: str):
    with open(common_path, "r", encoding="utf-8") as f:
        common = json.load(f)
    
    overrides = []
    if override_path:
        with open(override_path, "r", encoding="utf-8") as f:
            overrides = json.load(f)
            
    # Create override map
    override_map = {r["rule_id"]: r for r in overrides if "rule_id" in r}
    
    final_rules = []
    for rule in common:
        rid = rule["rule_id"]
        # Apply override if exists
        if rid in override_map:
            # Merge logic: update keys from override
            # If override has "override": true, it just patches.
            for k, v in override_map[rid].items():
                if k != "override":
                    rule[k] = v
        
        # Apply Region Prefix to ID
        rule["rule_id"] = f"{region_prefix}-{rid}"
        final_rules.append(rule)
        
    # Append strictly new rules from overrides (those not in common)
    common_ids = {r["rule_id"] for r in common} # Note: using original IDs
    
    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_rules, f, indent=2, ensure_ascii=False)
    
    print(f"Composed {len(final_rules)} rules to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--common", required=True)
    parser.add_argument("--override")
    parser.add_argument("--output", required=True)
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    
    compose(args.common, args.override, args.output, args.prefix)
