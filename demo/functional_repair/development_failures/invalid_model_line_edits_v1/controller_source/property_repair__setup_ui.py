"""Configure an uploaded FIFO from real elaborated ports, with no JSON required."""
import json

import streamlit as st

from ..common import sha256
from .inspect import inspect_ports
from .contract import TEXT,load_contract
from workspace_service import execution_slot

HINTS={'clk':['clk','clock','i_clk','clk_i'],'rst':['rst','reset','i_reset','rst_i'],
       's_valid':['s_valid','s_axis_tvalid','in_valid'],'s_ready':['s_ready','s_axis_tready','in_ready'],
       's_data':['s_data','s_axis_tdata','in_data'],'m_valid':['m_valid','m_axis_tvalid','out_valid'],
       'm_ready':['m_ready','m_axis_tready','out_ready'],'m_data':['m_data','m_axis_tdata','out_data']}


def configure_contract(project):
    key='fifo_setup_'+project.identity[:16]
    st.markdown('**Configure the independent FIFO contract**')
    st.caption('Inspect ports without a model request, then map the interface and confirm the capacity. This contract requires a positive-edge clock, synchronous active-high reset and same-cycle replacement at full capacity.')
    if st.button('Inspect FIFO ports without NVIDIA',key=key+'inspect'):
        try:
            with st.spinner('Elaborating the DUT interface…'):
                with execution_slot():result=inspect_ports(project)
            st.session_state[key+'interface']=result
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    interface=st.session_state.get(key+'interface')
    if not interface:st.info('Inspect the current source before mapping the contract ports.');return None
    ports=interface['ports']
    st.dataframe([{'Port':p['name'],'Direction':p['direction'],'Width':p['width']} for p in ports],hide_index=True)
    if len(ports)!=8:st.error('This contract needs exactly eight external ports. Use a wrapper for additional I/O or the general project route for other protocols.');return None
    selected={};used=set();by_name={p['name']:p for p in ports}
    for name in ('clk','rst','s_valid','m_ready','s_ready','m_valid','s_data','m_data'):
        direction='INPUT' if name in ('clk','rst','s_valid','m_ready','s_data') else 'OUTPUT'
        candidates=[p for p in ports if p['direction']==direction and p['name'] not in used and (p['width']==1 if name not in ('s_data','m_data') else 1<=p['width']<=16)]
        if not candidates:st.error('No compatible port remains for '+name+'. Review the earlier selections.');return None
        options=[p['name'] for p in candidates]
        default=next((p for p in HINTS[name] if p in options),max(candidates,key=lambda p:p['width'])['name'] if name in ('s_data','m_data') else options[0])
        option_id=sha256(json.dumps(options).encode())[:8]
        selected[name]=st.selectbox('Contract port: '+name,options,index=options.index(default),key=key+name+option_id);used.add(selected[name])
    width=by_name[selected['s_data']]['width']
    if width!=by_name[selected['m_data']]['width']:st.error('Input and output payload widths must match.');return None
    raw=project.config['dut_parameters'].get('DEPTH','4');default_depth=int(raw) if raw.isdecimal() and 2<=int(raw)<=8 else 4
    depth=st.number_input('FIFO capacity in entries',min_value=2,max_value=8,value=default_depth,key=key+'capacity')
    config={'schema_version':1,'kind':'ready_valid_fifo','ports':selected,'data_width':width,'depth':int(depth),'discovery_steps':12,'audit_steps':[16,20]}
    with st.expander('Contract semantics and optional JSON override'):
        st.write(TEXT);st.json(config)
        override=st.text_area('Optional contract JSON override',value='',key=key+'override')
        if override:config=json.loads(override)
    return load_contract(project,config)
