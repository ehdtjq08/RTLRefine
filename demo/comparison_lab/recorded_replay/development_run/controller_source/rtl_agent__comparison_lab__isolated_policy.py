"""A custom ranker sees only public JSON and declared model views."""
from pathlib import Path
import json
import subprocess
import sys
import time

from ..tool_paths import find_tool
from .policies import complete


def run_policy(source,packet,views,seed,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    bwrap=find_tool('bwrap');prlimit=find_tool('prlimit')
    if not bwrap or not prlimit:raise RuntimeError('Custom policies require bubblewrap and prlimit')
    command=[bwrap,'--unshare-all','--die-with-parent','--new-session','--clearenv','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/work']
    for path in dict.fromkeys(['/usr','/lib','/lib64',str(Path(sys.prefix).resolve())]):
        if Path(path).exists():command+=['--ro-bind',path,path]
    command+=['--ro-bind',str(Path(source).resolve()),'/work/policy.py',
        '--ro-bind',str(Path(__file__).with_name('policy_worker.py').resolve()),'/work/worker.py',
        '--chdir','/work','--setenv','PATH','/usr/bin:/bin',str(Path(sys.executable).resolve()),'-I','-S','/work/worker.py']
    command=[prlimit,'--core=0','--as=536870912','--fsize=2097152','--nofile=64','--cpu=10:11','--',*command]
    payload={'public':packet,'views':views,'seed':seed};start=time.monotonic()
    with (directory/'stdout.json').open('wb') as stdout,(directory/'stderr.log').open('wb') as stderr:
        try:
            result=subprocess.run(command,input=json.dumps(payload).encode(),stdout=stdout,stderr=stderr,timeout=15,check=False)
        except subprocess.TimeoutExpired:raise ValueError('Custom policy exceeded time limit') from None
    if result.returncode!=0:raise ValueError('Custom policy failed: '+(directory/'stderr.log').read_text()[-1500:])
    value=json.loads((directory/'stdout.json').read_text())
    if not isinstance(value,dict) or set(value)!={'order'} or not isinstance(value['order'],list):raise ValueError('Policy must return a candidate-ID list')
    order=complete(value['order'],packet['orders']['heuristic_order'])
    return order,time.monotonic()-start
