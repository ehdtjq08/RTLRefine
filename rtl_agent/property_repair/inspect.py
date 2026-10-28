"""Inspect the actual elaborated FIFO interface without a model request."""
from pathlib import Path

from ..common import new_run_dir,write_json
from ..project_repair.checker import _flags,_interface
from ..project_repair.runner import ProjectRunner


def inspect_ports(project,output=None):
    root=new_run_dir('fifo_port_inspection',output);private=root/'__rtlrefine';private.mkdir()
    runner=ProjectRunner(total_seconds=45)
    ok,why=runner.probe(root/'isolation')
    if not ok:raise RuntimeError('Native isolation unavailable: '+why)
    for name in project.config['rtl_files']+project.config['include_files']+project.config['data_files']:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(project.files[name])
    config=project.config
    result=runner.run('preprocess',['-g2012','-E','-o','__rtlrefine/design.v',*_flags(project),*['./'+p for p in config['rtl_files']]],root)
    if result['status']!='PASS':raise ValueError('Resolve RTL preprocessing before port inspection')
    params=['-P'+config['dut_top']+'.'+k+'='+v for k,v in config['dut_parameters'].items()]
    result=runner.run('compile',['-g2012','-s',config['dut_top'],'-o','__rtlrefine/interface.vvp',*params,'__rtlrefine/design.v'],root)
    if result['status']!='PASS':raise ValueError('The selected DUT top cannot elaborate independently')
    interface=_interface((private/'interface.vvp').read_text(),config['dut_top'])
    if len(interface)!=1:raise ValueError('Choose a single DUT top before configuring the FIFO contract')
    result={'status':'PASS','project_id':project.identity,'dut_top':config['dut_top'],'ports':interface[0]['ports'],'new_model_calls':0,'directory':str(root)}
    write_json(root/'interface.json',result);return result
