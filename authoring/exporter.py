import csv
import importlib
import json
import os
from typing import Any, Dict, List


def export_rules(rulepack_dir: str, formats: List[str]) -> Dict[str, str]:
    rules_path = os.path.join(rulepack_dir, "rules.json")
    if not os.path.exists(rules_path):
        raise FileNotFoundError("rules.json not found")
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f)

    output_paths: Dict[str, str] = {"json": rules_path}

    if "csv" in formats:
        csv_path = os.path.join(rulepack_dir, "rules.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rules[0].keys()) if rules else None
            if writer:
                writer.writeheader()
                writer.writerows(rules)
        output_paths["csv"] = csv_path

    if "yaml" in formats:
        spec = importlib.util.find_spec("yaml")
        if spec is None:
            raise RuntimeError("pyyaml is required for YAML export")
        yaml = importlib.import_module("yaml")  # type: ignore
        yaml_path = os.path.join(rulepack_dir, "rules.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(rules, f, allow_unicode=True)
        output_paths["yaml"] = yaml_path

    return output_paths
