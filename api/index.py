"""Vercel entrypoint: serves only the /finance workflow from pdf_editor.Handler."""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdf_editor import Handler

# Only the finance page and the routes it calls are exposed on Vercel.
FINANCE_GET = {
    '/finance', '/api/finance/decision-status', '/api/finance/linked-demo',
    '/amount-format.js', '/finance-edits.js', '/finance-preview.js', '/linked-finance.js',
}
FINANCE_POST = {
    '/api/finance/prepare', '/api/finance/workflow-analyze', '/api/finance/workflow-analyze-start',
    '/api/finance/analysis-job', '/api/finance/workflow-plan',
    '/api/finance/workflow-apply', '/api/finance/linked-analyze', '/api/finance/linked-plan',
    '/api/finance/linked-apply', '/api/general/dependencies', '/api/general/preview',
}


class handler(Handler):
    def _restore_path(self):
        # vercel.json rewrites every URL to /api/index?__path=<original path>.
        original = parse_qs(urlsplit(self.path).query).get('__path')
        if original:
            self.path = original[0]

    def do_GET(self):
        self._restore_path()
        if self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/finance')
            self.end_headers()
            return
        if self.path not in FINANCE_GET:
            return self.reply(404, {'error': 'Not found'})
        return super().do_GET()

    def do_POST(self):
        self._restore_path()
        if self.path not in FINANCE_POST:
            return self.reply(404, {'error': 'Not found'})
        # Same-origin check: allow the deployment's own host (preview and production URLs differ).
        host = self.headers.get('Host')
        self.allowed_origins = Handler.allowed_origins | ({'https://' + host} if host else set())
        return super().do_POST()
