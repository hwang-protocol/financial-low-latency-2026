"""Software measurements fix A only and restore even when work fails."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from software_measurement import fixed_market_mode


class FixedMarketModeTest(unittest.TestCase):
    def test_success_and_measurement_failure_restore_original(self):
        for fails in (False, True):
            with self.subTest(fails=fails), tempfile.TemporaryDirectory() as td:
                receipt = Path(td) / 'mode.json'
                state = {'market_mode': 'DUAL', 'market_network': {'market_schema': 'udp-multicast-ab-v1'}}
                with patch('software_measurement.http_json', return_value=state), patch('software_measurement.set_market_mode') as change, contextlib.redirect_stdout(io.StringIO()):
                    try:
                        with fixed_market_mode('http://fixture.invalid', receipt):
                            self.assertFalse(json.loads(receipt.read_text())['restored'])
                            if fails: raise ValueError('measurement failed')
                    except ValueError:
                        self.assertTrue(fails)
                    self.assertEqual([c.args[1] for c in change.call_args_list], ['MULTICAST_A', 'DUAL'])
                    self.assertTrue(json.loads(receipt.read_text())['restored'])

    def test_initial_switch_failure_still_restores_and_restore_failure_is_125(self):
        for effects, expected in (([RuntimeError('switch failed'), None], RuntimeError),
                                  ([None, RuntimeError('restore failed')], SystemExit)):
            with tempfile.TemporaryDirectory() as td, patch('software_measurement.http_json', return_value={'market_mode':'MULTICAST_B','market_network':{'market_schema':'udp-multicast-ab-v1'}}), patch('software_measurement.set_market_mode', side_effect=effects) as change, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(expected) as caught:
                    with fixed_market_mode('http://fixture.invalid', Path(td)/'mode.json'): pass
                self.assertEqual(change.call_count, 2)
                if expected is SystemExit: self.assertEqual(caught.exception.code, 125)

    def test_old_exchange_is_rejected_before_changes(self):
        with patch('software_measurement.http_json', return_value={'market_mode':'DUAL'}), patch('software_measurement.set_market_mode') as change:
            with self.assertRaises(SystemExit):
                with fixed_market_mode('http://fixture.invalid', Path('/unused')): pass
            change.assert_not_called()


if __name__ == '__main__': unittest.main()
