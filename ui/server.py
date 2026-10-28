#!/usr/bin/env python3
"""Read-only local web dashboard. python3 ui/server.py --dir /path/to/desk [--port 8787]
Binds 127.0.0.1 only. Serves ui/index.html and /api/snapshot (JSON built by deskdata.py: logs/state only, never keys/.env)."""
import argparse,json,os,sys
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
H=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,os.path.dirname(H))
import deskdata
ap=argparse.ArgumentParser();ap.add_argument("--dir",default=".");ap.add_argument("--port",type=int,default=8787);ap.add_argument("--no-price",action="store_true")
a=ap.parse_args();D=os.path.abspath(a.dir)
class Hd(BaseHTTPRequestHandler):
    def _send(self,code,body,ct):
        self.send_response(code);self.send_header("Content-Type",ct);self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        p=self.path.split("?")[0]
        if p in("/","/index.html"):self._send(200,open(os.path.join(H,"index.html"),"rb").read(),"text/html; charset=utf-8")
        elif p=="/api/snapshot":
            try:self._send(200,json.dumps(deskdata.snapshot(D,live_price=not a.no_price),default=str).encode(),"application/json")
            except Exception as e:self._send(500,json.dumps({"error":type(e).__name__}).encode(),"application/json")
        else:self._send(404,b"not found","text/plain")
    def log_message(self,*x):pass
print(f"desk UI (read-only) http://127.0.0.1:{a.port}  dir={D}",flush=True)
ThreadingHTTPServer(("127.0.0.1",a.port),Hd).serve_forever()
