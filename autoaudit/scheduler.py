"""
批次调度器
支持cron表达式的定时批次调度
"""
import logging
from typing import Dict, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    logger.warning("apscheduler not installed. Scheduling features disabled.")
    SCHEDULER_AVAILABLE = False


class BatchScheduler:
    """批次调度器"""
    
    def __init__(self):
        self.scheduler = None
        self.jobs = {}
        
        if SCHEDULER_AVAILABLE:
            self.scheduler = BackgroundScheduler()
            logger.info("BatchScheduler initialized")
        else:
            logger.warning("Scheduler not available (install apscheduler)")
    
    def schedule_batch(
        self, 
        job_id: str,
        cron_expr: str,
        batch_func: Callable,
        batch_config: Dict
    ):
        """
        调度批次
        
        Args:
            job_id: 任务ID
            cron_expr: Cron表达式，如"0 2 * * *" (每天2点)
            batch_func: 批次执行函数
            batch_config: 批次配置
        """
        if not self.scheduler:
            logger.error("Scheduler not available")
            return False
        
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
            
            self.scheduler.add_job(
                func=batch_func,
                trigger=trigger,
                args=[batch_config],
                id=job_id,
                name=f"Batch: {job_id}",
                replace_existing=True
            )
            
            self.jobs[job_id] = {
                "cron": cron_expr,
                "config": batch_config,
                "added_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Scheduled job '{job_id}' with cron '{cron_expr}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule job '{job_id}': {e}")
            return False
    
    def start(self):
        """启动调度器"""
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
            return True
        return False
    
    def stop(self):
        """停止调度器"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
            return True
        return False
    
    def list_jobs(self) -> Dict:
        """列出所有调度任务"""
        return self.jobs
    
    def remove_job(self, job_id: str):
        """移除调度任务"""
        if self.scheduler:
            try:
                self.scheduler.remove_job(job_id)
                if job_id in self.jobs:
                    del self.jobs[job_id]
                logger.info(f"Removed job '{job_id}'")
                return True
            except Exception as e:
                logger.error(f"Failed to remove job '{job_id}': {e}")
        return False


# 示例调度配置
EXAMPLE_SCHEDULE_CONFIG = {
    "schedules": [
        {
            "job_id": "jiangsu_nightly",
            "cron": "0 2 * * *",  # 每天凌晨2点
            "rulepack": "jiangsu_suqian_v1_1",
            "sites": ["all"]
        },
        {
            "job_id": "shanghai_weekly",
            "cron": "0 3 * * 0",  # 每周日凌晨3点
            "rulepack": "shanghai_v1_0",
            "sites": ["all"]
        }
    ]
}
