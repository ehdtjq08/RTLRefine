"""Install the exact native-checker compiler in the project, with no sudo."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent.parent
PACKAGE='verilator_4.038-1_amd64.deb'
SHA256='3ed130509d5493a3c95e7be97a00cfed7457b2aeb9c11eed96ea3a802c310836'
URL='https://archive.ubuntu.com/ubuntu/pool/universe/v/verilator/'+PACKAGE


def main():
    if platform.machine() not in ('x86_64','amd64'):raise RuntimeError('This pinned package is for Linux amd64')
    tools=ROOT/'.tools';tools.mkdir(exist_ok=True);destination=tools/'verilator'
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix='pinned-verilator-',dir=tools) as name:
            work=Path(name)
            with urlopen(URL,timeout=120) as response:data=response.read(16*1024*1024+1)
            if len(data)>16*1024*1024 or hashlib.sha256(data).hexdigest()!=SHA256:raise RuntimeError('Pinned Verilator package digest mismatch')
            archive=work/PACKAGE;archive.write_bytes(data);staged=work/'root';staged.mkdir()
            subprocess.run(['dpkg-deb','--extract',str(archive),str(staged)],check=True,timeout=30)
            (staged/'install.json').write_text(json.dumps({'version':'Verilator 4.038','url':URL,'package_sha256':SHA256},indent=2)+'\n')
            os.replace(staged,destination)
    binary=next(destination.rglob('verilator_bin'));support=destination/'usr/share/verilator'
    env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','VERILATOR_ROOT':str(support)}
    version=subprocess.check_output([str(binary),'--version'],env=env,text=True,timeout=15).strip()
    if not version.startswith('Verilator 4.038 '):raise RuntimeError('Wrong installed compiler version')
    wrapper=tools/'bin/verilator';wrapper.parent.mkdir(exist_ok=True)
    wrapper.write_text('#!/bin/sh\nexport VERILATOR_ROOT='+shlex.quote(str(support))+'\nexec '+shlex.quote(str(binary))+' "$@"\n')
    wrapper.chmod(0o755)
    print('Ready: '+version)


if __name__=='__main__':main()
