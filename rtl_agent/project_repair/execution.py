"""Reduce orchestration overhead around the byte-preserved admission checker.

Only successful DUT preprocessing/base elaboration can be reused, within one
checker call. Tests, actual-profile elaboration and simulation always run fresh.
The separately exported CI continues to use the frozen reference engine.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from ..common import write_json
from ..tool_paths import find_tool
from .runner import ProjectRunner
from .checker import check_project as reference_check

MAX_CACHE_BYTES=32*1024*1024
MAX_CACHE_ENTRIES=16


def wait_for_exit(process,timeout):
    """One blocking waiter wakes the deadline-controlled calling thread on exit."""
    failures=[]
    def wait():
        try:process.wait()
        except BaseException as exc:failures.append(exc)
    waiter=threading.Thread(target=wait,daemon=True,name='rtlrefine-child-wait')
    waiter.start();waiter.join(timeout)
    if waiter.is_alive():raise subprocess.TimeoutExpired(process.args,timeout)
    if failures:raise failures[0]
    return process.returncode


class PhaseRunner(ProjectRunner):
    def __init__(self,*,total_seconds=180):
        super().__init__(total_seconds=total_seconds)
        self._cache={};self._cache_bytes=0

    def _key(self,stage,arguments,directory,path):
        if stage not in ('preprocess','elaborate'):return None
        # The verdict header appears only after base DUT elaboration. Never
        # reuse an elaboration performed with any testbench files mounted.
        if (directory/'rtlrefine_check.vh').exists():return None
        binary=Path(path).resolve();stat=binary.stat()
        h=hashlib.sha256(json.dumps({'stage':stage,'arguments':arguments,'tool':str(binary),
            'tool_stat':[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns],
            'environment':self.environment(),'policy':'reference-bwrap-prlimit-v1'},sort_keys=True).encode())
        for item in sorted(directory.rglob('*')):
            rel=item.relative_to(directory)
            if not item.is_file():continue
            # Elaboration consumes the expanded design. All other generated
            # logs/command records are outputs, not compiler inputs.
            if rel.parts[0]=='__rtlrefine' and rel.as_posix()!='__rtlrefine/design.v':continue
            if stage=='preprocess' and rel.parts[0]=='__rtlrefine':continue
            name=rel.as_posix().encode();data=item.read_bytes()
            if b'`__DATE__' in data or b'`__TIME__' in data:return None
            h.update(len(name).to_bytes(8,'big'));h.update(name)
            h.update(len(data).to_bytes(8,'big'));h.update(hashlib.sha256(data).digest())
        return h.hexdigest()

    def run(self,stage,arguments,directory,*,timeout=30):
        executable={'preprocess':'iverilog','test_preprocess':'iverilog','elaborate':'iverilog','compile':'iverilog','simulate':'vvp'}.get(stage)
        if not executable:raise ValueError('Unknown native project stage')
        path=find_tool(executable)
        if not path:raise RuntimeError('Missing '+executable)
        command=[path,*arguments]
        record={'stage':stage,'command':command,'status':'ERROR','returncode':None,'execution_mode':'bubblewrap','network':False,
                'wait_strategy':'blocking-thread','cache_hit':False}
        started=time.monotonic();limit=min(timeout,self.deadline-started)
        log=directory/'__rtlrefine'/(stage+'.log');process=None
        key=self._key(stage,arguments,directory,path) if limit>0 else None
        cached=self._cache.get(key)
        if cached and time.monotonic()<self.deadline:
            if stage=='preprocess':(directory/'__rtlrefine/design.v').write_bytes(cached['expanded'])
            log.write_bytes(cached['log'])
            record.update(status='PASS',returncode=0,execution_mode='phase-local-compiler-reuse',cache_hit=True,
                          reuse_input_sha256=key,reused_from=cached['origin'])
        elif limit<=0:
            record['status']='TIMEOUT';log.write_text('Project time budget exhausted\n')
        else:
            try:
                prlimit=find_tool('prlimit')
                if not prlimit:raise RuntimeError('prlimit is required')
                isolated=self.sandbox(command,directory)
                isolated=[prlimit,'--core=0','--as=2147483648','--cpu=60:61','--fsize=16777216','--nofile=128','--',*isolated]
                with log.open('wb') as stream:
                    process=subprocess.Popen(isolated,cwd=directory,env=self.environment(),stdin=subprocess.DEVNULL,
                        stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                    record['returncode']=wait_for_exit(process,limit)
                record['status']='PASS' if record['returncode']==0 else 'FAIL'
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait();record['status']='TIMEOUT'
            except (OSError,RuntimeError) as exc:log.write_text(str(exc)+'\n')
            if key is not None and record['status']=='PASS' and len(self._cache)<MAX_CACHE_ENTRIES:
                entry={'log':log.read_bytes(),'origin':str(directory/'__rtlrefine'/(stage+'.command.json'))}
                if stage=='preprocess':entry['expanded']=(directory/'__rtlrefine/design.v').read_bytes()
                size=len(entry['log'])+len(entry.get('expanded',b''))
                if self._cache_bytes+size<=MAX_CACHE_BYTES:
                    self._cache[key]=entry;self._cache_bytes+=size
        record['wall_seconds']=time.monotonic()-started
        write_json(directory/'__rtlrefine'/(stage+'.command.json'),record)
        return record


def check_project(project,changes,directory,*,phase='all',runner=None,interfaces=None):
    # A new runner owns every phase. No state crosses original/candidate/final
    # checks, and the standalone gate has its own unchanged reference engine.
    return reference_check(project,changes,directory,phase=phase,runner=runner or PhaseRunner(),interfaces=interfaces)
