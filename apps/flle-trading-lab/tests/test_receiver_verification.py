"""Reject stale READY files and replaced running images without contacting VMs."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('receiver_verify', Path(__file__).resolve().parents[1] / 'scripts/verify-feed-receiver.py')
VERIFY = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(VERIFY)


class ReceiverVerificationTest(unittest.TestCase):
    def fixture(self, root):
        run=root/'run'; run.mkdir(); proc=root/'proc'; process=proc/'42'; process.mkdir(parents=True)
        boot=proc/'sys/kernel/random/boot_id'; boot.parent.mkdir(parents=True); boot.write_text('boot\n')
        (process/'stat').write_text('42 (receiver test) '+' '.join(['S']+['0']*18+['123'])+'\n')
        (run/'feed-receiver.pid').write_text('42\n')
        (run/'feed-receiver.identity').write_text('pid=42 start_ticks=123 boot_id=boot\n')
        (run/'flle-feed-receiver').write_bytes(b'new receiver'); (process/'exe').symlink_to(run/'flle-feed-receiver')
        (run/'feed-receiver.log').write_text(f'feed_receiver=READY pid=42 market_schema=udp-multicast-ab-v1 multicast_source=20.1.1.1 multicast=233.74.125.32:31032 multicast_b=233.74.125.33:31033 ipc={run}/feed.sock\n')
        return run,proc

    def test_valid_and_stale_receivers(self):
        for fault in ('', 'legacy', 'source', 'b-port', 'stale-ready', 'reused-pid', 'replaced-image'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as td:
                run,proc=self.fixture(Path(td)); log=run/'feed-receiver.log'; text=log.read_text()
                if fault=='legacy': log.write_text(text.replace(' market_schema=udp-multicast-ab-v1', ''))
                if fault=='source': log.write_text(text.replace('20.1.1.1', '20.1.1.9'))
                if fault=='b-port': log.write_text(text.replace(':31033', ':31034'))
                if fault=='stale-ready': log.write_text(text.replace('pid=42', 'pid=41'))
                if fault=='reused-pid': (run/'feed-receiver.identity').write_text('pid=42 start_ticks=122 boot_id=boot')
                if fault=='replaced-image':
                    (run/'flle-feed-receiver.old').write_bytes(b'old receiver')
                    (proc/'42/exe').unlink(); (proc/'42/exe').symlink_to(run/'flle-feed-receiver.old')
                if fault:
                    with self.assertRaises(ValueError): VERIFY.verify(run,proc=proc)
                else: self.assertEqual(VERIFY.verify(run,proc=proc)['pid'],'42')

    def test_ipc_alias_resolves_to_the_same_socket(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);run,proc=self.fixture(root);alias=root/'alias';alias.symlink_to(run,target_is_directory=True)
            log=run/'feed-receiver.log';text=log.read_text();log.write_text(text.replace(f'ipc={run}/',f'ipc={alias}/'))
            self.assertEqual(VERIFY.verify(alias,proc=proc)['pid'],'42')
            log.write_text(text.replace(f'ipc={run}/feed.sock',f'ipc={root}/wrong.sock'))
            with self.assertRaisesRegex(ValueError,'different IPC'):VERIFY.verify(run,proc=proc)

    def test_profile_does_not_override_actual_subscription(self):
        with tempfile.TemporaryDirectory() as td:
            run,proc=self.fixture(Path(td)); (run/'feed-multicast.profile').write_text('1\n')
            p=run/'feed-receiver.log'; p.write_text(p.read_text().replace('233.74.125.33','DISABLED'))
            with self.assertRaises(ValueError): VERIFY.verify(run,proc=proc)


if __name__=='__main__': unittest.main()
