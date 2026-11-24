#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import unittest
SPEC=importlib.util.spec_from_file_location('comparison',Path(__file__).with_name('check-comparison-state.py'))
MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

class ComparisonStateTest(unittest.TestCase):
    def test_same_session_and_restarts(self):
        start={'session':'one','replay':{'loop':1},'feed':{'session':'one','duplicates':50}}
        for fault in ('','session','loop','feed-lag','empty'):
            with self.subTest(fault=fault):
                state=copy.deepcopy(start);state['feed']['duplicates']=55
                if fault=='session':state['session']=state['feed']['session']='two';state['feed']['duplicates']=0
                if fault=='loop':state['replay']['loop']=2
                if fault=='feed-lag':state['feed']['session']='old'
                if fault=='empty':state['feed']['session']=''
                if fault:
                    with self.assertRaises(ValueError):MOD.duplicate_count(start,state)
                else:self.assertEqual(MOD.duplicate_count(start,state),55)

if __name__=='__main__':unittest.main()
