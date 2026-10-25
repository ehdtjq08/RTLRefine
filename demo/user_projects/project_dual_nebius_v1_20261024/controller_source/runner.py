"""Closed Icarus commands with only submitted sources and one test mounted."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time

from ..common import write_json
from ..tool_paths import find_tool


class ProjectRunner:
    def __init__(self,*,total_seconds=180):self.deadline=time.monotonic()+total_seconds

    @staticmethod
    def environment():
        paths=[str(Path(find_tool(n)).parent) for n in ('iverilog','vvp') if find_tool(n)]
        return {'PATH':':'.join(dict.fromkeys(paths+['/usr/bin','/bin'])),'LANG':'C','LC_ALL':'C','HOME':'/nonexistent'}

    def sandbox(self,command,directory):
        bwrap=find_tool('bwrap')
        if not bwrap:raise RuntimeError('bubblewrap is required; there is no unisolated fallback')
        args=[bwrap,'--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL','--clearenv']
        for path in ('/usr','/bin','/lib','/lib64','/etc/ld.so.cache'):
            if Path(path).exists():args+=['--ro-bind',path,path]
        prefixes=set()
        for name in ('iverilog','vvp'):
            path=find_tool(name)
            if not path:raise RuntimeError('Missing native tool: '+name)
            if not path.startswith(('/usr/','/bin/')):prefixes.add(str(Path(path).parent.parent))
        for prefix in prefixes:
            if prefix in ('/',str(Path.home()),'/home','/tmp'):raise RuntimeError('Unsafe tool-prefix mount')
            args+=['--ro-bind',prefix,prefix]
        args+=['--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',str(directory.resolve()),'/work',
            '--bind',str((directory/'__rtlrefine').resolve()),'/work/__rtlrefine','--chdir','/work']
        for name,value in self.environment().items():args+=['--setenv',name,value]
        return args+['--setenv','TMPDIR','/tmp','--',*command]

    def probe(self,directory):
        directory.mkdir(parents=True,exist_ok=True);(directory/'__rtlrefine').mkdir(exist_ok=True)
        try:
            r=subprocess.run(self.sandbox(['/bin/true'],directory),env=self.environment(),capture_output=True,text=True,timeout=5)
            return r.returncode==0,(r.stderr or 'Network/filesystem isolation ready')[:1500]
        except (RuntimeError,OSError,subprocess.TimeoutExpired) as exc:return False,str(exc)

    def run(self,stage,arguments,directory,*,timeout=30):
        executable={'preprocess':'iverilog','elaborate':'iverilog','compile':'iverilog','simulate':'vvp'}.get(stage)
        if not executable:raise ValueError('Unknown native project stage')
        path=find_tool(executable)
        if not path:raise RuntimeError('Missing '+executable)
        command=[path,*arguments];record={'stage':stage,'command':command,'status':'ERROR','returncode':None,'execution_mode':'bubblewrap','network':False}
        started=time.monotonic();limit=min(timeout,self.deadline-started);log=directory/(stage+'.log');process=None
        if limit<=0:record['status']='TIMEOUT';log.write_text('Project time budget exhausted\n')
        else:
            try:
                prlimit=find_tool('prlimit')
                if not prlimit:raise RuntimeError('prlimit is required')
                isolated=self.sandbox(command,directory)
                isolated=[prlimit,'--core=0','--as=2147483648','--cpu=60:61','--fsize=16777216','--nofile=128','--',*isolated]
                with log.open('wb') as stream:
                    process=subprocess.Popen(isolated,cwd=directory,env=self.environment(),stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                    record['returncode']=process.wait(timeout=limit)
                record['status']='PASS' if record['returncode']==0 else 'FAIL'
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait();record['status']='TIMEOUT'
            except (OSError,RuntimeError) as exc:log.write_text(str(exc)+'\n')
        record['wall_seconds']=time.monotonic()-started;write_json(directory/(stage+'.command.json'),record)
        return record
