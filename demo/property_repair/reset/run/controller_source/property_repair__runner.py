"""Yosys-only stages added to the existing readonly project-worker boundary."""
import os
from pathlib import Path
import signal
import subprocess
import time

from ..common import write_json
from ..project_repair.runner import ProjectRunner
from ..tool_paths import find_tool


class PropertyRunner(ProjectRunner):
    def sandbox(self,command,directory):
        args=super().sandbox(command,directory)
        position=args.index('--')
        bindings=[]
        prefixes=set()
        for name in ('yosys',):
            tool=find_tool(name)
            if tool and not tool.startswith(('/usr/','/bin/')):prefixes.add(str(Path(tool).parent.parent))
        for prefix in prefixes:
            if prefix in ('/',str(Path.home()),'/home','/tmp'):raise RuntimeError('Unsafe property-tool prefix')
            bindings+=['--ro-bind',prefix,prefix]
        for path in sorted((directory/'__rtlrefine/frozen').rglob('*')):
            if path.is_file():bindings+=['--ro-bind',str(path.resolve()),'/work/'+path.relative_to(directory).as_posix()]
        return args[:position]+bindings+args[position:]

    def run(self,stage,arguments,directory,*,timeout=35):
        if stage not in ('prepare_properties','solve_properties'):
            return super().run(stage,arguments,directory,timeout=timeout)
        tool=find_tool('yosys');limiter=find_tool('prlimit')
        if not tool or not limiter:raise RuntimeError('Yosys and prlimit are required')
        if arguments:raise ValueError('Property tools accept no caller arguments')
        command=[tool,'-Q','-T','-s','__rtlrefine/frozen/'+stage+'.ys']
        log=directory/'__rtlrefine'/(stage+'.log');started=time.monotonic();process=None
        record={'stage':stage,'command':command,'status':'ERROR','returncode':None,'execution_mode':'bubblewrap','network':False}
        limit=min(timeout,self.deadline-started)
        try:
            if limit<=0:raise RuntimeError('Property run time budget exhausted')
            argv=[limiter,'--core=0','--as=2147483648','--cpu=60:61','--fsize=16777216','--nofile=128','--',*self.sandbox(command,directory)]
            with log.open('wb') as stream:
                process=subprocess.Popen(argv,cwd=directory,env=self.environment(),stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                record['returncode']=process.wait(timeout=limit)
            record['status']='PASS' if record['returncode']==0 else 'FAIL'
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait();record['status']='TIMEOUT'
        except (OSError,RuntimeError) as exc:log.write_text(str(exc)+'\n')
        record['wall_seconds']=time.monotonic()-started
        write_json(directory/'__rtlrefine'/(stage+'.command.json'),record)
        return record
