"""Local integration: compiled Trader, Soup/OUCH peer, and captured IPv4 headers."""
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest

BINARY = os.environ.get('FLLE_QOS_TEST_BINARY', '/tmp/flle-posix-qos/flle-trader')

class OrderDscpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        checkpoint = Path(self.tmp.name) / 'book'
        checkpoint.write_bytes(b'FLLEB01\0' + struct.pack('!Q', 2) + b''.join(
            struct.pack('!Q8scII', n, b'AAPL    ', side, 1000, price)
            for n, side, price in [(1,b'B',1000000),(2,b'S',1000001)]))
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1',0)); self.listener.listen(); self.listener.settimeout(.2)
        self.addCleanup(self.listener.close)
        self.order_port = self.listener.getsockname()[1]
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); self.port = s.getsockname()[1]
        self.stop = threading.Event(); self.hold = threading.Event(); self.hold.set()
        self.inflight = threading.Event(); self.client = None
        self.peer = threading.Thread(target=self.exchange,daemon=True); self.peer.start()
        self.addCleanup(self.end_peer)
        self.proc = subprocess.Popen([BINARY,'--role','MANUAL','--management-ip','127.0.0.1',
            '--management-port',str(self.port),'--data-ip','127.0.0.1','--exchange-data-ip','127.0.0.1',
            '--order-port',str(self.order_port),'--market-receiver','0','--lock-order-queue','1',
            '--book-checkpoint',str(checkpoint),'--telemetry-host','127.0.0.1'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.end_process)
        self.wait(lambda:self.command('STATE').get('status')=='ONLINE')

    def end_process(self):
        self.hold.set(); self.proc.terminate(); self.proc.communicate(timeout=5)

    def end_peer(self):
        self.stop.set(); self.hold.set()
        if self.client:
            try: self.client.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        self.peer.join(2)

    def exchange(self):
        while not self.stop.is_set():
            try: c,_ = self.listener.accept()
            except (OSError,socket.timeout): continue
            self.client = c
            with c:
                f=c.makefile('rb')
                try:
                    while not self.stop.is_set():
                        h=f.read(2)
                        if len(h)!=2: break
                        frame=f.read(struct.unpack('!H',h)[0]); kind=frame[:1]
                        if kind==b'L': out=b'A'+b'TEST      '+b'00000000000000000001'
                        elif kind==b'U':
                            self.inflight.set(); self.hold.wait(3)
                            user=struct.unpack('!I',frame[2:6])[0]
                            out=b'S'+struct.pack('!cQIIQcQH',b'E',0,user,1,1000001,b'A',user,0)
                        else: raise RuntimeError('unexpected Soup message')
                        c.sendall(struct.pack('!H',len(out))+out)
                except (OSError,ValueError): pass
                finally: f.close()
            self.client=None

    def command(self,value):
        with socket.create_connection(('127.0.0.1',self.port),timeout=4) as c:
            c.sendall(value.encode()+b'\n')
            return json.loads(c.makefile('rb').readline())

    def wait(self,predicate):
        end=time.monotonic()+5
        while time.monotonic()<end:
            try:
                if predicate(): return
            except ConnectionRefusedError: pass
            time.sleep(.01)
        self.fail('condition timed out')

    def order(self,measurement=False):
        fills=self.command('STATE')['stats']['fills']
        result=self.command(('MEASUREMENT_ORDER' if measurement else 'ORDER')+'|AAPL|BUY|1|9999999')
        self.assertTrue(result.get('ok'),result)
        self.wait(lambda:self.command('STATE')['stats']['fills']==fills+1)

    def test_default_toggle_restore_and_comparison_guard(self):
        before=self.command('ORDER_DSCP|GET')
        self.assertEqual((before['dscp'],before['tos'],before['connected']),(0,None,False))
        self.order(measurement=True)
        a=self.command('ORDER_DSCP|GET'); self.assertEqual(a['tos']>>2,0)
        self.assertIn('error',self.command('ORDER_DSCP|46|'+str(a['pid']+1)))
        self.assertEqual(self.command('ORDER_DSCP|GET')['dscp'],0)
        for bad in ('-1','64','999','abc','46oops',''):
            self.assertIn('error',self.command('ORDER_DSCP|'+bad))
        self.assertEqual(self.command('ORDER_DSCP|46')['tos']>>2,46)
        self.assertIn('error',self.command('MEASUREMENT_ORDER|AAPL|BUY|1|9999999'))
        self.order()
        b=self.command('ORDER_DSCP|0')
        self.assertEqual((b['tos']>>2,b['local_port']),(0,a['local_port']))
        self.order(measurement=True)
        self.assertEqual(self.command('STATE')['measurement_latency']['ready_samples'],2)

    def test_busy_change_is_rejected(self):
        self.hold.clear(); self.inflight.clear()
        self.assertTrue(self.command('ORDER|AAPL|BUY|1|9999999')['ok'])
        self.assertTrue(self.inflight.wait(2))
        self.assertIn('error',self.command('ORDER_DSCP|46'))
        self.hold.set(); self.wait(lambda:self.command('STATE')['stats']['fills']==1)
        self.assertEqual(self.command('ORDER_DSCP|GET')['dscp'],0)

    def test_mark_survives_reconnect(self):
        self.command('ORDER_DSCP|46'); self.order()
        a=self.command('ORDER_DSCP|GET')
        self.client.shutdown(socket.SHUT_RDWR)
        self.order()
        b=self.command('ORDER_DSCP|GET')
        self.assertNotEqual(a['local_port'],b['local_port'])
        self.assertEqual(b['tos']>>2,46)
        self.command('ORDER_DSCP|0')

    def test_actual_ipv4_header(self):
        # Observe TCP packets, not merely getsockopt results; root/CAP_NET_RAW required.
        raw=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_TCP)
        self.addCleanup(raw.close); raw.bind(('127.0.0.1',0)); raw.settimeout(2)
        for dscp in (0,46,0):
            self.assertTrue(self.command('ORDER_DSCP|'+str(dscp))['ok'])
            self.order()
            seen=[]
            deadline=time.monotonic()+.5
            while time.monotonic()<deadline:
                try: p=raw.recv(65536)
                except socket.timeout: break
                iplen=(p[0]&15)*4
                dest=struct.unpack('!H',p[iplen+2:iplen+4])[0]
                tcplen=(p[iplen+12]>>4)*4
                if dest==self.order_port and len(p)>iplen+tcplen: seen.append(p[1]>>2)
            self.assertTrue(seen)
            self.assertEqual(set(seen),{dscp})

if __name__=='__main__': unittest.main()
