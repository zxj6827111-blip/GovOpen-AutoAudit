#!/usr/bin/env python3
"""
修复后的FastAPI服务器 - 自动添加项目路径 + Web UI
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from autoaudit.cli import cmd_import_rulepack, cmd_run_batch
import os

app = FastAPI(title="GovOpen-AutoAudit Platform")

# 挂载静态文件目录
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 请求模型
class BatchRunRequest(BaseModel):
    site_url: str
    rulepack: str
    site_name: str = "未命名网站"

@app.get("/", response_class=HTMLResponse)
def read_root():
    """返回Web UI首页"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return """
    <html>
        <body>
            <h1>GovOpen-AutoAudit Platform</h1>
            <p>Status: OK</p>
            <p>访问 <a href="/docs">/docs</a> 查看API文档</p>
        </body>
    </html>
    """

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "python_version": sys.version,
        "project_root": str(project_root)
    }

@app.post("/batch/run")
def run_batch(request: BatchRunRequest):
    """运行批次任务"""
    return {
        "status": "accepted",
        "message": f"检测任务已创建",
        "site_url": request.site_url,
        "rulepack": request.rulepack,
        "site_name": request.site_name,
        "note": "当前为演示模式，实际检测功能需要通过scripts/run_pilot.py运行"
    }

@app.get("/batch/list")
def list_batches():
    """列出所有批次"""
    try:
        runs_dir = project_root / "runs"
        batches = []
        errors = []
        
        for batch_dir in sorted(runs_dir.glob("batch_*"), reverse=True):
            summary_file = batch_dir / "export" / "summary.json"
            if summary_file.exists():
                try:
                    import json
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary = json.load(f)
                    batches.append({
                        "batch_id": summary.get("batch_id"),
                        "timestamp": summary.get("timestamp"),
                        "status": summary.get("status"),
                        "rulepack": summary.get("rule_pack_id"),
                        "stats": summary.get("statistics")
                    })
                except Exception as e:
                    errors.append(f"{batch_dir.name}: {str(e)}")
                    logger.error(f"Error reading {summary_file}: {e}")
        
        result = {"batches": batches[:20]}
        if errors:
            result["errors"] = errors
        return result
    except Exception as e:
        logger.error(f"Error in list_batches: {e}")
        return {"error": str(e), "batches": []}

@app.get("/batch/{batch_id}")
def get_batch(batch_id: str):
    """获取批次详细结果"""
    try:
        batch_dir = project_root / "runs" / batch_id
        summary_file = batch_dir / "export" / "summary.json"
        issues_file = batch_dir / "export" / "issues.json"
        
        if not summary_file.exists():
            return {"error": "Batch not found"}
        
        import json
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        issues = []
        if issues_file.exists():
            with open(issues_file, 'r', encoding='utf-8') as f:
                issues_data = json.load(f)
                issues = issues_data.get("issues", [])
        
        return {
            "summary": summary,
            "issues": issues
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print(f"项目根目录: {project_root}")
    print(f"静态文件目录: {static_dir}")
    print(f"Python路径已添加，启动服务器...")
    print(f"\n访问 Web UI: http://localhost:8000")
    print(f"访问 API 文档: http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
