"""An explicit external-port contract, fixed before any repair request."""
import json
import re

from ..common import sha256
from ..project_repair.project import Project, IDENTIFIER
from ..project_repair.policy import tokens

PORTS = {'clk':('INPUT',1), 'rst':('INPUT',1), 's_valid':('INPUT',1),
         's_ready':('OUTPUT',1), 's_data':('INPUT',None), 'm_valid':('OUTPUT',1),
         'm_ready':('INPUT',1), 'm_data':('OUTPUT',None)}
TEXT = ('Single positive-edge clock; synchronous active-high reset flushes the queue. '
        'Transfers occur only with valid && ready outside reset. Output valid exactly '
        'matches nonempty occupancy. Input ready when capacity exists or a simultaneous '
        'output transfer frees space. Accepted payloads leave in FIFO order. '
        'Output remains valid and stable while stalled. No fall-through on an empty queue.')


def load_contract(project, value=None):
    if value is None:
        try: value=json.loads(project.files['fifo_contract.json'])
        except (KeyError,ValueError): raise ValueError('Include fifo_contract.json with the independent FIFO contract') from None
    if not isinstance(value,dict) or set(value)!={'schema_version','kind','ports','data_width','depth','discovery_steps','audit_steps'}:
        raise ValueError('Use the documented FIFO contract fields')
    if value['schema_version']!=1 or value['kind']!='ready_valid_fifo':raise ValueError('Unsupported property contract')
    for key,lo,hi in [('data_width',1,16),('depth',2,8),('discovery_steps',4,24)]:
        if type(value[key]) is not int or not lo<=value[key]<=hi:raise ValueError('Unsupported '+key)
    if not isinstance(value['audit_steps'],list) or not 1<=len(value['audit_steps'])<=2:
        raise ValueError('Declare one or two final audit bounds')
    if any(type(n) is not int or not value['discovery_steps']<n<=40 for n in value['audit_steps']):
        raise ValueError('Audit bounds must exceed discovery and be at most 40')
    mapping=value['ports']
    if not isinstance(mapping,dict) or set(mapping)!=set(PORTS) or any(not isinstance(v,str) or not IDENTIFIER.fullmatch(v) for v in mapping.values()) or len(set(mapping.values()))!=len(PORTS):
        raise ValueError('Map each contract port to a distinct DUT port')
    # These values enter a generated Verilog instance, never a Yosys command.
    for v in project.config['dut_parameters'].values():
        if not re.fullmatch(r"(?:\d+|\d+'[sS]?[bBoOdDhH][0-9a-fA-F_]+)",v):
            raise ValueError('Property mode accepts constant numeric DUT parameters only')
    return json.loads(json.dumps(value))


def bind_contract(project, contract):
    files={**project.files,'fifo_contract.json':(json.dumps(contract,sort_keys=True,indent=2)+'\n').encode()}
    if 'fifo_contract.json' in project.config['editable_files']:raise ValueError('Contract cannot be editable')
    return Project(files,project.config)


def contract_id(contract):return sha256(json.dumps(contract,sort_keys=True).encode())


def validate_formal_source(source):
    ts=tokens(source);values=[t[0] for t in ts]
    banned={'assert','assume','cover','restrict','property','sequence','defparam',
            'anyseq','anyconst','allseq','allconst','blackbox','whitebox','casex','casez','__rtlrefine_property_top'}
    if any(kind=='number' and "'" in word and re.search('[xXzZ?]',word.split("'",1)[1]) for word,_,_,kind in ts):
        raise ValueError('Explicit X/Z/dont-care literals are unsupported in the two-state property contract')
    for word in values:
        if word in banned:raise ValueError('Formal DUT cannot contain property/checker controls: '+word)
        if word.startswith('$') and word not in {'$clog2','$bits','$signed','$unsigned'}:
            raise ValueError('Property-mode DUT must not print or invoke simulator tasks: '+word)
    if re.search(r'\(\*',source):raise ValueError('DUT attributes are not supported in property mode')
