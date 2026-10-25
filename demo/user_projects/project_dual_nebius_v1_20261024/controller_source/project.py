"""Bounded ZIP import and explicit, template-independent verification roles."""
from __future__ import annotations

from dataclasses import dataclass
import io
import json
from pathlib import PurePosixPath
import re
import stat
import zipfile

from ..common import sha256

MAX_ARCHIVE=10*1024*1024
MAX_EXPANDED=32*1024*1024
MAX_FILES=256
MAX_CONTEXT=240000
IDENTIFIER=re.compile(r'[A-Za-z_][A-Za-z0-9_$]*\Z')


def safe_path(name):
    if not isinstance(name,str) or not name or '\\' in name or '\x00' in name or any(ord(c)<32 for c in name):raise ValueError('Use ordinary relative project paths')
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or ':' in path.parts[0]:raise ValueError('Absolute paths and parent traversal are not allowed')
    normalized=str(path)
    if normalized=='.' or path.name=='rtlrefine_check.vh' or path.parts[0].startswith('__rtlrefine'):raise ValueError('Reserved or empty project path')
    if any(p in ('.git','.ssh','.aws') or p.startswith('.env') or p.endswith('.env') for p in path.parts):raise ValueError('Remove credential/environment files from the project ZIP')
    return normalized


def read_archive(data):
    if not isinstance(data,bytes) or not 1<=len(data)<=MAX_ARCHIVE:raise ValueError('Upload a ZIP no larger than 10 MiB')
    files={};total=0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist())>MAX_FILES:raise ValueError('Project has more than 256 entries')
            for info in archive.infolist():
                name=safe_path(info.filename.rstrip('/'))
                if stat.S_ISLNK(info.external_attr>>16):raise ValueError('ZIP symlinks are not allowed')
                if info.is_dir():continue
                if info.flag_bits&1:raise ValueError('Encrypted ZIP entries are not supported')
                if name in files:raise ValueError('Duplicate ZIP path: '+name)
                total+=info.file_size
                if info.file_size>4*1024*1024 or total>MAX_EXPANDED:raise ValueError('Expanded project exceeds file/size limits')
                value=archive.read(info)
                if len(value)!=info.file_size:raise ValueError('Incomplete ZIP entry')
                files[name]=value
    except zipfile.BadZipFile:raise ValueError('The upload is not a valid ZIP') from None
    # Accept the common single enclosing directory produced by GitHub downloads.
    if 'rtlrefine.json' not in files:
        manifests=[p for p in files if p.endswith('/rtlrefine.json')]
        if len(manifests)==1:
            prefix=manifests[0][:-len('rtlrefine.json')]
            if all(p.startswith(prefix) for p in files):files={p[len(prefix):]:v for p,v in files.items()}
    return files


def _paths(value,files,label,*,allow_empty=False):
    if not isinstance(value,list) or (not value and not allow_empty) or any(not isinstance(p,str) for p in value):raise ValueError(label+' must be a file list')
    result=[safe_path(p) for p in value]
    if len(result)!=len(set(result)):raise ValueError('Duplicate '+label)
    for name in result:
        if name not in files:raise ValueError('Missing '+label+' file: '+name)
    return result


def _parameters(value):
    if not isinstance(value,dict) or len(value)>32:raise ValueError('Parameters/defines must be an object with at most 32 entries')
    result={}
    for name,item in value.items():
        if not IDENTIFIER.fullmatch(name) or type(item) not in (str,int):raise ValueError('Invalid parameter/define')
        text=str(item)
        if len(text)>120 or any(c in text for c in '\n\r\x00'):raise ValueError('Invalid parameter/define value')
        result[name]=text
    return result


@dataclass
class Project:
    files:dict[str,bytes]
    config:dict

    @property
    def identity(self):
        value={'config':self.config,'files':{p:sha256(v) for p,v in sorted(self.files.items())}}
        return sha256(json.dumps(value,sort_keys=True).encode())

    @property
    def sources(self):return {p:self.files[p].decode('utf-8') for p in self.config['rtl_files']+self.config['include_files']}

    @property
    def editable(self):return {p:self.files[p].decode('utf-8') for p in self.config['editable_files']}

    @property
    def public_tests(self):return [t for t in self.config['tests'] if t['phase']=='public']

    @property
    def audit_tests(self):return [t for t in self.config['tests'] if t['phase']=='audit']


def load_project(files,config=None):
    if config is None:
        if 'rtlrefine.json' not in files:raise ValueError('Add rtlrefine.json or configure the file roles in the web importer')
        try:config=json.loads(files['rtlrefine.json'])
        except (ValueError,UnicodeError):raise ValueError('rtlrefine.json is not valid UTF-8 JSON') from None
    if not isinstance(config,dict) or config.get('schema_version')!=1:raise ValueError('Use project schema_version 1')
    if not isinstance(config.get('name'),str) or not 1<=len(config['name'])<=100:raise ValueError('Set a project name')
    top=config.get('dut_top','')
    if not IDENTIFIER.fullmatch(top):raise ValueError('Set a valid DUT top module')
    rtl=_paths(config.get('rtl_files'),files,'RTL')
    includes=_paths(config.get('include_files',[]),files,'include',allow_empty=True)
    editable=_paths(config.get('editable_files',rtl),files,'editable')
    if not set(editable)<=set(rtl+includes) or len(editable)>12:raise ValueError('Choose at most 12 editable design files')
    if any(PurePosixPath(p).suffix not in ('.v','.sv','.vh','.svh') for p in rtl+includes):raise ValueError('Design sources must be Verilog/SystemVerilog files')
    dirs=config.get('include_dirs',[])
    if not isinstance(dirs,list):raise ValueError('include_dirs must be a list')
    dirs=[str(PurePosixPath(p)) if p=='.' else safe_path(p) for p in dirs]
    data=_paths(config.get('data_files',[]),files,'design data',allow_empty=True)
    tests=[];names=set()
    for item in config.get('tests',[]):
        name=item.get('id','');test_top=item.get('top','')
        if not IDENTIFIER.fullmatch(name) or name in names or not IDENTIFIER.fullmatch(test_top):raise ValueError('Tests need unique identifiers and valid top names')
        names.add(name);phase=item.get('phase','public')
        if phase not in ('public','audit'):raise ValueError('Test phase must be public or audit')
        test_files=_paths(item.get('files'),files,'testbench')
        extra=_paths(item.get('data_files',[]),files,'test data',allow_empty=True)
        if set(test_files)&set(rtl+includes+editable):raise ValueError('Testbench and design roles cannot overlap')
        timeout=item.get('timeout_seconds',10)
        if type(timeout) not in (int,float) or not .1<=timeout<=30:raise ValueError('Test timeout must be 0.1–30 seconds')
        checks=item.get('minimum_checks',1)
        if type(checks) is not int or not 1<=checks<=100000000:raise ValueError('minimum_checks must be a positive count')
        text='\n'.join(files[p].decode('utf-8') for p in test_files)
        marker=item.get('success_marker')
        if marker is not None:
            if not isinstance(marker,str) or not 1<=len(marker)<=100 or any(c in marker for c in '\n\r"\\%'):raise ValueError('Use a plain literal success marker')
            pattern=r'\$(?:display|write)\s*\(\s*"'+re.escape(marker)+r'"\s*\)'
            if not re.search(pattern,text):raise ValueError('Success marker must be a literal $display/$write call in the readonly testbench')
        elif 'RTLREFINE_DONE' not in text:raise ValueError('Test '+name+' needs success_marker or `RTLREFINE_DONE(check_count)')
        tests.append({'id':name,'top':test_top,'phase':phase,'files':test_files,'data_files':extra,'timeout_seconds':float(timeout),
            'minimum_checks':checks,'parameters':_parameters(item.get('parameters',{})),'success_marker':marker})
    if not 1<=len(tests)<=8 or not any(t['phase']=='public' for t in tests):raise ValueError('Provide 1–8 tests, including a public discovery test')
    if set(rtl+includes+data)&{p for t in tests for p in t['files']+t['data_files']}:raise ValueError('Design and test-only file roles cannot overlap')
    declared=set(rtl+includes+data)
    for test in tests:declared.update(test['files']+test['data_files'])
    # Preserve licenses, documentation and undeclared assets for round-trip
    # export. Only declared roles are ever copied to simulation or model input.
    clean=dict(files)
    for p in rtl+includes:
        try:clean[p].decode('utf-8')
        except UnicodeDecodeError:raise ValueError('RTL must be UTF-8: '+p) from None
    if sum(len(clean[p]) for p in editable)>MAX_CONTEXT:raise ValueError('Editable context exceeds 240 KB; narrow editable files')
    normalized={'schema_version':1,'name':config['name'],'dut_top':top,'rtl_files':rtl,'include_files':includes,'editable_files':editable,
        'include_dirs':dirs,'data_files':data,'defines':_parameters(config.get('defines',{})),
        'dut_parameters':_parameters(config.get('dut_parameters',{})),'tests':tests,
        'contract':str(config.get('contract','Follow the provided self-checking testbenches.'))[:4000]}
    return Project(clean,normalized)


def archive_project(project,overrides=None):
    content={**project.files,**{p:v.encode() for p,v in (overrides or {}).items()}}
    content['rtlrefine.json']=(json.dumps(project.config,indent=2)+'\n').encode();buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,value in sorted(content.items()):archive.writestr(name,value)
    return buffer.getvalue()
