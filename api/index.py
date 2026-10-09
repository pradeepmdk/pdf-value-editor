"""Vercel entrypoint: serves the same Handler as pdf_editor.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdf_editor import Handler


class handler(Handler):
    def do_POST(self):
        # Same-origin check: allow the deployment's own host (preview and production URLs differ).
        host = self.headers.get('Host')
        self.allowed_origins = Handler.allowed_origins | ({'https://' + host} if host else set())
        return super().do_POST()
