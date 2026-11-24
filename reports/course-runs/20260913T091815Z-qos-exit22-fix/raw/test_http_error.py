from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import threading,tempfile,subprocess,os
class Reject(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_POST(self):
  self.rfile.read(int(self.headers.get('Content-Length',0)))
  self.send_response(400);self.end_headers();self.wfile.write(b'{"error":"FEED_NOT_HEALTHY"}')
srv=ThreadingHTTPServer(('127.0.0.1',0),Reject)
threading.Thread(target=srv.serve_forever,daemon=True).start()
s=Path('Documents/newDoc/assets/06-arista-time/11-qos-real-order-contention-live.sh').read_text();fn=s[s.index('issue_orders() {'):s.index('\nqueue_counter() {')]
with tempfile.TemporaryDirectory() as d:
 env=os.environ.copy();env.update(RAW=d,DERIVED=d,API=f'http://127.0.0.1:{srv.server_port}')
 p=subprocess.run(['bash','-c','set -Eeuo pipefail\n'+fn+'\nissue_orders baseline 1 0'],env=env,text=True,capture_output=True)
 assert p.returncode==22,(p.returncode,p.stdout,p.stderr)
 assert 'FEED_NOT_HEALTHY' in p.stderr and '第 1 笔' in p.stderr,p.stderr
 assert (Path(d)/'baseline-order-error.json').read_text().strip()=='{"error":"FEED_NOT_HEALTHY"}'
 print('PASS: real curl HTTP400 returns22; Chinese diagnosis and response body preserved.')
srv.shutdown()
