"""
栏目同义词映射器
自动扩展content_paths以识别同义栏目
"""
import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class SynonymMapper:
    """栏目同义词映射"""
    
    def __init__(self, synonyms_file: Path = None):
        self.synonyms = {}
        self.canonical_map = {}  # 反向映射: synonym -> canonical
        
        if synonyms_file and synonyms_file.exists():
            self._load_synonyms(synonyms_file)
        else:
            # 使用默认同义词
            self._load_default_synonyms()
    
    def _load_synonyms(self, synonyms_file: Path):
        """从文件加载同义词"""
        try:
            data = json.loads(synonyms_file.read_text(encoding="utf-8"))
            for group in data.get("column_groups", []):
                canonical = group["canonical_name"]
                synonyms = group.get("synonyms", [])
                priority = group.get("priority", 5)
                
                self.synonyms[canonical] = {
                    "synonyms": synonyms,
                    "priority": priority
                }
                
                # 构建反向映射
                for syn in synonyms:
                    self.canonical_map[syn.lower()] = canonical
                self.canonical_map[canonical.lower()] = canonical
                
            logger.info(f"Loaded {len(self.synonyms)} synonym groups")
        except Exception as e:
            logger.error(f"Failed to load synonyms: {e}")
            self._load_default_synonyms()
    
    def _load_default_synonyms(self):
        """加载默认同义词组"""
        default_groups = [
            {
                "canonical_name": "政务公开",
                "synonyms": ["信息公开", "政府信息", "公开信息", "zwgk", "xxgk"],
                "priority": 10
            },
            {
                "canonical_name": "机构职能",
                "synonyms": ["组织机构", "机构设置", "jgzn", "zzjg"],
                "priority": 9
            },
            {
                "canonical_name": "政策法规",
                "synonyms": ["政策文件", "法律法规", "zcfg"],
                "priority": 8
            },
            {
                "canonical_name": "财政信息",
                "synonyms": ["财政公开", "预算决算", "czxx", "yjjs"],
                "priority": 9
            }
        ]
        
        for group in default_groups:
            canonical = group["canonical_name"]
            self.synonyms[canonical] = {
                "synonyms": group["synonyms"],
                "priority": group["priority"]
            }
            
            for syn in group["synonyms"]:
                self.canonical_map[syn.lower()] = canonical
            self.canonical_map[canonical.lower()] = canonical
        
        logger.info(f"Loaded {len(self.synonyms)} default synonym groups")
    
    def find_canonical(self, path: str) -> str:
        """查找路径的标准名称"""
        path_lower = path.lower()
        
        # 检查每个同义词
        for syn, canonical in self.canonical_map.items():
            if syn in path_lower:
                return canonical
        
        return None
    
    def expand_content_paths(self, content_paths: List) -> List:
        """扩展content_paths（添加同义变体）"""
        expanded = []
        seen = set()  # 去重
        
        for path_obj in content_paths:
            # 支持字符串或对象格式
            if isinstance(path_obj, str):
                path = path_obj
                priority = 5
                tags = []
            else:
                path = path_obj.get("path", "")
                priority = path_obj.get("priority", 5)
                tags = path_obj.get("tags", [])
            
            # 添加原始路径
            if path not in seen:
                expanded.append({
                    "path": path,
                    "priority": priority,
                    "tags": tags
                })
                seen.add(path)
            
            # 查找匹配的同义词组
            canonical = self.find_canonical(path)
            if canonical and canonical in self.synonyms:
                group = self.synonyms[canonical]
                
                # 为每个同义词生成变体
                for synonym in group["synonyms"]:
                    # 简单替换（可以更智能）
                    variant_path = self._replace_canonical(path, canonical, synonym)
                    
                    if variant_path != path and variant_path not in seen:
                        expanded.append({
                            "path": variant_path,
                            "priority": group["priority"],
                            "tags": tags + ["synonym_variant"]
                        })
                        seen.add(variant_path)
        
        logger.info(f"Expanded {len(content_paths)} paths to {len(expanded)} paths")
        return expanded
    
    def _replace_canonical(self, path: str, canonical: str, synonym: str) -> str:
        """替换路径中的标准名称为同义词"""
        # 简单替换（大小写不敏感）
        import re
        pattern = re.compile(re.escape(canonical), re.IGNORECASE)
        return pattern.sub(synonym, path, count=1)
    
    def get_accuracy_test_data(self) -> List[Dict]:
        """获取准确率测试数据"""
        test_cases = [
            {"input": "/政务公开/xxgk/index.html", "expected_canonical": "政务公开"},
            {"input": "/jgzn/zzjg/", "expected_canonical": "机构职能"},
            {"input": "/zcfg/policy/", "expected_canonical": "政策法规"},
            {"input": "/czxx/budget/", "expected_canonical": "财政信息"},
            {"input": "/unknown/path/", "expected_canonical": None}
        ]
        return test_cases
    
    def test_accuracy(self) -> float:
        """测试同义词识别准确率"""
        test_cases = self.get_accuracy_test_data()
        correct = 0
        
        for case in test_cases:
            found = self.find_canonical(case["input"])
            if found == case["expected_canonical"]:
                correct += 1
        
        accuracy = correct / len(test_cases)
        logger.info(f"Synonym accuracy: {accuracy:.1%} ({correct}/{len(test_cases)})")
        return accuracy
