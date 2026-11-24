#!/usr/bin/env python3
"""Build a small GUI/Linux handoff from canonical chapter 09 sources."""
import hashlib
from pathlib import Path
import zipfile

here = Path(__file__).resolve().parent
source = here.parent
repo = here.parents[2]
destination = repo / "artifacts/blobs/ch09-vivado/flle-ch09-vivado.zip"
files = {
    name: (source / name).read_bytes()
    for name in ("market_filter.sv", "mold_filter_adapter.cpp",
                 "market_filter_tb.cpp", "offline-selftest.sh")
}
files["market_filter_sim_tb.sv"] = (here / "market_filter_sim_tb.sv").read_bytes()
files["README.md"] = (here / "README.md").read_bytes()
files["SHA256SUMS"] = "".join(
    f"{hashlib.sha256(data).hexdigest()}  {name}\n"
    for name, data in sorted(files.items())
).encode()
destination.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name, data in sorted(files.items()):
        info = zipfile.ZipInfo(f"flle-ch09-vivado/{name}", date_time=(2026, 9, 18, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, data)
digest = hashlib.sha256(destination.read_bytes()).hexdigest()
destination.with_suffix(".zip.sha256").write_text(f"{digest}  {destination.name}\n")
print(f"package={destination}")
print(f"bytes={destination.stat().st_size}")
print(f"sha256={digest}")
