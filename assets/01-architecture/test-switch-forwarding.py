#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('check', Path(__file__).with_name('check-switch-forwarding.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Forwarding(unittest.TestCase):
    def fixture(self, tools_up=False):
        return '\n'.join(f'Et{p} {"connected" if p < 3 or tools_up else "notconnect"} 20 full 10G 10GBASE-CR' for p in (1,2,11,12))+'\n'+'\n'.join(f'Et{p} designated forwarding 2000' for p in ((1,2,11,12) if tools_up else (1,2)))
    def test_parked_and_connected_tools(self):
        module.check(self.fixture())
        module.check(self.fixture(True))
    def test_real_faults_remain_rejected(self):
        cases=[self.fixture().replace('Et1 connected','Et1 notconnect'),
               self.fixture(True).replace('Et11 designated forwarding','Et11 designated discarding'),
               self.fixture().replace('Et12 notconnect 20','Et12 notconnect 100'),
               self.fixture().replace('Et12 notconnect','Et12 disabled'),
               '\n'.join(l for l in self.fixture().splitlines() if not l.startswith('Et2 '))]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):module.check(text)

if __name__=='__main__':unittest.main()
