"""Standard-library entry point copied into general-project CI exports."""
import sys

if __name__ == '__main__' and not sys.flags.isolated:
    print('Use isolated Python: python3 -I rtlrefine_ci/run.py', file=sys.stderr)
    raise SystemExit(2)

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

ENGINE_SHA256 = '4259d42270af42ab593129fd1a7171dc9805349f20f3de3afc0afe4b8fd743a0'
MANIFEST_SHA256 = '163d982b02ec166bbc0bc504e78c55c4293aac2465eb16732dfaa636311d8fed'
FOLDER = 'rtlrefine_ci'
WORKFLOW = '.github/workflows/rtlrefine.yml'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_input(root, name):
    if not isinstance(name, str) or not name or '\\' in name or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid bundle path')
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or ':' in rel.parts[0]:
        raise ValueError('Unsafe bundle path')
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symlink inputs are not supported: ' + name)
    if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Missing or oversized input: ' + name)
    return path.read_bytes()


def load_inputs(root):
    raw = read_input(root, FOLDER + '/manifest.json')
    if digest(raw) != MANIFEST_SHA256:
        raise ValueError('CI manifest changed; re-export after reviewing the checks')
    lock = json.loads(raw)
    if lock.get('schema_version') != 1 or lock.get('producer') != 'RTLRefine':
        raise ValueError('Unsupported CI manifest')
    names = lock['input_hashes']
    if not isinstance(names, dict) or not 1 <= len(names) <= 251:
        raise ValueError('Invalid CI input set')
    files = {name: read_input(root, name) for name in names}
    if sum(map(len, files.values())) > 32 * 1024 * 1024:
        raise ValueError('CI input size limit exceeded')
    for name, data in files.items():
        if name not in lock['editable_files'] and digest(data) != names[name]:
            raise ValueError('Protected input changed: ' + name + '; review and re-export')
    return lock, files


def run_suite(root):
    root = Path(root).resolve()
    lock, files = load_inputs(root)
    engine = read_input(root, FOLDER + '/engine.zip')
    if digest(engine) != ENGINE_SHA256:
        raise ValueError('Bundled verification engine changed')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='rtlrefine-project-ci-') as temp:
        work = Path(temp)
        trusted = work / 'engine'
        trusted.mkdir()
        with zipfile.ZipFile(io.BytesIO(engine)) as archive:
            for entry in archive.infolist():
                rel = PurePosixPath(entry.filename)
                if rel.is_absolute() or '..' in rel.parts or '\\' in entry.filename:
                    raise ValueError('Unsafe engine archive')
                target = trusted / str(rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))
        # Only this hash-verified engine enters Python's import path. Project
        # scripts, including files named json.py or rtl_agent, never do.
        sys.path.insert(0, str(trusted))
        from rtl_agent.project_repair.project import load_project
        from rtl_agent.project_repair.checker import check_project
        project = load_project(files)
        if project.config['editable_files'] != lock['editable_files']:
            raise ValueError('Editable-file roles changed')
        result = check_project(project, {}, work / 'native', interfaces=lock['interfaces'])
        _, after = load_inputs(root)
        if after != files:
            raise ValueError('Project inputs changed while verification was running')
    design_failures = {'ASSERTION_FAILED', 'DUT_COMPILE_FAILED', 'INTERFACE_CHANGED'}
    failed = [t for t in result['tests'] if not t['passed']]
    status = 'REGRESSIONS_PASS' if result['accepted'] else 'REGRESSION_FAILED' if all(t['status'] in design_failures for t in failed) else 'CHECK_UNPROVEN'
    return {'status': status, 'accepted': result['accepted'], 'new_model_calls': 0,
            'tests': result['tests'], 'design_hashes': result['design_hashes'],
            'changed_editable_files': [p for p in lock['editable_files'] if digest(files[p]) != lock['input_hashes'][p]],
            'manifest_sha256': MANIFEST_SHA256, 'engine_sha256': ENGINE_SHA256,
            'wall_seconds': time.monotonic() - started,
            'scope': 'All bundled immutable testbenches and elaborated interfaces; finite simulation, not unbounded correctness, timing or CDC proof.'}


def junit_bytes(result):
    tests = result.get('tests') or [{'id': 'setup', 'passed': False, 'status': result['status'], 'error': result.get('error', '')}]
    suite = ET.Element('testsuite', name='RTLRefine', tests=str(len(tests)),
                       failures=str(sum(not t['passed'] and t['status'] in {'ASSERTION_FAILED', 'DUT_COMPILE_FAILED', 'INTERFACE_CHANGED'} for t in tests)),
                       errors=str(sum(not t['passed'] and t['status'] not in {'ASSERTION_FAILED', 'DUT_COMPILE_FAILED', 'INTERFACE_CHANGED'} for t in tests)))
    for test in tests:
        case = ET.SubElement(suite, 'testcase', name=test['id'], classname='rtlrefine.provided_tests', time=str(test.get('wall_seconds', 0)))
        if not test['passed']:
            tag = 'failure' if test['status'] in {'ASSERTION_FAILED', 'DUT_COMPILE_FAILED', 'INTERFACE_CHANGED'} else 'error'
            ET.SubElement(case, tag, message=test['status']).text = test.get('log_tail') or test.get('error', '')
    return ET.tostring(suite, encoding='utf-8', xml_declaration=True) + b'\n'


def output_path(name, root):
    path = Path(name).absolute()
    # Never let a requested report overwrite checked inputs or the runner.
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('Report paths cannot contain symlinks')
    path = path.resolve()
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return path
    raw = read_input(root, FOLDER + '/manifest.json')
    if digest(raw) != MANIFEST_SHA256:
        raise ValueError('CI manifest changed; re-export after reviewing the checks')
    lock = json.loads(raw)
    if rel in lock['input_hashes'] or rel.startswith(FOLDER + '/') or rel == WORKFLOW:
        raise ValueError('Report path overlaps a protected project input')
    return path


def main():
    parser = argparse.ArgumentParser(description='Recheck this RTL project without RTLRefine, Streamlit or an API key')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument('--report', default='rtlrefine-ci-report.json')
    parser.add_argument('--junit', default='rtlrefine-ci-junit.xml')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        report = output_path(args.report, root)
        junit = output_path(args.junit, root)
        if report == junit:
            raise ValueError('JSON and JUnit output paths must differ')
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({'status': 'SETUP_ERROR', 'accepted': False, 'new_model_calls': 0, 'error': str(exc)}))
        return 2
    try:
        result = run_suite(root)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        result = {'status': 'SETUP_ERROR', 'accepted': False, 'new_model_calls': 0, 'tests': [], 'error': str(exc)}
    try:
        report.parent.mkdir(parents=True, exist_ok=True)
        junit.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        junit.write_bytes(junit_bytes(result))
    except OSError as exc:
        print(json.dumps({'status': 'REPORT_ERROR', 'accepted': False, 'new_model_calls': 0, 'error': str(exc)}))
        return 2
    print(json.dumps({k: v for k, v in result.items() if k != 'tests'}, indent=2))
    return 0 if result['accepted'] else 1 if result['status'] == 'REGRESSION_FAILED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
