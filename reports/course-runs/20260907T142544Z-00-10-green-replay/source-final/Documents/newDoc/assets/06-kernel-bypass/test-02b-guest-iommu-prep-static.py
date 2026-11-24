#!/usr/bin/env python3
"""Compatibility entry: the authoritative preparation and test live in Chapter 02."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1] / '02-trading-baseline/test-iommu-prep.py'), run_name='__main__')
