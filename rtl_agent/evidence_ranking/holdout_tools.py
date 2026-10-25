"""Evaluation-only helpers for a new-module, synthetic ranking cohort.

This is a conditional candidate-ranking benchmark. A known inverse is seeded
into each pool. Neither grammar coverage nor discovery of real bugs is tested.
The ranking algorithm and its weights live in separate, frozen modules.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
import re
import shutil

from ..common import sha256, write_json
from ..known_bugs_v2.cases import code_only, source_policy
from ..known_bugs_v2.engine import harness, compile_candidate, run_trace, qualify_expected_file
from ..repair_search.candidates import make_pool
from ..repair_search.retention import comment_blanked

SEED = 20261023
POOL_CAP = 24
PROFILES = ((256, 1103), (512, 7403), (768, 9601))


def normalize_source(source):
    """Remove only an inactive, outer `ifdef FORMAL appendix; retain lines."""
    lines = source.splitlines(keepends=True)
    depth = 0
    removed = 0
    result = []
    for line in lines:
        directive = re.match(r'\s*`(ifdef|ifndef|else|endif)\b\s*(\w*)', line)
        if depth:
            if directive and directive[1] in ('ifdef', 'ifndef'):
                depth += 1
            elif directive and directive[1] == 'endif':
                depth -= 1
            elif directive and directive[1] == 'else' and depth == 1:
                raise ValueError('Unsupported outer FORMAL else branch')
            result.append(''.join('\n' if c == '\n' else ' ' for c in line))
            removed += 1
        elif directive and directive[1] == 'ifdef' and directive[2] == 'FORMAL':
            depth = 1
            result.append(''.join('\n' if c == '\n' else ' ' for c in line))
            removed += 1
        else:
            result.append(line)
    if depth:
        raise ValueError('Unbalanced FORMAL appendix')
    return ''.join(result), removed


def widths_from(module):
    return {name: len(net['bits']) for name, net in module.get('netnames', {}).items()
            if re.fullmatch(r'[A-Za-z_]\w*', name)}


def mutation_options(source, widths):
    """Fixed source-only fault family: replace a same-width signal RHS by zero."""
    clean = comment_blanked(source)
    start = source.index(');') + 2
    options = []
    for m in re.finditer(r'\b(\w+)\s*(<=|=(?!=))\s*(\w+)\s*;', clean[start:]):
        lhs, operator, rhs = m.groups()
        if lhs not in widths or rhs not in widths or widths[lhs] != widths[rhs]:
            continue
        if re.search(r'clk|clock|reset|rst', lhs + ' ' + rhs, re.I):
            continue
        a, b = start + m.start(3), start + m.end(3)
        options.append({'start': a, 'end': b, 'old': source[a:b], 'replacement': '0',
                        'lhs': lhs, 'operator': operator, 'line': source.count('\n', 0, a) + 1})
    random.Random(SEED).shuffle(options)
    return options[:12]


def candidate_pool(mutant, reference, mutation, widths, ports):
    """Source grammar distractors plus a seeded inverse, with no outcome use."""
    options = make_pool(mutant, widths)
    clean = comment_blanked(mutant)
    boundary = mutant.index(');') + 2
    signals = sorted(n for n in widths if not re.search(r'clk|clock|rst|reset', n, re.I))
    for m in re.finditer(r'\b(\w+)\s*(?:<=|=(?!=))\s*(?:\d+\s*\x27\s*[bBdDhH][0-9a-fA-F_]+|\d+)\s*;', clean[boundary:]):
        lhs = m[1]
        if lhs not in widths:
            continue
        # Locate just the RHS, retaining all assignment/control syntax.
        fragment = clean[boundary + m.start():boundary + m.end()]
        op = re.search(r'<=|=(?!=)', fragment)
        a = boundary + m.start() + op.end()
        b = boundary + m.end() - 1
        while a < b and mutant[a].isspace():
            a += 1
        while b > a and mutant[b-1].isspace():
            b -= 1
        alternatives = [n for n in signals if widths[n] == widths[lhs] and n != lhs]
        random.Random(SEED + a).shuffle(alternatives)
        for rhs in alternatives[:6]:
            rtl = mutant[:a] + rhs + mutant[b:]
            options.append({'family': 'rhs_substitution', 'line': mutant.count('\n', 0, a)+1,
                            'note': 'Use existing same-width signal '+rhs+' for '+lhs,
                            'edits': [{'start': a, 'end': b, 'old': mutant[a:b], 'replacement': rhs}],
                            'rtl_sha256': sha256(rtl.encode()), 'rtl': rtl, 'changed_spans': 1})
    a = mutation['start']
    inverse = {'family': 'rhs_substitution', 'line': mutation['line'],
               'note': 'Use existing same-width signal '+mutation['old']+' for '+mutation['lhs'],
               'edits': [{'start': a, 'end': a+1, 'old': '0', 'replacement': mutation['old']}],
               'rtl_sha256': sha256(reference.encode()), 'rtl': reference, 'changed_spans': 1}
    by_hash = {}
    for item in options + [inverse]:
        try:
            source_policy(item['rtl'], mutant, ports)
        except ValueError:
            continue
        by_hash[item['rtl_sha256']] = item
    by_hash.pop(inverse['rtl_sha256'], None)
    distractors = sorted(by_hash.values(), key=lambda p: p['rtl_sha256'])
    random.Random(SEED + mutation['start']).shuffle(distractors)
    pool = distractors[:POOL_CAP-1] + [inverse]
    pool.sort(key=lambda p: (p['edits'][0]['start'], p['rtl_sha256']))
    for i, item in enumerate(pool, 1):
        item['id'] = f'candidate_{i:03d}'
    return pool


def proposed_inputs(ports, clock, module_id, cycles, seed):
    names = sorted(n for n,p in ports.items() if p['direction'] == 'input' and n != clock)
    rng = random.Random(seed)
    rows = []
    for cycle in range(cycles):
        reset = cycle < 4 or cycle in (cycles//2, cycles//2+1)
        row = {}
        for name in names:
            width = ports[name]['width']
            if name in ('rst', 'i_reset'):
                value = int(reset)
            elif name in ('rate_num', 'rate_denom'):
                value = 3 if name == 'rate_num' else 5
            elif name == 'rate_by_frame':
                value = seed % 2
            elif name == 'prescale':
                value = 2
            elif name == 'stop_on_idle':
                value = 1
            elif name in ('scl_i', 'sda_i'):
                value = 1  # replaced by wired-AND feedback in reference capture
            elif name == 'trigger':
                value = int(cycle % 37 == 8)
            elif name == 's_axis_cmd_valid':
                value = int(cycle % 160 < 12 and not reset)
            elif name == 's_axis_cmd_address':
                value = 0x52
            elif name in ('s_axis_cmd_start', 's_axis_cmd_write', 's_axis_cmd_stop'):
                value = 1
            elif name in ('s_axis_cmd_read', 's_axis_cmd_write_multiple'):
                value = 0
            elif name.endswith(('valid', 'ready')):
                value = int(rng.random() < .7 and not reset)
            elif name.endswith('tkeep'):
                value = (1 << rng.randrange(width+1)) - 1
            elif name.endswith('tlast'):
                value = int(rng.random() < .25)
            else:
                value = rng.getrandbits(width)
            row[name] = value
        rows.append(row)
    return names, rows


def capture_harness(ports, clock, top):
    """Drive source fields stably until the reference accepts the transfer.

    I2C has no responding slave: external lines are released, with the master's
    own open-drain drive fed back. It exercises address/NACK/stop, not slave data.
    The resulting concrete stimulus is replayed identically for every candidate.
    """
    text = harness(ports, clock, top)
    inputs = sorted(n for n,p in ports.items() if p['direction'] == 'input' and n != clock)
    groups = []
    for valid in inputs:
        if valid == 'i_valid':
            ready, fields = 'o_ready', ['i_valid', 'i_data']
        elif valid.endswith('tvalid'):
            prefix = valid[:-len('tvalid')]
            ready = prefix + 'tready'
            fields = [n for n in inputs if n.startswith(prefix) and n != ready]
        elif valid.endswith('_valid'):
            prefix = valid[:-len('valid')]
            ready = prefix + 'ready'
            fields = [n for n in inputs if n.startswith(prefix) and n != ready]
        else:
            continue
        if ready in ports:
            groups.append((valid, ready, fields))
    declarations = '\nstd::ofstream actual_stimulus("actual_stimulus.hex");\n'
    declarations += f'uint64_t held_values[{len(inputs)}]={{0}};\n'
    declarations += '\n'.join(f'bool stalled_{i}=false;' for i in range(len(groups)))
    text = text.replace(' std::vector<std::string> history;', ' std::vector<std::string> history;'+declarations)
    reset = 'i_reset' if 'i_reset' in ports else 'rst'
    reset_expr = f'input_values[{inputs.index(reset)}]'
    before = []
    for i, (valid, ready, fields) in enumerate(groups):
        for name in fields:
            index = inputs.index(name)
            before.append(f'if(stalled_{i} && !{reset_expr}) input_values[{index}]=held_values[{index}];')
        before.append(f'if({reset_expr}) input_values[{inputs.index(valid)}]=0;')
    text = text.replace('  dut.'+clock+'=0;', '\n'.join(before)+'\n  dut.'+clock+'=0;', 1)
    after = []
    if 'scl_i' in ports and 'sda_i' in ports:
        after += ['dut.scl_i=dut.scl_o; dut.sda_i=dut.sda_o; dut.eval();',
                  f'input_values[{inputs.index("scl_i")}]=dut.scl_i;',
                  f'input_values[{inputs.index("sda_i")}]=dut.sda_i;']
    after += [f'for(size_t j=0;j<{len(inputs)};j++) held_values[j]=input_values[j];']
    for i,(valid,ready,fields) in enumerate(groups):
        after.append(f'stalled_{i}=dut.{valid} && !dut.{ready} && !dut.{reset};')
    after += ['for(auto v:input_values) actual_stimulus<<std::hex<<v<<" ";actual_stimulus<<"\\n";']
    text = text.replace('  uint64_t output_values[]=', '\n'.join(after)+'\n  uint64_t output_values[]=')
    return text


def build_reference_traces(source, ports, clock, top, directory, runner):
    compiled = directory / 'reference_capture'
    compiled.mkdir()
    (compiled/'candidate.v').write_text(source)
    (compiled/'dependencies.v').write_text('')
    (compiled/'harness.cpp').write_text(capture_harness(ports, clock, top))
    commands = [runner.run('translate', compiled, top)]
    if commands[-1]['status'] == 'PASS':
        commands.append(runner.run('build', compiled, top))
    if len(commands) != 2 or commands[-1]['status'] != 'PASS':
        raise RuntimeError('Reference capture compilation failed: '+str(compiled))
    traces = []
    for i,(cycles,seed) in enumerate(PROFILES):
        folder = directory/f'trace_{i}'
        folder.mkdir()
        names, rows = proposed_inputs(ports, clock, top, cycles, seed)
        proposed = folder/'proposed.hex'
        proposed.write_text(''.join(' '.join(format(r[n],'x') for n in names)+'\n' for r in rows))
        expected = folder/'expected.hex'
        expected.write_text('')
        outputs = sorted(n for n,p in ports.items() if p['direction'] == 'output')
        trace = {'stimulus': str(proposed), 'expected': str(expected), 'cycles': cycles,
                 'inputs': names, 'outputs': outputs, 'label': 'discovery' if i == 0 else 'sealed_audit_'+str(i)}
        result = run_trace(compiled, trace, top, runner, capture=True)
        if not result['passed']:
            raise RuntimeError('Incomplete reference capture')
        shutil.copyfile(compiled/'actual_stimulus.hex', folder/'stimulus.hex')
        shutil.copyfile(compiled/'observed.hex', expected)
        qualify_expected_file(expected, outputs)
        # Skidbuffer payload only has meaning while its valid flag is asserted.
        if 'o_data' in outputs and 'o_valid' in outputs:
            lines = []
            for line in expected.read_text().splitlines():
                cells = line.split()
                if cells[outputs.index('o_valid')] == '0':
                    cells[outputs.index('o_data')] = '?'
                lines.append(' '.join(cells)+'\n')
            expected.write_text(''.join(lines))
        traces.append({**trace, 'stimulus': str((folder/'stimulus.hex').resolve()),
                       'expected': str(expected.resolve()), 'seed': seed})
    return traces


def evaluate_source(source, original, case, directory, runner, *, discovery_only=False):
    """Same fixed native runner and source policy as the historical comparison."""
    directory.mkdir(parents=True)
    result = {'rtl_sha256': sha256(source.encode()), 'discovery_pass': False,
              'accepted': False, 'traces': [], 'status': 'POLICY_REJECTED'}
    try:
        source_policy(source, original, case['ports'])
        compiled = directory/'compiled'
        commands = compile_candidate(source, '', case['ports'], case['clock'], case['top'], compiled, runner)
        result['commands'] = commands
        if len(commands) != 2 or commands[-1]['status'] != 'PASS':
            result['status'] = 'COMPILE_FAILED'
        else:
            for i,trace in enumerate(case['traces'][:1] if discovery_only else case['traces']):
                value = run_trace(compiled, trace, case['top'], runner)
                result['traces'].append(value)
                (directory/f'trace_{i}.log').write_bytes((compiled/'simulate.log').read_bytes())
                if i == 0:
                    result['discovery_pass'] = value['passed']
                    if not value['passed']:
                        break
            result['accepted'] = not discovery_only and len(result['traces']) == 3 and all(t['passed'] for t in result['traces'])
            result['status'] = 'ACCEPTED' if result['accepted'] else 'DISCOVERY_PASS' if result['discovery_pass'] else 'DISCOVERY_FAILED'
    except (ValueError, RuntimeError, OSError) as exc:
        result['error'] = str(exc)
    write_json(directory/'evaluation.json', result)
    return result
