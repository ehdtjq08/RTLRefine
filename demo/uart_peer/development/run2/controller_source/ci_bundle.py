"""Package the unchanged general-project checker and actually run the export."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from ..common import ROOT, sha256, write_json
from . import portable_ci
from .project import Project, archive_project, read_archive, MAX_FILES

FOLDER = 'rtlrefine_ci'
WORKFLOW = '.github/workflows/rtlrefine.yml'
OWNED = {FOLDER + '/' + p for p in ('run.py', 'engine.zip', 'manifest.json', 'README.md')} | {WORKFLOW}
ENGINE_FILES = ('rtl_agent/__init__.py', 'rtl_agent/common.py', 'rtl_agent/tool_paths.py',
                'rtl_agent/project_repair/__init__.py', 'rtl_agent/project_repair/project.py',
                'rtl_agent/project_repair/policy.py', 'rtl_agent/project_repair/test_policy.py',
                'rtl_agent/project_repair/runner.py', 'rtl_agent/project_repair/checker.py', 'LICENSE')


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def config_bytes(config):
    return (json.dumps(config, indent=2) + '\n').encode()


def engine_bytes():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ENGINE_FILES:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (ROOT / name).read_bytes())
    return stream.getvalue()


def driver_bytes(manifest, engine):
    return Path(portable_ci.__file__).read_bytes().replace(b'__ENGINE_SHA256__', sha256(engine).encode()).replace(b'__MANIFEST_SHA256__', sha256(manifest).encode())


def workflow_bytes():
    return b'''name: RTLRefine regressions
"on":
  push:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  rtl-regressions:
    runs-on: ubuntu-22.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
      - name: Install native verification tools
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y --no-install-recommends iverilog bubblewrap util-linux
      - name: Recompile and run all bundled checks
        run: python3 -I rtlrefine_ci/run.py --report rtlrefine-ci-report.json --junit rtlrefine-ci-junit.xml
      - name: Save JSON and JUnit results
        if: always()
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: rtlrefine-regressions
          path: |
            rtlrefine-ci-report.json
            rtlrefine-ci-junit.xml
          retention-days: 14
'''


README = '''# Reusable RTL project checks

From the extracted project root, run:

    python3 -I rtlrefine_ci/run.py

No API key, model request, Streamlit or RTLRefine installation is needed.
Python 3.10+, Linux, Icarus Verilog (`iverilog` and `vvp`), bubblewrap and
util-linux `prlimit` are required. Ubuntu/Debian setup:

    sudo apt-get install iverilog bubblewrap util-linux

The host must permit unprivileged user namespaces. Restricted hosts return
an explicit setup error; there is no unisolated fallback.

Exit 0: every provided test passed. Exit 1: a design regression (including
RTL compilation/interface failures). Exit 2: setup, integrity or unproven result.
JSON and JUnit reports default to `rtlrefine-ci-report.json` and
`rtlrefine-ci-junit.xml`; `--report`, `--junit` and `--root` override paths.

Commit the extracted project at your repository root, including the hidden
`.github/workflows/rtlrefine.yml`. Pushes and pull requests then run the same
command on GitHub Actions and upload both reports, even on failure. The workflow
uses read-only repository permission, no persisted checkout credential, no
secrets and no inference. Review normal CI changes before merging them.

The engine is a byte-preserving copy of RTLRefine's existing checker, policy,
project loader and isolated native runner, with its MIT license. The engine and
manifest hashes are embedded in run.py. Testbenches, read-only dependencies,
configuration and elaborated interfaces are locked; editable RTL can change
and is always freshly compiled. Re-export after intentionally changing checks
or interfaces. Hashes catch accidental drift; repository review protects the
runner and workflow themselves. They are not a signed or tamper-proof policy.

Only hash-verified bundled Python is imported. Uploaded project scripts are
never executed. Native tools receive only declared files, resource limits,
read-only inputs and no network or API credentials. The result covers the
provided finite tests; it is not unbounded protocol, timing or CDC proof.
'''


def prepare_project(project):
    present = {p for p in project.files if p == FOLDER or p.startswith(FOLDER + '/') or p == WORKFLOW}
    if not present:
        if len(project.files) + len(OWNED) + ('rtlrefine.json' not in project.files) > MAX_FILES:
            raise ValueError('Leave five project entries available for the generated CI bundle')
        return None
    if present != OWNED:
        raise ValueError('Reserved CI paths conflict or are incomplete: use an original project or a complete RTLRefine export')
    manifest = project.files[FOLDER + '/manifest.json']
    engine = engine_bytes()
    if (project.files[FOLDER + '/engine.zip'] != engine or project.files[FOLDER + '/run.py'] != driver_bytes(manifest, engine)
            or project.files[WORKFLOW] != workflow_bytes() or project.files[FOLDER + '/README.md'] != README.encode()):
        raise ValueError('Generated CI runner/engine/workflow changed; review and re-export from original sources')
    try:
        lock = json.loads(manifest)
        if lock['schema_version'] != 1 or lock['producer'] != 'RTLRefine' or lock['editable_files'] != project.config['editable_files']:
            raise ValueError('CI roles changed')
        for name, expected in lock['input_hashes'].items():
            if name not in project.files or (name not in lock['editable_files'] and sha256(project.files[name]) != expected):
                raise ValueError('Protected CI input changed: ' + name)
        if set(lock['input_hashes']) - set(project.files) or not set(lock['editable_files']) <= set(lock['input_hashes']):
            raise ValueError('CI source roles changed')
        # Verify normalized configuration too, including wizard/CLI overrides.
        if lock['input_hashes']['rtlrefine.json'] != sha256(config_bytes(project.config)):
            raise ValueError('CI configuration changed; review and re-export')
        return lock
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid generated CI manifest') from exc


def with_bundle(project, changes, checked):
    files = {p: v for p, v in project.files.items() if p not in OWNED}
    files.update({p: text.encode() for p, text in changes.items()})
    files['rtlrefine.json'] = config_bytes(project.config)
    lock = {'schema_version': 1, 'producer': 'RTLRefine', 'editable_files': project.config['editable_files'],
            'input_hashes': {p: sha256(v) for p, v in sorted(files.items())},
            'interfaces': {t['id']: t['interface'] for t in checked['tests']},
            'scope': 'Provided finite testbenches and elaborated interfaces; no model call.'}
    raw = json_bytes(lock)
    engine = engine_bytes()
    files.update({FOLDER + '/manifest.json': raw, FOLDER + '/engine.zip': engine,
                  FOLDER + '/run.py': driver_bytes(raw, engine), FOLDER + '/README.md': README.encode(), WORKFLOW: workflow_bytes()})
    exported = Project(files, project.config)
    assert read_archive(archive_project(exported)) == files
    return exported


def check_bundle(project, directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    files = read_archive(archive_project(project))
    from .project import load_project
    canonical = load_project(files)
    prepare_project(canonical)
    snapshot = root / 'project'
    snapshot.mkdir()
    for name, data in files.items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report, junit = root / 'standalone-report.json', root / 'standalone-junit.xml'
    command = [sys.executable, '-I', str(snapshot / FOLDER / 'run.py'), '--root', str(snapshot), '--report', str(report), '--junit', str(junit)]
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': '/nonexistent', 'LANG': 'C', 'LC_ALL': 'C'}
    try:
        with (root / 'stdout.log').open('wb') as stdout, (root / 'stderr.log').open('wb') as stderr:
            process = subprocess.run(command, cwd=snapshot, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, timeout=195)
        result = json.loads(report.read_text()) if report.exists() else {'status': 'RUNNER_ERROR', 'accepted': False}
        expected = 0 if result.get('accepted') else 1 if result.get('status') == 'REGRESSION_FAILED' else 2
        if process.returncode != expected or not junit.exists():
            result.update(status='RUNNER_PROTOCOL_ERROR', accepted=False)
        result.update(standalone_exit_code=process.returncode, python_isolated=True, canonical_runner_verified=True)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        result = {'status': 'RUNNER_UNPROVEN', 'accepted': False, 'error': str(exc), 'new_model_calls': 0}
    write_json(root / 'ci-result.json', result)
    return result
