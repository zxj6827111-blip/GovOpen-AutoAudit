import os
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

# ✅ 加载环境变量（确保.env中的API KEY被读取）
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


# 尝试导入AI Provider
try:
    from openai import OpenAI
    MODELSCOPE_AVAILABLE = True
except ImportError:
    logger.warning("openai not installed. ModelScope providers will be disabled.")
    MODELSCOPE_AVAILABLE = False


@dataclass
class AiInvocation:
    """AI调用记录"""
    invocation_id: str
    provider: str  # "glm" | "deepseek"
    model: str
    prompt_version: str = "v1.0"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    success: bool = False
    error: Optional[str] = None
    result: Optional[Dict] = None


class AIExtractor:
    """AI辅助字段提取 - 支持DeepSeek/Qwen/GLM三个Provider"""
    
    def __init__(
        self, 
        primary_provider="deepseek",  # DeepSeek作为默认（综合最优）
        fallback_provider="qwen",      # Qwen作为备选（最快响应）
        max_tokens=2000,
        timeout_seconds=30,
        max_cost_per_batch=None  # 从环境变量读取
    ):
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        
        # ✅ 从环境变量读取token限额，默认50000（足够复核大量规则）
        if max_cost_per_batch is None:
            max_cost_per_batch = int(os.environ.get("AI_MAX_TOKENS_PER_BATCH", "50000"))
        self.max_cost_per_batch = max_cost_per_batch
        
        # 当前批次token消耗
        self.batch_tokens_used = 0
        
        # AI调用记录
        self.invocations: List[AiInvocation] = []
        
        # 初始化Providers
        self.deepseek_client = None
        self.qwen_client = None
        self.glm_client = None
        
        # ModelScope API Key（所有模型共用）
        modelscope_key = os.environ.get("DEEPSEEK_API_KEY")
        
        # DeepSeek（魔搭）初始化 - 主要Provider
        if MODELSCOPE_AVAILABLE and modelscope_key:
            try:
                self.deepseek_client = OpenAI(
                    api_key=modelscope_key,
                    base_url="https://api-inference.modelscope.cn/v1"
                )
                logger.info("DeepSeek provider initialized (ModelScope) - Primary")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek: {e}")
        
        # Qwen3-32B（魔搭）初始化 - 备用Provider
        if MODELSCOPE_AVAILABLE and modelscope_key:
            try:
                self.qwen_client = OpenAI(
                    api_key=modelscope_key,
                    base_url="https://api-inference.modelscope.cn/v1"
                )
                logger.info("Qwen3-32B provider initialized (ModelScope) - Fallback")
            except Exception as e:
                logger.error(f"Failed to initialize Qwen: {e}")
        
        # GLM-4.7（魔搭）初始化 - 特殊场景
        if MODELSCOPE_AVAILABLE and modelscope_key:
            try:
                self.glm_client = OpenAI(
                    api_key=modelscope_key,
                    base_url="https://api-inference.modelscope.cn/v1"
                )
                logger.info("GLM-4.7 provider initialized (ModelScope) - Special Cases")
            except Exception as e:
                logger.error(f"Failed to initialize GLM: {e}")

    
    def extract_fields(self, html_body: str, fields: List[str]) -> Dict[str, Optional[str]]:
        """
        从HTML中提取指定字段（支持双Provider）
        
        Args:
            html_body: 页面HTML内容
            fields: 要提取的字段列表，如["phone", "address"]
        
        Returns:
            {"phone": "025-12345", "address": "南京市..."}
        """
        # Cost Control检查
        if self.batch_tokens_used >= self.max_cost_per_batch:
            logger.warning(f"Batch token limit reached ({self.batch_tokens_used}/{self.max_cost_per_batch}), skipping AI extraction")
            return {field: None for field in fields}
        
        # 尝试主Provider
        result = self._try_provider(self.primary_provider, html_body, fields)
        if result:
            return result
        
        # 降级到副Provider
        logger.warning(f"Primary provider {self.primary_provider} failed, trying fallback {self.fallback_provider}")
        result = self._try_provider(self.fallback_provider, html_body, fields)
        if result:
            return result
        
        # 所有Provider都失败
        logger.error("All AI providers failed")
        return {field: None for field in fields}
    
    def _try_provider(self, provider: str, html_body: str, fields: List[str]) -> Optional[Dict]:
        """尝试使用指定Provider"""
        if provider == "deepseek":
            return self._extract_with_deepseek(html_body, fields)
        elif provider == "qwen":
            return self._extract_with_qwen(html_body, fields)
        elif provider == "glm":
            return self._extract_with_glm(html_body, fields)
        else:
            logger.error(f"Unknown provider: {provider}")
            return None
    
    def _extract_with_glm(self, html_body: str, fields: List[str]) -> Optional[Dict]:
        """使用GLM-4.7提取"""
        if not self.glm_client:
            logger.warning("GLM client not available")
            return None
        
        invocation = AiInvocation(
            invocation_id=f"glm_{int(time.time()*1000)}",
            provider="glm",
            model="ZhipuAI/GLM-4.7"
        )
        
        try:
            prompt = self._build_extraction_prompt(html_body, fields)
            start_time = time.time()
            
            # GLM调用（非流式）
            response = self.glm_client.chat.completions.create(
                model="ZhipuAI/GLM-4.7",  # ModelScope Model-Id
                messages=[
                    {"role": "system", "content": "你是一个专业的信息提取助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens,
                stream=False  # 非流式
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 解析结果
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            import json
            extracted = json.loads(result_text)
            
            # 记录成功调用
            invocation.latency_ms = elapsed_ms
            invocation.success = True
            invocation.result = extracted
            invocation.input_tokens = response.usage.prompt_tokens
            invocation.output_tokens = response.usage.completion_tokens
            invocation.total_tokens = response.usage.total_tokens
            
            self.batch_tokens_used += invocation.total_tokens
            self.invocations.append(invocation)
            
            logger.info(f"GLM extraction successful ({elapsed_ms}ms, {invocation.total_tokens} tokens)")
            return extracted
            
        except Exception as e:
            invocation.success = False
            invocation.error = str(e)
            self.invocations.append(invocation)
            logger.error(f"GLM extraction failed: {e}")
            return None
    
    def _extract_with_qwen(self, html_body: str, fields: List[str]) -> Optional[Dict]:
        """使用Qwen3-32B提取（支持thinking模式）"""
        if not self.qwen_client:
            logger.warning("Qwen client not available")
            return None
        
        invocation = AiInvocation(
            invocation_id=f"qwen_{int(time.time()*1000)}",
            provider="qwen",
            model="Qwen/Qwen3-32B"
        )
        
        try:
            prompt = self._build_extraction_prompt(html_body, fields)
            start_time = time.time()
            
            # Qwen3调用（非流式，显式禁用thinking）
            response = self.qwen_client.chat.completions.create(
                model="Qwen/Qwen3-32B",
                messages=[
                    {"role": "system", "content": "你是一个专业的信息提取助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens,
                stream=False,  # 非流式
                extra_body={"enable_thinking": False}  # 显式禁用thinking
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 解析结果
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            import json
            extracted = json.loads(result_text)
            
            # 记录成功调用
            invocation.latency_ms = elapsed_ms
            invocation.success = True
            invocation.result = extracted
            invocation.input_tokens = response.usage.prompt_tokens
            invocation.output_tokens = response.usage.completion_tokens
            invocation.total_tokens = response.usage.total_tokens
            
            self.batch_tokens_used += invocation.total_tokens
            self.invocations.append(invocation)
            
            logger.info(f"Qwen extraction successful ({elapsed_ms}ms, {invocation.total_tokens} tokens)")
            return extracted
            
        except Exception as e:
            invocation.success = False
            invocation.error = str(e)
            self.invocations.append(invocation)
            logger.error(f"Qwen extraction failed: {e}")
            return None
    
    
    def _extract_with_deepseek(self, html_body: str, fields: List[str]) -> Optional[Dict]:
        """使用DeepSeek提取（魔搭社区）"""
        if not self.deepseek_client:
            logger.warning("DeepSeek client not available")
            return None
        
        invocation = AiInvocation(
            invocation_id=f"deepseek_{int(time.time()*1000)}",
            provider="deepseek",
            model="deepseek-ai/DeepSeek-V3.2"  # 魔搭ModelScope Model-Id
        )
        
        try:
            prompt = self._build_extraction_prompt(html_body, fields)
            start_time = time.time()
            
            # 魔搭DeepSeek调用（非流式）
            response = self.deepseek_client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V3.2",  # ModelScope Model-Id
                messages=[
                    {"role": "system", "content": "你是一个专业的信息提取助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens,
                stream=False  # 非流式
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 解析结果
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            import json
            extracted = json.loads(result_text)
            
            # 记录成功调用
            invocation.latency_ms = elapsed_ms
            invocation.success = True
            invocation.result = extracted
            invocation.input_tokens = response.usage.prompt_tokens
            invocation.output_tokens = response.usage.completion_tokens
            invocation.total_tokens = response.usage.total_tokens
            
            self.batch_tokens_used += invocation.total_tokens
            self.invocations.append(invocation)
            
            logger.info(f"DeepSeek (魔搭) extraction successful ({elapsed_ms}ms, {invocation.total_tokens} tokens)")
            return extracted
            
        except Exception as e:
            invocation.success = False
            invocation.error = str(e)
            self.invocations.append(invocation)
            logger.error(f"DeepSeek extraction failed: {e}")
            return None
    
    def _build_extraction_prompt(self, html_body: str, fields: List[str]) -> str:
        """构建提取prompt"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_body, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator="\n", strip=True)
        
        # 限制长度
        text = text[:5000]
        
        field_descriptions = {
            "phone": "联系电话（如：025-12345678或010-12345678）",
            "address": "办公地址（如：江苏省南京市玄武区XX路XX号）",
            "email": "电子邮件",
            "fax": "传真号码"
        }
        
        fields_str = "\n".join([f"- {field}: {field_descriptions.get(field, field)}" for field in fields])
        
        return f"""从以下政府网站内容中提取指定字段。

内容:
{text}

需要提取的字段:
{fields_str}

请返回严格的JSON格式，如:
{{"phone": "025-12345678", "address": "江苏省南京市玄武区..."}}

如果某个字段找不到，返回null。只返回JSON，不要其他解释。
"""
    
    def _clean_json_response(self, text: str) -> str:
        """清理JSON响应（移除markdown标记）"""
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    
    def review_uncertain_rule(self, rule: Dict, pages: List[Dict], reason: str) -> Dict:
        """
        使用AI复核UNCERTAIN规则
        
        Args:
            rule: 规则定义
            pages: 所有页面内容（即使locator未匹配）
            reason: UNCERTAIN原因（如 "no_pages_matched"）
        
        Returns:
            {
                "status": "PASS" | "FAIL" | "UNCERTAIN",
                "confidence": float,  # 0.0-1.0
                "reasoning": str,     # AI判断理由
                "suggested_action": str  # 建议操作
            }
        """
        # Cost Control检查
        if self.batch_tokens_used >= self.max_cost_per_batch:
            logger.warning(f"Batch token limit reached, skipping AI review")
            return {
                "status": "UNCERTAIN",
                "confidence": 0.0,
                "reasoning": "Token限额已达上限，无法进行AI复核",
                "suggested_action": "increase_token_limit"
            }
        
        # 尝试主Provider
        result = self._try_review_provider(self.primary_provider, rule, pages, reason)
        if result:
            return result
        
        # 降级到副Provider
        logger.warning(f"Primary provider {self.primary_provider} failed for review, trying fallback")
        result = self._try_review_provider(self.fallback_provider, rule, pages, reason)
        if result:
            return result
        
        # 所有Provider都失败
        logger.error("All AI providers failed for review")
        return {
            "status": "UNCERTAIN",
            "confidence": 0.0,
            "reasoning": "AI复核失败",
            "suggested_action": "manual_review"
        }
    
    def _try_review_provider(self, provider: str, rule: Dict, pages: List[Dict], reason: str) -> Optional[Dict]:
        """尝试使用指定Provider进行复核"""
        if provider == "deepseek":
            return self._review_with_deepseek(rule, pages, reason)
        elif provider == "qwen":
            return self._review_with_qwen(rule, pages, reason)
        elif provider == "glm":
            return self._review_with_glm(rule, pages, reason)
        else:
            logger.error(f"Unknown provider: {provider}")
            return None
    
    def _review_with_deepseek(self, rule: Dict, pages: List[Dict], reason: str) -> Optional[Dict]:
        """使用DeepSeek复核UNCERTAIN规则"""
        if not self.deepseek_client:
            logger.warning("DeepSeek client not available")
            return None
        
        invocation = AiInvocation(
            invocation_id=f"deepseek_review_{int(time.time()*1000)}",
            provider="deepseek",
            model="deepseek-ai/DeepSeek-V3.2"
        )
        
        try:
            prompt = self._build_review_prompt(rule, pages, reason)
            start_time = time.time()
            
            response = self.deepseek_client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V3.2",
                messages=[
                    {"role": "system", "content": "你是一个专业的政务公开评估专家，负责复核不确定的规则判定。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000,
                stream=False
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 解析结果
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            import json
            review_result = json.loads(result_text)
            
            # 记录成功调用
            invocation.latency_ms = elapsed_ms
            invocation.success = True
            invocation.result = review_result
            invocation.input_tokens = response.usage.prompt_tokens
            invocation.output_tokens = response.usage.completion_tokens
            invocation.total_tokens = response.usage.total_tokens
            
            self.batch_tokens_used += invocation.total_tokens
            self.invocations.append(invocation)
            
            logger.info(f"DeepSeek review successful: {review_result['status']} (confidence: {review_result['confidence']:.2f})")
            return review_result
            
        except Exception as e:
            invocation.success = False
            invocation.error = str(e)
            self.invocations.append(invocation)
            logger.error(f"DeepSeek review failed: {e}")
            return None
    
    def _review_with_qwen(self, rule: Dict, pages: List[Dict], reason: str) -> Optional[Dict]:
        """使用Qwen复核UNCERTAIN规则"""
        if not self.qwen_client:
            return None
        
        invocation = AiInvocation(
            invocation_id=f"qwen_review_{int(time.time()*1000)}",
            provider="qwen",
            model="Qwen/Qwen3-32B"
        )
        
        try:
            prompt = self._build_review_prompt(rule, pages, reason)
            start_time = time.time()
            
            response = self.qwen_client.chat.completions.create(
                model="Qwen/Qwen3-32B",
                messages=[
                    {"role": "system", "content": "你是一个专业的政务公开评估专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000,
                stream=False,
                extra_body={"enable_thinking": False}
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            import json
            review_result = json.loads(result_text)
            
            invocation.latency_ms = elapsed_ms
            invocation.success = True
            invocation.result = review_result
            invocation.input_tokens = response.usage.prompt_tokens
            invocation.output_tokens = response.usage.completion_tokens
            invocation.total_tokens = response.usage.total_tokens
            
            self.batch_tokens_used += invocation.total_tokens
            self.invocations.append(invocation)
            
            logger.info(f"Qwen review successful: {review_result['status']} (confidence: {review_result['confidence']:.2f})")
            return review_result
            
        except Exception as e:
            invocation.success = False
            invocation.error = str(e)
            self.invocations.append(invocation)
            logger.error(f"Qwen review failed: {e}")
            return None
    
    def _review_with_glm(self, rule: Dict, pages: List[Dict], reason: str) -> Optional[Dict]:
        """使用GLM复核UNCERTAIN规则"""
        if not self.glm_client:
            return None
        
        invocation = AiInvocation(
            invocation_id=f"glm_review_{int(time.time()*1000)}",
            provider="glm",
            model="ZhipuAI/GLM-4.7"
        )
        
        try:
            prompt = self._build_review_prompt(rule, pages, reason)
            start_time = time.time()
            
            response = self.glm_client.chat.completions.create(
                model="ZhipuAI/GLM-4.7",
                messages=[
                    {"role": "system", "content": "你是一个专业的政务公开评估专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000,
                stream=False
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            import json
            review_result = json.loads(result_text)
            
            invocation.latency_ms = elapsed_ms
            invocation.success = True
            invocation.result = review_result
            invocation.input_tokens = response.usage.prompt_tokens
            invocation.output_tokens = response.usage.completion_tokens
            invocation.total_tokens = response.usage.total_tokens
            
            self.batch_tokens_used += invocation.total_tokens
            self.invocations.append(invocation)
            
            logger.info(f"GLM review successful: {review_result['status']} (confidence: {review_result['confidence']:.2f})")
            return review_result
            
        except Exception as e:
            invocation.success = False
            invocation.error = str(e)
            self.invocations.append(invocation)
            logger.error(f"GLM review failed: {e}")
            return None
    
    def _build_review_prompt(self, rule: Dict, pages: List[Dict], reason: str) -> str:
        """构建AI复核prompt"""
        from bs4 import BeautifulSoup
        
        # 提取所有页面的文本内容（最多3个页面）
        page_texts = []
        for page in pages[:3]:
            soup = BeautifulSoup(page.get("body", ""), 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator="\n", strip=True)
            page_texts.append(text[:2000])  # 每个页面最多2000字符
        
        combined_text = "\n\n---\n\n".join(page_texts)
        
        # 构建规则描述
        rule_desc = rule.get("description", "")
        locator = rule.get("locator", {})
        evaluator = rule.get("evaluator", {})
        
        locator_keywords = locator.get("keywords", [])
        evaluator_keywords = evaluator.get("keywords", [])
        
        return f"""你是政务公开评估专家。一条规则被标记为UNCERTAIN（不确定），需要你复核。

**规则描述**: {rule_desc}

**UNCERTAIN原因**: {reason}

**规则要求**:
- 定位关键词: {locator_keywords}
- 评估关键词: {evaluator_keywords}

**网站内容摘要**:
{combined_text}

**任务**: 
基于上述网站内容，判断该规则应该是PASS（通过）还是FAIL（失败），还是确实UNCERTAIN（无法判断）。

请返回JSON格式:
{{
    "status": "PASS" 或 "FAIL" 或 "UNCERTAIN",
    "confidence": 0.0到1.0之间的数字（置信度，如0.85表示85%确定）,
    "reasoning": "你的判断理由，用中文简要说明（1-2句话）",
    "suggested_action": "建议的操作，如manual_review（人工复核）、add_keywords（添加关键词）等"
}}

注意:
- 只有confidence > 0.8时才建议改变状态为PASS或FAIL
- 如果confidence <= 0.8，应保持UNCERTAIN
- reasoning要具体，指出在哪里找到（或未找到）相关内容
"""
    
    def get_invocation_stats(self) -> Dict:
        """获取AI调用统计"""
        total = len(self.invocations)
        success = sum(1 for inv in self.invocations if inv.success)
        
        total_tokens = sum(inv.total_tokens for inv in self.invocations)
        avg_latency = sum(inv.latency_ms for inv in self.invocations) / total if total > 0 else 0
        
        provider_stats = {}
        for inv in self.invocations:
            if inv.provider not in provider_stats:
                provider_stats[inv.provider] = {"total": 0, "success": 0}
            provider_stats[inv.provider]["total"] += 1
            if inv.success:
                provider_stats[inv.provider]["success"] += 1
        
        return {
            "total_invocations": total,
            "successful_invocations": success,
            "success_rate": success / total if total > 0 else 0,
            "total_tokens_used": total_tokens,
            "batch_tokens_remaining": self.max_cost_per_batch - self.batch_tokens_used,
            "average_latency_ms": int(avg_latency),
            "provider_stats": provider_stats
        }
    
    def generate_audit_report(self) -> str:
        """生成AI审计报告（Markdown）"""
        stats = self.get_invocation_stats()
        
        md = []
        md.append("# AI调用审计报告\n\n")
        md.append(f"**生成时间**: {datetime.utcnow().isoformat()}Z\n\n")
        
        md.append("## 📊 调用统计\n\n")
        md.append(f"- **总调用次数**: {stats['total_invocations']}\n")
        md.append(f"- **成功次数**: {stats['successful_invocations']}\n")
        md.append(f"- **成功率**: {stats['success_rate']:.1%}\n")
        md.append(f"- **Token消耗**: {stats['total_tokens_used']} / {self.max_cost_per_batch}\n")
        md.append(f"- **平均延迟**: {stats['average_latency_ms']}ms\n\n")
        
        md.append("## 🔌 Provider统计\n\n")
        md.append("| Provider | 调用次数 | 成功次数 | 成功率 |\n")
        md.append("|----------|----------|----------|--------|\n")
        for provider, ps in stats['provider_stats'].items():
            rate = ps['success'] / ps['total'] if ps['total'] > 0 else 0
            md.append(f"| {provider} | {ps['total']} | {ps['success']} | {rate:.1%} |\n")
        md.append("\n")
        
        md.append("## 📋 详细调用记录\n\n")
        md.append("| 时间 | Provider | 延迟 | Tokens | 状态 |\n")
        md.append("|------|----------|------|--------|------|\n")
        for inv in self.invocations[-50:]:  # 最多显示50条
            status = "✅" if inv.success else f"❌ {inv.error[:30]}"
            md.append(f"| {inv.timestamp} | {inv.provider} | {inv.latency_ms}ms | {inv.total_tokens} | {status} |\n")
        
        return "".join(md)
