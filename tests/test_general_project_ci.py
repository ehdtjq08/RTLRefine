import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from rtl_agent.project_repair import ci_bundle
from rtl_agent.project_repair.examples import example_files
from rtl_agent.project_repair.project import load_project, read_archive
from rtl_agent.project_repair.runner import ProjectRunner
from rtl_agent.project_repair.workflow import run_project


@pytest.fixture(scope='module')
def exported(tmp_path_factory):
    root = tmp_path_factory.mktemp('general-ci')
    ok, why = ProjectRunner().probe(root / 'probe')
    if not ok:
        pytest.skip(why)
    files = example_files()
    files['rtl/word_math.sv'] = files['rtl/word_math.sv'].replace(b'lhs - rhs', b'lhs + rhs')
    # This uploaded Python must never enter the standalone import path.
    files['json.py'] = b'raise RuntimeError("PROJECT_PYTHON_MUST_NOT_EXECUTE")\n'
    result = run_project(load_project(files), output=str(root / 'export'))
    assert result['accepted'] and result['ci_regressions']['standalone_exit_code'] == 0
    return read_archive((root / 'export/checked-project.zip').read_bytes())


def extract(files, root):
    root.mkdir()
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def invoke(root, output, *extra):
    output.mkdir()
    report = output / 'report.json'
    process = subprocess.run([sys.executable, '-I', str(root / 'rtlrefine_ci/run.py'),
                              '--report', str(report), '--junit', str(output / 'junit.xml'), *map(str, extra)],
                             cwd=root, env={'PATH': os.environ['PATH'], 'HOME': '/nonexistent', 'LANG': 'C'},
                             capture_output=True, text=True, timeout=195)
    return process, json.loads(report.read_text()) if report.exists() else json.loads(process.stdout)


def test_exported_multifile_runner_catches_reintroduced_bug_then_passes_restore(exported, tmp_path):
    root = extract(exported, tmp_path / 'project')
    design = root / 'rtl/word_math.sv'
    original = design.read_bytes()
    outcomes = []
    for label, data in [('checked', original), ('regressed', original.replace(b'lhs + rhs', b'lhs - rhs')), ('restored', original)]:
        design.write_bytes(data)
        p, r = invoke(root, tmp_path / label)
        outcomes.append(p.returncode)
        assert r['new_model_calls'] == 0
        if label == 'regressed':
            assert r['status'] == 'REGRESSION_FAILED' and r['changed_editable_files'] == ['rtl/word_math.sv']
            assert '<failure ' in (tmp_path / label / 'junit.xml').read_text()
        else:
            assert r['accepted'] and [t['checks'] for t in r['tests']] == [2, 40]
    assert outcomes == [0, 1, 0]


@pytest.mark.parametrize('path', ['tests/audit.sv', 'rtl/customer_top.sv', 'rtlrefine.json', 'rtlrefine_ci/engine.zip'])
def test_standalone_protected_input_changes_are_setup_errors(exported, tmp_path, path):
    root = extract(exported, tmp_path / 'project')
    target = root / path
    target.write_bytes(target.read_bytes() + b'\n')
    p, r = invoke(root, tmp_path / 'check')
    assert p.returncode == 2 and not r['accepted'] and r['new_model_calls'] == 0


@pytest.mark.parametrize('path', ['rtlrefine_ci/run.py', 'rtlrefine_ci/manifest.json', '.github/workflows/rtlrefine.yml'])
def test_reimport_rejects_changed_generated_code_before_any_model_call(exported, tmp_path, monkeypatch, path):
    files = dict(exported)
    files[path] += b'\n'
    monkeypatch.setattr('rtl_agent.project_repair.workflow.propose', lambda *a, **k: pytest.fail('Paid call attempted'))
    with pytest.raises(ValueError):
        run_project(load_project(files), repair=True, output=str(tmp_path / 'must-not-start'))
    assert not (tmp_path / 'must-not-start').exists()


def test_manifest_override_cannot_drop_locked_audit(exported):
    config = copy.deepcopy(load_project(exported).config)
    config['tests'] = config['tests'][:1]
    with pytest.raises(ValueError, match='configuration'):
        ci_bundle.prepare_project(load_project(exported, config))


def test_report_cannot_overwrite_inputs_via_parent_segments(exported, tmp_path):
    root = extract(exported, tmp_path / 'project')
    before = (root / 'rtlrefine.json').read_bytes()
    p, r = invoke(root, tmp_path / 'output', '--report', root / 'unused/../rtlrefine.json')
    assert p.returncode == 2 and not r['accepted']
    assert (root / 'rtlrefine.json').read_bytes() == before


def test_reimported_ci_project_retains_both_benches(exported, tmp_path):
    result = run_project(load_project(exported), output=str(tmp_path / 'recheck'))
    assert result['accepted'] and result['audit_tests'] == 1 and result['api_requests'] == 0
    assert len(result['ci_regressions']['tests']) == 2


def test_reserved_ci_collision_stops_before_model_request(tmp_path, monkeypatch):
    files = example_files()
    files['rtlrefine_ci/README.md'] = b'User-owned file'
    monkeypatch.setattr('rtl_agent.project_repair.workflow.propose', lambda *a, **k: pytest.fail('Paid call attempted'))
    with pytest.raises(ValueError, match='Reserved CI'):
        run_project(load_project(files), repair=True, output=str(tmp_path / 'must-not-start'))


def test_failed_standalone_export_gate_prevents_checked_download(exported, tmp_path, monkeypatch):
    monkeypatch.setattr(ci_bundle, 'check_bundle', lambda *a, **k: {'status': 'CHECK_UNPROVEN', 'accepted': False, 'new_model_calls': 0})
    result = run_project(load_project(exported), output=str(tmp_path / 'check'))
    assert result['final_check']['accepted'] and not result['accepted'] and result['status'] == 'CI_EXPORT_REJECTED'
    assert not (tmp_path / 'check/checked-project.zip').exists()
