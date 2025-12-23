import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


SCENARIOS = {
    "/pass": {
        "status": 200,
        "body": """
        <html><body>
        <h1>机构信息</h1>
        <div>机构设置：综合办公室</div>
        <div>联系方式：123456789</div>
        <div>负责人：张三</div>
        </body></html>
        """,
    },
    "/missing-leader": {
        "status": 200,
        "body": """
        <html><body>
        <h1>机构信息</h1>
        <div>机构设置：综合办公室</div>
        <div>联系方式：987654321</div>
        </body></html>
        """,
    },
    "/outdated-guide": {
        "status": 200,
        "body": """
        <html><body>
        <h1>政府信息公开指南</h1>
        <div>更新日期：2022-01-01</div>
        </body></html>
        """,
    },
    "/synonym": {
        "status": 200,
        "body": """
        <html><body>
        <h1>依申请服务</h1>
        <p>请使用在线表单提交申请</p>
        </body></html>
        """,
    },
    "/attachment": {
        "status": 200,
        "body": """
        <html><body>
        <h1>年度报告</h1>
        <a href="/attachments/missing.pdf">下载</a>
        </body></html>
        """,
    },
    "/blocked": {"status": 403, "body": "Forbidden"},
    "/ratelimited": {"status": 429, "body": "Too Many Requests"},
}


class SandboxHandler(BaseHTTPRequestHandler):
    def _write(self, code: int, body: str):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/paged":
            page = int(parse_qs(parsed.query).get("page", [1])[0])
            next_link = "<a href='/paged?page=2'>下一页</a>" if page == 1 else ""
            body = f"<html><body><h1>列表第{page}页</h1><a href='/pass'>最新</a>{next_link}</body></html>"
            return self._write(200, body)
        scenario = SCENARIOS.get(parsed.path)
        if scenario:
            return self._write(scenario["status"], scenario["body"])
        return self._write(404, "Not Found")

    def log_message(self, fmt, *args):  # noqa: D401
        return


class SandboxServer(HTTPServer):
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        super().__init__((host, port), SandboxHandler)

    def serve_in_thread(self):
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        return thread
