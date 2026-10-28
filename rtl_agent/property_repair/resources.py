"""Diagnostic mapped-cell comparison; never a replacement for correctness gates."""
from collections import Counter
from pathlib import Path
import re

from ..common import sha256,write_json
from .runner import PropertyRunner
from .portable import NUMBER,IDENTIFIER


def measure(project,expanded_file,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    result={'status':'UNAVAILABLE','target':'Xilinx 7-series (xc7)','board_executed':False,
            'scope':'Mapped primitive cell estimates with no I/O pads or clock buffer. Not placement/routing, timing, power or a physical resource guarantee.'}
    try:
        top=project.config['dut_top'];params=project.config['dut_parameters']
        if not IDENTIFIER.fullmatch(top) or any(not IDENTIFIER.fullmatch(k) or not NUMBER.fullmatch(v) for k,v in params.items()):raise ValueError('Unsupported synthesis constants')
        frozen=directory/'__rtlrefine/frozen';frozen.mkdir(parents=True)
        data=Path(expanded_file).read_bytes();(frozen/'design.v').write_bytes(data)
        parameter_lines='\n'.join('chparam -set '+k+' '+v+' '+top for k,v in sorted(params.items()))
        script=f'''read_verilog -sv __rtlrefine/frozen/design.v
{parameter_lines}
synth_xilinx -family xc7 -top {top} -flatten -noiopad -noclkbuf
select -module {top}
write_json -selected -noscopeinfo __rtlrefine/mapped.json
'''
        (frozen/'measure_resources.ys').write_text(script)
        runner=PropertyRunner(total_seconds=90)
        ok,why=runner.probe(directory/'isolation')
        if not ok:raise RuntimeError(why)
        command=runner.run('measure_resources',[],directory,timeout=45)
        result.update(command=command,expanded_source_sha256=sha256(data),script_sha256=sha256(script.encode()))
        if command['status']!='PASS':raise ValueError('Synthesis did not complete')
        import json
        mapped=json.loads((directory/'__rtlrefine/mapped.json').read_text())['modules'][top]
        histogram=dict(sorted(Counter(c['type'] for c in mapped['cells'].values()).items()))
        groups={
            'logic_lut_cells':sum(n for kind,n in histogram.items() if re.fullmatch(r'LUT[1-6](?:_2)?',kind)),
            'flip_flop_cells':sum(n for kind,n in histogram.items() if kind.startswith('FD')),
            'lutram_primitive_cells':sum(n for kind,n in histogram.items() if kind.startswith('RAM') and not kind.startswith('RAMB')),
            'srl_primitive_cells':sum(n for kind,n in histogram.items() if kind.startswith('SRL')),
            'bram18_primitive_cells':sum(n for kind,n in histogram.items() if kind.startswith('RAMB18')),
            'bram36_primitive_cells':sum(n for kind,n in histogram.items() if kind.startswith('RAMB36')),
            'dsp_primitive_cells':sum(n for kind,n in histogram.items() if kind.startswith('DSP')),
        }
        result.update(status='PARTIAL_MAPPING' if any(kind.startswith('$') for kind in histogram) else 'MAPPED_ESTIMATE',cells_by_type=histogram,counts=groups)
    except (OSError,ValueError,KeyError,RuntimeError) as exc:result['error']=str(exc)
    write_json(directory/'resources.json',result);return result


def compare(project,original_expanded,selected_expanded,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    before=measure(project,original_expanded,directory/'original');after=measure(project,selected_expanded,directory/'selected')
    result={'status':'AVAILABLE' if before['status']==after['status']=='MAPPED_ESTIMATE' else 'UNAVAILABLE',
            'before':before,'after':after,'affects_correctness_acceptance':False}
    if result['status']=='AVAILABLE':result['delta']={k:after['counts'][k]-v for k,v in before['counts'].items()}
    write_json(directory/'comparison.json',result);return result
