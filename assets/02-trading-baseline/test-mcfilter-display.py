#!/usr/bin/env python3
"""Check real proc format details without requiring a lab interface."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
SPEC=importlib.util.spec_from_file_location('mcfilter',Path(__file__).with_name('format-mcfilter.py'))
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)

class McfilterDisplayTest(unittest.TestCase):
    def test_index_and_hex_addresses_not_truncated_device_names(self):
        raw='Idx Device MCA SRC INC EXC\n4 ens64n 0xe94a7d20 0x14010101 1 0\n4 ens64n 0xe94a7d21 0x14010101 1 0\n5 ens64n 0xe94a7d20 0x14010102 2 1\n'
        with contextlib.redirect_stdout(io.StringIO()) as out:MOD.display(raw,4,'ens64np1')
        self.assertEqual(out.getvalue().splitlines(),[
            'ens64np1 (Idx=4)  源 20.1.1.1 → 组 233.74.125.32  INC=1 EXC=0',
            'ens64np1 (Idx=4)  源 20.1.1.1 → 组 233.74.125.33  INC=1 EXC=0'])

    def test_missing_or_excluded_sources_are_not_printed_as_success(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:MOD.display('Idx Device MCA SRC INC EXC\n',4,'ens64np1')
        self.assertIn('[未读到]',out.getvalue());self.assertNotIn('20.1.1.1',out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:MOD.display('4 ens64n 0xe94a7d20 0x14010101 0 2\n',4,'ens64np1')
        self.assertIn('INC=0 EXC=2',out.getvalue())
        with self.assertRaises(ValueError):MOD.display('4 broken\n',4,'ens64np1')

if __name__=='__main__':unittest.main()
