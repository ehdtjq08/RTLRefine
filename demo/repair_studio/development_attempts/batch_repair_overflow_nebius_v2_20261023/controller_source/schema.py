"""Runtime patch selectors for non-overlapping procedural/expression edits.

Instrumentation is only a screening aid. The exact uninstrumented candidate
must pass the existing independent checker before it can be accepted.
"""
from collections import defaultdict
import re

from ..common import sha256
from ..repair_search.candidates import closing,end_block
from ..repair_search.retention import comment_blanked

SELECTOR='rtlrefine_patch_select'


def header(source,module):
    clean=comment_blanked(source)
    m=re.search(r'\bmodule\s+'+re.escape(module)+r'\b',clean)
    if not m:raise ValueError('Top module not found for selector instrumentation')
    point=m.end()
    while clean[point].isspace():point+=1
    if clean[point]=='#':
        point=clean.index('(',point);point=closing(clean,point)+1
        while clean[point].isspace():point+=1
    if clean[point]!='(':raise ValueError('Unsupported module header')
    end=closing(clean,point)
    return point,end,bool(re.search(r'\b(?:input|output|inout)\b',clean[point:end]))


def add_selector(source,module):
    first,last,ansi=header(source,module)
    if ansi:return source[:last]+', input wire [7:0] '+SELECTOR+source[last:]
    after=source.index(';',last)+1
    return source[:last]+', '+SELECTOR+source[last:after]+'\ninput wire [7:0] '+SELECTOR+';\n'+source[after:]


def supported_ranges(source):
    clean=comment_blanked(source);procedural=[];assignments=[]
    for event in re.finditer(r'\balways\s*@\s*(?:\([^)]*\)|\*)\s*begin\b',clean):
        begin=clean.rfind('begin',event.start(),event.end());end,_=end_block(clean,begin)
        procedural.append((event.end(),end))
    for match in re.finditer(r'\bassign\s+[^;]*?=(?!=)([^;]+);',clean):assignments.append((match.start(1),match.end(1)))
    return procedural,assignments


def partition(source,pool):
    procedural,assignments=supported_ranges(source);supported=[];fallback=[]
    for item in pool:
        reason=None
        if item['family']=='ack_pipeline':reason='Whole process replacement needs a standalone build'
        for edit in item['edits']:
            a,b=edit['start'],edit['end']
            if source[a:b]!=edit['old']:raise ValueError('Candidate span mismatch')
            if not any(x<=a and b<=y for x,y in procedural+assignments):reason='Constant elaboration or unsupported statement context'
            if a!=b and re.search(r'\b(?:always|initial|reg|wire)\b|;',edit['replacement']):reason='Non-expression replacement'
            if a==b and not any(x<=a<=y for x,y in procedural):reason='Insertion outside procedural block'
        (fallback if reason else supported).append({**item,'batch_fallback_reason':reason} if reason else item)
    return supported,fallback


def instrument(source,dependencies,case,pool):
    if re.search(r'\b'+SELECTOR+r'\b',source+dependencies):raise ValueError('Selector name collision')
    if not 1<=len(pool)<=128:raise ValueError('Use one to 128 candidates')
    sites=defaultdict(lambda:defaultdict(list));mapping={}
    for index,item in enumerate(pool,1):
        if sha256(item['rtl'].encode())!=item['rtl_sha256']:raise ValueError('Candidate hash mismatch')
        rebuilt=source
        for edit in sorted(item['edits'],key=lambda e:e['start'],reverse=True):
            a,b=edit['start'],edit['end']
            if source[a:b]!=edit['old']:raise ValueError('Candidate edit mismatch')
            rebuilt=rebuilt[:a]+edit['replacement']+rebuilt[b:]
            sites[(a,b)][edit['replacement']].append(index)
        if rebuilt!=item['rtl']:raise ValueError('Edit reconstruction mismatch')
        mapping[item['id']]=index
    intervals=sorted(sites)
    if any(a[1]>b[0] for a,b in zip(intervals,intervals[1:])):raise ValueError('Overlapping edit sites require separate batches')
    signal=SELECTOR if case['top']==case['edited_module'] else case['top']+'.'+SELECTOR
    result=source
    for (a,b),choices in sorted(sites.items(),reverse=True):
        if a==b:
            text='\ncase ('+signal+')\n'
            for replacement,selectors in choices.items():
                text+=', '.join(str(i) for i in selectors)+': begin\n'+replacement+'\nend\n'
            text+='default: begin end\nendcase\n'
        else:
            text='('+source[a:b]+')'
            for replacement,selectors in reversed(list(choices.items())):
                condition=' || '.join(signal+' == '+str(i) for i in selectors)
                text='(('+condition+') ? ('+replacement+') : '+text+')'
        result=result[:a]+text+result[b:]
    if case['top']==case['edited_module']:result=add_selector(result,case['top'])
    else:dependencies=add_selector(dependencies,case['top'])
    return result,dependencies,mapping
