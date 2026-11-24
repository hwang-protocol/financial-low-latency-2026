#!/usr/bin/env python3
"""Extract the pinned sfutils source tarball without requiring RPM on .111."""
import argparse
import gzip
import hashlib
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'artifacts/blobs/x2522/sfutils/8.3.3.1000/SF-105095-LS-68-linux-vmware-esx-utilities-source.zip'
ZIP_SHA = '8c5645275fb5fcc857b30f324c67dfd0bfbaa3ec47dc922cae38aabb27b81230'
RPM_NAME = 'sfutils-8.3.3.1000-1.src.rpm'
RPM_SHA = 'c1b0313981f02fb011160194c94d16e5e0820cb3cf56eff860435fb039f51e8a'
TAR_NAME = 'sfutils-8.3.3.1000.tar.gz'
TAR_SHA = '258ae93bd116c767188a4cf91917d5420dd1f3124a0279e51affcd63cebd6403'


def checked(data, expected, name):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'{name} 摘要不符；停止准备，不转公网下载。')
    return data


def header_end(data, offset):
    if data[offset:offset + 4] != b'\x8e\xad\xe8\x01':
        raise ValueError('不是预期的 RPM 头')
    count, size = struct.unpack_from('>II', data, offset + 8)
    return offset + 16 + count * 16 + size


def extract_source(archive=ARCHIVE):
    checked(archive.read_bytes(), ZIP_SHA, archive.name)
    with zipfile.ZipFile(archive) as source:
        rpm = checked(source.read(RPM_NAME), RPM_SHA, RPM_NAME)
    # RPM lead, aligned signature header, main header, then gzip/newc payload.
    signature_end = header_end(rpm, 96)
    payload = gzip.decompress(rpm[header_end(rpm, (signature_end + 7) & ~7):])
    offset = 0
    while offset + 110 <= len(payload):
        header = payload[offset:offset + 110]
        if header[:6] != b'070701':
            raise ValueError('不是预期的 CPIO newc 格式')
        size = int(header[54:62], 16)
        name_size = int(header[94:102], 16)
        name = payload[offset + 110:offset + 110 + name_size - 1].decode('utf-8')
        start = (offset + 110 + name_size + 3) & ~3
        if name == TAR_NAME:
            return checked(payload[start:start + size], TAR_SHA, TAR_NAME)
        if name == 'TRAILER!!!':
            break
        offset = (start + size + 3) & ~3
    raise ValueError('固定 RPM 中未找到 sfutils 源码包')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        source = extract_source()
        with args.output.open('xb') as output:
            output.write(source)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc)) from exc
    print('sfutils 8.3.3.1000 源码已就绪；ZIP、RPM、源码包三层 SHA-256 核对通过。')


if __name__ == '__main__':
    main()
