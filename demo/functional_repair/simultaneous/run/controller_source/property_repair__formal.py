"""Compile an immutable external-port monitor and replay SAT witnesses in Icarus."""
import json
from pathlib import Path
import re

from ..common import sha256,write_json
from ..project_repair.checker import _flags,_interface
from ..project_repair.policy import validate_design,validate_patch
from .contract import PORTS,TEXT,contract_id,validate_formal_source
from .runner import PropertyRunner

INPUTS=('rst','s_valid','s_data','m_ready')
OUTPUTS=('s_ready','m_valid','m_data','expected_count','property_valid','property_ready','property_payload','property_stable','property_capacity','cover_progress','watch_this')


def instance(project,contract):
    params=','.join('.'+k+'('+v+')' for k,v in project.config['dut_parameters'].items())
    return project.config['dut_top']+(' #('+params+')' if params else '')+' dut('+','.join('.'+v+'('+k+')' for k,v in contract['ports'].items())+');'


def monitor(project,c):
    return '''module __rtlrefine_property_top(input clk,rst,s_valid,m_ready,watch_this,
input [WIDTH-1:0] s_data,output s_ready,m_valid,output [WIDTH-1:0] m_data,
output [31:0] expected_count,
output property_valid,property_ready,property_payload,property_stable,property_capacity,cover_progress);
localparam WIDTH='''+str(c['data_width'])+''', DEPTH='''+str(c['depth'])+''';
'''+instance(project,c)+'''
// Universally quantified transaction tracking, independent of circular pointers.
localparam CW=$clog2(DEPTH+2);
reg [CW-1:0] occupancy=0;
wire push=!rst && s_valid && s_ready;
wire pop=!rst && m_valid && m_ready;
always @(posedge clk) begin
    if(rst) occupancy<=0;
    else begin
        case({push,pop})
            2'b10:occupancy<=occupancy+1;
            2'b01:occupancy<=occupancy-1;
            default:occupancy<=occupancy;
        endcase
    end
end
reg tracking=0,seen_watched_pop=0;
reg [CW-1:0] position=0;
reg [WIDTH-1:0] watched_data=0;
always @(posedge clk) begin
    if(rst) begin tracking<=0;position<=0;watched_data<=0;end
    else if(!tracking) begin
        if(push && watch_this) begin
            tracking<=1;position<=occupancy-(pop ? 1 : 0);watched_data<=s_data;
        end
    end else if(pop) begin
        if(position==0) begin tracking<=0;seen_watched_pop<=1;end
        else position<=position-1;
    end
end
reg past_valid=0,was_stalled=0;
reg [WIDTH-1:0] previous_data=0;
always @(posedge clk) begin
    past_valid<=1;
    was_stalled<=!rst && m_valid && !m_ready;
    previous_data<=m_data;
end
always @* if(!past_valid) assume(rst);
assign expected_count=occupancy;
assign property_valid=(m_valid==(!rst && occupancy!=0));
assign property_ready=(s_ready==(!rst && ((occupancy<DEPTH) || (occupancy!=0 && m_ready))));
assign property_payload=rst || !tracking || position!=0 || (m_data==watched_data);
assign property_stable=rst || !was_stalled || (m_valid && m_data==previous_data);
assign property_capacity=(occupancy<=DEPTH);
always @* begin
    assert(property_valid);assert(property_ready);assert(property_payload);
    assert(property_stable);assert(property_capacity);
end
reg seen_push=0,seen_pop=0,seen_full=0,seen_overlap=0,seen_stall=0,seen_reset=0,seen_wrap=0;
reg [CW-1:0] window_pops=0;
always @(posedge clk) begin
    if(push) seen_push<=1;
    if(rst) window_pops<=0;
    else if(pop) begin
        seen_pop<=1;
        if(window_pops<DEPTH) window_pops<=window_pops+1;
        if(window_pops==DEPTH-1) seen_wrap<=1;
    end
    if(!rst && occupancy==DEPTH) seen_full<=1;
    if(push && pop) seen_overlap<=1;
    if(!rst && m_valid && !m_ready) seen_stall<=1;
    if(rst && seen_push) seen_reset<=1;
end
assign cover_progress=seen_push && seen_pop && seen_full && seen_overlap && seen_stall && seen_reset && seen_watched_pop && seen_wrap;
endmodule
'''


def _write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data if isinstance(data,bytes) else data.encode())


def prepare(project,changes,c,directory,runner):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    frozen=directory/'__rtlrefine/frozen';frozen.mkdir(parents=True)
    if changes:validate_patch(project,changes)
    ok,why=runner.probe(directory/'isolation')
    if not ok:raise RuntimeError('Native isolation unavailable: '+why)
    for name in project.config['rtl_files']+project.config['include_files']+project.config['data_files']:
        _write(directory/name,changes[name].encode() if name in changes else project.files[name])
    flags=_flags(project)
    command=runner.run('preprocess',['-g2012','-E','-o','__rtlrefine/expanded.v',*flags,*['./'+p for p in project.config['rtl_files']]],directory)
    if command['status']!='PASS':raise ValueError('DUT preprocessing failed before property checking')
    expanded=(directory/'__rtlrefine/expanded.v').read_text()
    validate_design(expanded,test_tops=[t['top'] for t in project.config['tests']],data_files=project.config['data_files'])
    validate_formal_source(expanded)
    params=['-P'+project.config['dut_top']+'.'+k+'='+v for k,v in project.config['dut_parameters'].items()]
    command=runner.run('compile',['-g2012','-s',project.config['dut_top'],'-o','__rtlrefine/dut.vvp',*params,'./__rtlrefine/expanded.v'],directory)
    if command['status']!='PASS':raise ValueError('DUT cannot elaborate independently')
    interface=_interface((directory/'__rtlrefine/dut.vvp').read_text(),project.config['dut_top'])
    if len(interface)!=1:raise ValueError('Property mode needs exactly one standalone DUT top')
    actual={p['name']:(p['direction'],p['width']) for p in interface[0]['ports']}
    expected={c['ports'][p]:(direction,width or c['data_width']) for p,(direction,width) in PORTS.items()}
    if actual!=expected:raise ValueError('FIFO port directions/widths do not match the declared contract')
    _write(frozen/'design.v',expanded);_write(frozen/'properties.v',monitor(project,c))
    script='''read_verilog -sv __rtlrefine/frozen/design.v
read_verilog -formal -sv __rtlrefine/frozen/properties.v
hierarchy -check -top __rtlrefine_property_top
proc
flatten
wreduce
memory_map
opt
chformal -lower
check -assert
write_rtlil __rtlrefine/prepared.il
write_json __rtlrefine/prepared.json
'''
    _write(frozen/'prepare_properties.ys',script)
    command=runner.run('prepare_properties',[],directory)
    if command['status']!='PASS':raise ValueError('Yosys cannot prepare this DUT: '+(directory/'__rtlrefine/prepare_properties.log').read_text(errors='replace')[-1200:])
    netlist=json.loads((directory/'__rtlrefine/prepared.json').read_text())['modules']['__rtlrefine_property_top']
    clock=netlist['ports']['clk']['bits']
    for cell in netlist['cells'].values():
        kind=cell['type']
        if any(word in kind.lower() for word in ('dff','latch')) or kind=='$ff':
            if kind not in {'$dff','$dffe','$sdff','$sdffe','$sdffce'} or cell['connections'].get('CLK')!=clock or int(cell['parameters'].get('CLK_POLARITY','0'),2)!=1:
                raise ValueError('Property mode supports a single positive-edge clock and synchronous reset only')
    il=(directory/'__rtlrefine/prepared.il').read_bytes()
    if len(re.findall(rb'cell \$assert ',il))!=5 or len(re.findall(rb'cell \$assume ',il))!=1:
        raise ValueError('Prepared design has unexpected property/assumption cells')
    _write(frozen/'prepared.il',il)
    return {'interface':interface,'monitor_sha256':sha256((frozen/'properties.v').read_bytes()),'prepared_sha256':sha256(il)}


def solve(directory,runner,steps,*,cover=False):
    # Each solve has a fresh process and files, and reads the same readonly IL.
    directory=Path(directory);out=directory/'__rtlrefine'
    for name in ('counterexample.json','counterexample.vcd'):
        if (out/name).exists():(out/name).unlink()
    target='-prove cover_progress 0' if cover else '-prove-asserts'
    solver_seconds=45 if steps>=20 else 25
    script=f'''read_rtlil __rtlrefine/frozen/prepared.il
sat -seq {steps} -set-assumes {target} -set-init-zero -set-def-inputs -timeout {solver_seconds} -show-ports -dump_json __rtlrefine/counterexample.json -dump_vcd __rtlrefine/counterexample.vcd
'''
    _write(out/'frozen/solve_properties.ys',script)
    frozen={p:sha256(p.read_bytes()) for p in (out/'frozen').iterdir() if p.is_file()}
    command=runner.run('solve_properties',[],directory,timeout=solver_seconds+8)
    log=(out/'solve_properties.log').read_text(errors='replace')
    for path,value in frozen.items():
        if sha256(path.read_bytes())!=value:raise ValueError('Immutable property input changed')
    no_model=command['status']=='PASS' and '\nSAT proof finished - no model found: SUCCESS!' in log
    model=command['status']=='PASS' and '\nSAT proof finished - model found: FAIL!' in log and (out/'counterexample.json').exists()
    status=('REACHABLE' if model else 'UNREACHABLE' if no_model else 'UNPROVEN') if cover else ('BOUNDED_PASS' if no_model else 'COUNTEREXAMPLE' if model else 'UNPROVEN')
    record={'status':status,'steps':steps,'command':command,'script_sha256':sha256(script.encode()),'cover_query':cover}
    name=('cover_' if cover else 'bound_')+str(steps)
    for artifact in ['solve_properties.log','counterexample.json','counterexample.vcd']:
        path=out/artifact
        if path.exists():_write(out/(name+'_'+artifact),path.read_bytes())
    write_json(out/(name+'.json'),record)
    return record


def decode_signal(signal):
    values=iter(signal.get('data',[]));result=[];current=None
    for symbol in signal['wave']:
        if symbol=='.':pass
        elif symbol=='=':
            word=next(values);current=int(word,2) if word and set(word)<={'0','1'} else None
        elif symbol in '01':current=int(symbol)
        elif symbol=='4':
            if signal.get('data'):next(values)
            current=None
        else:raise ValueError('Unsupported witness symbol')
        result.append(current)
    return result


def witness(directory,steps):
    signals={}
    for line in (Path(directory)/'__rtlrefine/counterexample.json').read_text().splitlines():
        match=re.search(r'"name"\s*:\s*"([^"\\]+)"',line)
        if match and match[1] in INPUTS+OUTPUTS:signals[match[1]]=decode_signal(json.loads(line.strip().rstrip(',')))
    if set(INPUTS+OUTPUTS)-set(signals) or any(len(values)!=steps+1 for values in signals.values()):
        raise ValueError('Incomplete external-port SAT witness')
    rows=[{k:values[i] for k,values in signals.items()} for i in range(1,steps+1)]
    if any(row[k] is None for row in rows for k in INPUTS):raise ValueError('Undefined witness input')
    return rows


def replay(project,changes,c,rows,directory,runner):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);(directory/'__rtlrefine/frozen').mkdir(parents=True)
    # The expanded, validated DUT is copied without the formal monitor.
    for name in project.config['rtl_files']+project.config['include_files']+project.config['data_files']:
        _write(directory/name,changes[name].encode() if name in changes else project.files[name])
    statements=[]
    for i,row in enumerate(rows):
        statements.append('step('+','.join(map(str,[i,*[row[k] for k in INPUTS]]))+');')
    width=c['data_width']
    bench=f'''module __rtlrefine_replay_tb;
reg clk=0,rst=0,s_valid=0,m_ready=0;
reg [{width-1}:0] s_data=0;
wire s_ready,m_valid;wire [{width-1}:0] m_data;
{instance(project,c)}
task step;
input integer cycle,reset_value,valid_value,data_value,ready_value;
begin
    clk=0;rst=reset_value;s_valid=valid_value;s_data=data_value;m_ready=ready_value;
    #2;$display("FIFO_OBS %0d %b %b %b",cycle,s_ready,m_valid,m_data);
    clk=1;#1;clk=0;#1;
end
endtask
initial begin
'''+ '\n'.join(statements)+'\n$finish;end\nendmodule\n'
    _write(directory/'__rtlrefine/frozen/replay_tb.v',bench)
    flags=_flags(project)
    commands=[runner.run('compile',['-g2012','-s','__rtlrefine_replay_tb','-o','__rtlrefine/replay.vvp',*flags,*['./'+p for p in project.config['rtl_files']],'__rtlrefine/frozen/replay_tb.v'],directory)]
    if commands[-1]['status']=='PASS':commands.append(runner.run('simulate',['__rtlrefine/replay.vvp'],directory))
    observations=[];violations=[];queue=[];previous=None
    if len(commands)==2 and commands[-1]['status']=='PASS':
        raw=re.findall(r'^FIFO_OBS (\d+) ([01xz]+) ([01xz]+) ([01xz]+)$',(directory/'__rtlrefine/simulate.log').read_text(),re.M)
        if len(raw)!=len(rows) or [int(t[0]) for t in raw]!=list(range(len(rows))):raise ValueError('Incomplete independent replay')
        for given,(_,ready,valid,data) in zip(rows,raw):
            ready=int(ready,2) if set(ready)<={'0','1'} else None
            valid=int(valid,2) if set(valid)<={'0','1'} else None
            data=int(data,2) if set(data)<={'0','1'} else None
            if given['rst']:queue=[]
            count=len(queue);want_valid=int(not given['rst'] and count>0)
            want_ready=int(not given['rst'] and (count<c['depth'] or (count>0 and given['m_ready'])))
            errors=[]
            if valid!=want_valid:errors.append('valid_matches_occupancy')
            if ready!=want_ready:errors.append('ready_matches_capacity')
            if not given['rst'] and count and data!=queue[0]:errors.append('payload_order')
            if previous and previous['m_valid']==1 and previous['m_ready']==0 and not previous['rst'] and not given['rst']:
                if valid!=1 or data!=previous['m_data']:errors.append('stable_while_stalled')
            if count>c['depth']:errors.append('capacity')
            observation={**{k:given[k] for k in INPUTS},'cycle':len(observations),'s_ready':ready,'m_valid':valid,'m_data':data,
                         'expected_count':count,'expected_data':queue[0] if queue else None,'violations':errors}
            observations.append(observation)
            if errors:violations.append(observation)
            if not given['rst']:
                if valid==1 and given['m_ready'] and queue:queue.pop(0)
                if ready==1 and given['s_valid']:queue.append(given['s_data'])
            previous=observation
    result={'status':'FAILURE_REPRODUCED' if violations else 'NOT_REPRODUCED','observations':observations,'violations':violations,'commands':commands,
            'oracle':'Independent Python transaction queue and four-state Icarus; no corrected RTL'}
    write_json(directory/'replay.json',result);return result


def check_properties(project,changes,c,directory,*,steps=None,minimize=False,require_progress=False,runner=None):
    runner=runner or PropertyRunner(total_seconds=240);directory=Path(directory)
    steps=steps or c['discovery_steps']
    setup=prepare(project,changes,c,directory,runner)
    queries=[];minimal_confirmed=False
    record=solve(directory,runner,steps)
    queries.append(record)
    if minimize and record['status']=='COUNTEREXAMPLE':
        lo,hi=1,steps
        while lo<hi:
            mid=(lo+hi)//2;query=solve(directory,runner,mid);queries.append(query)
            if query['status']=='COUNTEREXAMPLE':hi=mid
            elif query['status']=='BOUNDED_PASS':lo=mid+1
            else:break
        record=solve(directory,runner,hi);queries.append(record)
        minimal_confirmed=lo==hi and all(q['status'] in {'COUNTEREXAMPLE','BOUNDED_PASS'} for q in queries)
    result={'status':record['status'],'steps':record['steps'],'minimal_counterexample_confirmed':minimal_confirmed,'queries':queries,'contract_id':contract_id(c),'contract':TEXT,**setup,
            'design_hashes':{p:sha256(changes.get(p,project.files[p].decode()).encode()) for p in project.sources},
            'scope':'Bounded two-state synchronous positive-edge FIFO contract; reset at first step; arbitrary defined external inputs; zero initial state. Not unbounded correctness or physical CDC.',
            'fixed_corrected_rtl_used':False,'new_model_calls':0}
    if record['status']=='COUNTEREXAMPLE':
        rows=witness(directory,record['steps']);result['witness']=rows
        result['replay']=replay(project,changes,c,rows,directory/'replay',runner)
        if result['replay']['status']!='FAILURE_REPRODUCED':result['status']='UNREPRODUCED_COUNTEREXAMPLE'
    if require_progress and result['status']=='BOUNDED_PASS':
        result['progress']=solve(directory,runner,steps,cover=True)
        if result['progress']['status']!='REACHABLE':result['status']='PROGRESS_NOT_REACHED'
    write_json(directory/'properties.json',result);return result
