"""Exercise the exported command without importing RTLRefine or third-party Python."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def invoke(project, folder):
    folder.mkdir()
    report = folder / 'report.json'
    command = [sys.executable, '-I', str(project / 'rtlrefine_ci/run.py'), '--root', str(project),
               '--report', str(report), '--junit', str(folder / 'junit.xml')]
    process = subprocess.run(command, cwd=project, env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': '/nonexistent', 'LANG': 'C'},
                             capture_output=True, text=True, timeout=195)
    (folder / 'stdout.json').write_text(process.stdout)
    (folder / 'stderr.log').write_text(process.stderr)
    result = json.loads(report.read_text()) if report.exists() else json.loads(process.stdout)
    return {'exit_code': process.returncode, 'status': result['status'], 'accepted': result['accepted'],
            'new_model_calls': result['new_model_calls'], 'testbenches': len(result.get('tests', [])),
            'assertion_evaluations': sum(t['checks'] or 0 for t in result.get('tests', [])),
            'junit_exists': (folder / 'junit.xml').exists(), 'changed_editable_files': result.get('changed_editable_files', [])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='results/general-project-ci-cycle')
    a = p.parse_args()
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    base = ROOT / 'demo/general_project_ci'
    cases = []
    with tempfile.TemporaryDirectory(prefix='rtlrefine-ci-cycle-') as temp:
        for name, design, mutation, expected_assertions in [
            ('axis-register', 'rtl/axis_register.v', None, 30493),
            ('wide-math', 'rtl/word_math.sv', (b'lhs + rhs', b'lhs - rhs'), 42),
            ('dual-clock', 'rtl/domain_ticks.sv', (b'count_b + 1', b'count_b + 2'), 27),
            ('uart-peer', 'rtl/uart_tx.v', None, 186772),
        ]:
            project = Path(temp) / name
            shutil.copytree(base / name / 'project', project)
            target = project / design
            original = target.read_bytes()
            if name=='uart-peer':
                bad=(ROOT/'external_cases/uart_bitorder_external/original/rtl/uart_tx.v').read_bytes()
                other=project/'rtl/uart_rx.v';other_original=other.read_bytes()
                other_bad=(ROOT/'external_cases/uart_bitorder_external/original/rtl/uart_rx.v').read_bytes()
            else:
                bad = (ROOT / 'external_cases/axis_register_external/regressed/rtl/axis_register.v').read_bytes() if mutation is None else original.replace(*mutation)
            assert bad != original, name
            rows = []
            for phase, source in [('checked', original), ('bug_reintroduced', bad), ('restored', original)]:
                target.write_bytes(source)
                if name=='uart-peer':other.write_bytes(other_bad if phase=='bug_reintroduced' else other_original)
                row = {'phase': phase, **invoke(project, out / (name + '-' + phase))}
                if phase == 'bug_reintroduced':
                    assert row['exit_code'] == 1 and row['status'] == 'REGRESSION_FAILED', (name, row)
                else:
                    assert row['exit_code'] == 0 and row['accepted'] and row['assertion_evaluations'] == expected_assertions, (name, row)
                assert row['new_model_calls'] == 0 and row['junit_exists']
                rows.append(row)
            # A changed protected audit is a configuration error, not a pass.
            config = json.loads((project / 'rtlrefine.json').read_text())
            test = next(t for t in config['tests'] if t['phase'] == 'audit')['files'][0]
            audit = project / test
            audit.write_bytes(audit.read_bytes() + b'\n// unexpected check edit\n')
            protected = invoke(project, out / (name + '-audit-edited'))
            assert protected['exit_code'] == 2 and not protected['accepted']
            cases.append({'case': name, 'cycle': rows, 'changed_audit_exit_code': protected['exit_code'],
                          'engine_sha256': hashlib.sha256((project / 'rtlrefine_ci/engine.zip').read_bytes()).hexdigest()})
    report = {'status': 'PASS', 'new_model_calls': 0, 'third_party_python_required': False,
              'cases': cases, 'github_actions': bool(os.getenv('GITHUB_ACTIONS')),
              'github_sha': os.getenv('GITHUB_SHA'), 'scope': 'Finite supplied-test regression checks; not repair accuracy or physical CDC proof.'}
    (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
