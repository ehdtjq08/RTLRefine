import json

from rtl_agent.project_repair import agent
from rtl_agent.project_repair.examples import example_files
from rtl_agent.project_repair.project import load_project


def test_revision_ends_with_latest_failure_and_labels_previous_hypothesis():
    files=example_files()
    files['tests/audit.sv']+=b'\n// PRIVATE_REVISION_AUDIT_94\n'
    project=load_project(files)
    latest={'status':'PROVIDED_TESTS_NOT_PASSED','tests':[{'id':'public','log_tail':'LATEST_RUNTIME_FAILURE_73'}]}
    messages=agent.public_messages(project,latest,previous={'diagnosis':'OLD_REJECTED_HYPOTHESIS','edits':[]})
    context=json.loads(messages[-1]['content'])
    assert list(context)[-1]=='public_observations'
    assert context['public_observations']==latest
    assert 'Rejected' in context['previous_proposal_status']
    assert 'PRIVATE_REVISION_AUDIT_94' not in json.dumps(messages)


def test_known_failed_proposal_enables_reasoning_without_extra_requests(tmp_path,monkeypatch):
    project=load_project(example_files());flags=[]
    path='rtl/word_math.sv';line=next(i+1 for i,t in enumerate(project.files[path].decode().splitlines()) if 'lhs - rhs' in t)
    proposal={'diagnosis':'Example arithmetic correction','edits':[{'file':path,'start_line':line,'end_line':line,'replacement':'    combine = lhs + rhs;'}]}
    class Ledger:
        def summary(self):return {'remaining_usd':50,'phase_remaining_usd':20}
        def quote(self,*a):return {'reserved_usd':1}
    class Client:
        inference_requests=0
        last_cost=None
        def __init__(self,files,*,enable_thinking):flags.append(enable_thinking);self.thinking=enable_thinking
        def verify_model(self):pass
        def generate(self,messages,*,max_tokens):
            assert max_tokens==(12288 if self.thinking else 6144)
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(proposal)}}]}
    monkeypatch.setattr(agent,'BudgetLedger',Ledger);monkeypatch.setattr(agent,'ProjectClient',Client)
    first=agent.propose(project,{'status':'PUBLIC_TESTS_FAILED'},tmp_path/'first')
    revised=agent.propose(project,{'status':'PUBLIC_TESTS_FAILED'},tmp_path/'revised',previous=proposal)
    assert flags==[False,True]
    assert first['api_requests']==revised['api_requests']==0
    assert first['status']==revised['status']=='VALID_PATCH'
    assert revised['reasoning_enabled'] and not first['reasoning_enabled']
    assert json.loads((tmp_path/'revised/request_started.json').read_text())['automatic_retry'] is False
