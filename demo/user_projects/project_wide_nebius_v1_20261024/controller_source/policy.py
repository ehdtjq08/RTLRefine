"""Synthesis-oriented project edits, with immutable public interfaces and tests."""
from __future__ import annotations

import re

TOKEN=re.compile(r'(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<string>"(?:\\.|[^"\\])*")|(?P<escaped>\\[^\s]+)|(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<number>(?:\d+)?\x27[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|\x27[01xXzZ]|\d+(?:\.\d+)?)|(?P<symbol>::|\*\*|<=|>=|==|!=|&&|\|\||.)')
PURE={'$clog2','$bits','$signed','$unsigned','$size','$left','$right','$low','$high','$increment','$dimensions','$unpacked_dimensions','$typename','$countones','$onehot','$onehot0','$isunknown','$fatal','$error'}
FORBIDDEN={'force','release','bind','export','specify','fork','join','join_any','join_none','class','program','checker'}


def tokens(source):
    return [(m.group(),m.start(),m.end(),m.lastgroup) for m in TOKEN.finditer(source) if m.lastgroup not in ('space','comment')]


def _balanced(values,start):
    depth=0
    for index in range(start,len(values)):
        if values[index]=='(':depth+=1
        elif values[index]==')':
            depth-=1
            if depth==0:return index
    raise ValueError('Unbalanced module/event syntax')


def interfaces(source):
    ts=tokens(source);v=[x[0] for x in ts];headers=[];decl=[];events=[]
    for i,word in enumerate(v):
        if word in ('module','package','interface'):
            j=i+1;depth=0
            while j<len(v):
                if v[j]=='(':depth+=1
                elif v[j]==')':depth-=1
                if v[j]==';' and depth==0:break
                j+=1
            headers.append(tuple(v[i:j+1]))
        if word in ('input','output','inout','parameter','typedef'):
            j=i+1
            while j<len(v) and v[j] not in (';',):j+=1
            decl.append(tuple(v[i:j]))
        if word=='@' and i+1<len(v):
            j=_balanced(v,i+1) if v[i+1]=='(' else i+1
            events.append(tuple(v[i:j+1]))
    return headers,decl,set(events)


def validate_design(source,*,test_tops=(),data_files=()):
    ts=tokens(source);v=[x[0] for x in ts]
    for i,token in enumerate(ts):
        word,_,_,kind=token
        if kind in ('string','escaped','number'):continue
        if word in FORBIDDEN:raise ValueError('Unsupported synthesizable-DUT construct: '+word)
        if word in ('$root','$unit'):raise ValueError('DUT cannot access verification scope')
        if word in test_tops:raise ValueError('DUT cannot name a testbench scope')
        if word.startswith('$'):
            if word in ('$readmemh','$readmemb'):
                if i+2>=len(ts) or v[i+1]!='(' or ts[i+2][3]!='string':raise ValueError('Memory initialization needs a literal declared data path')
                path=v[i+2][1:-1]
                if path not in data_files:raise ValueError('Memory initialization may read only declared design data')
            elif word not in PURE:raise ValueError('Unsupported DUT runtime/checker task: '+word)
        if word=='.' and i and i+1<len(ts) and ts[i-1][3] in ('id','escaped') and ts[i+1][3] in ('id','escaped'):
            raise ValueError('Cross-hierarchy/member references are not yet supported in editable DUT code')
        if word=='import' and i+1<len(ts) and ts[i+1][3]=='string':raise ValueError('No foreign-function/DPI imports')
        if word=='#':
            # Parameterized module instances are permitted; timing controls are not.
            if i+1>=len(v) or v[i+1]!='(':raise ValueError('DUT timing delays are unsupported')
            end=_balanced(v,i+1)
            if end+2>=len(ts) or ts[end+1][3] not in ('id','escaped') or v[end+2]!='(':
                # A module parameter header is protected separately.
                if not any(x[0]=='module' for x in ts[max(0,i-4):i]):raise ValueError('DUT timing delays are unsupported')
    return source


def validate_patch(project,changes):
    if not changes or set(changes)-set(project.config['editable_files']):raise ValueError('Only declared editable design files may change')
    for path,new in changes.items():
        if not isinstance(new,str) or len(new.encode())>4*1024*1024:raise ValueError('Invalid edited source size')
        old=project.files[path].decode();old_sig=interfaces(old);new_sig=interfaces(new)
        if old_sig[:2]!=new_sig[:2] or not new_sig[2]<=old_sig[2]:raise ValueError('Preserve module interfaces, configuration, type declarations and clock/reset event forms')
        first=next((t[1] for t in tokens(old) if t[0] in ('module','package','interface')),0)
        if new[:first]!=old[:first]:raise ValueError('Preserve original license/header prefix')
        if re.findall(r'^\s*`[^\n]+',new,re.M)!=re.findall(r'^\s*`[^\n]+',old,re.M):raise ValueError('Compiler directives are read-only')
    return changes


def apply_edits(project,proposal):
    if not isinstance(proposal,dict) or set(proposal)!={'diagnosis','edits'} or not isinstance(proposal['diagnosis'],str) or not isinstance(proposal['edits'],list) or not 1<=len(proposal['edits'])<=12:raise ValueError('Invalid multi-file patch schema')
    grouped={}
    for edit in proposal['edits']:
        if not isinstance(edit,dict) or set(edit)!={'file','start_line','end_line','replacement'} or edit['file'] not in project.config['editable_files']:raise ValueError('Unknown or read-only patch file')
        lines=project.files[edit['file']].decode().splitlines(keepends=True)
        a,b=edit['start_line'],edit['end_line'];text=edit['replacement']
        if type(a) is not int or type(b) is not int or not 1<=a<=b<=len(lines) or not isinstance(text,str) or len(text.encode())>24000:raise ValueError('Invalid line edit range/replacement')
        grouped.setdefault(edit['file'],[]).append((a,b,text))
    result={}
    for path,edits in grouped.items():
        edits.sort()
        if any(a[1]>=b[0] for a,b in zip(edits,edits[1:])):raise ValueError('Patch edits overlap')
        lines=project.files[path].decode().splitlines(keepends=True)
        for a,b,text in reversed(edits):lines[a-1:b]=[text+'\n' if text and not text.endswith('\n') else text]
        result[path]=''.join(lines)
    return validate_patch(project,result)
