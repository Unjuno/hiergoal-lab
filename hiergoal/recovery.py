# SPDX-License-Identifier: Apache-2.0
"""Controlled post-failure recovery pilot; live execution is explicitly gated.

Preparation is shared and blinded. A successful model-generated artifact is
corrupted once and forked into two isolated repair episodes. Neither repair
episode receives the preparation history or pre-corruption artifact.
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

from hiergoal.study import Trace, OracleResponder, action_prompt, apply_patch, object_reply
from hiergoal.study_api import OpenAIResponder, TransportError
from hiergoal.study_mechanisms import InvalidAction, validate_replan
from hiergoal.study_planning import active_leaf, milestone_statuses, plan_prompt, statuses, validate_plan
from hiergoal.study_protocol import canonical, digest, host_metadata, save
from hiergoal.recovery_protocol import build_manifest, make_task, validate_manifest
from hiergoal.recovery_checkpoint import make_checkpoint, restore_checkpoint


def all_pass(grades):
    return bool(grades) and all(item['passed'] is True for item in grades.values())


def ordered_plan(plan, task):
    """JSON object key sorting cannot alter the controller's executable order."""
    if plan is None:
        return None
    result = copy.deepcopy(plan)
    by_gate = {leaf['checks'][0]: ident for ident, leaf in plan['leaves'].items()}
    result['leaves'] = {by_gate[gate]: result['leaves'][by_gate[gate]] for gate in task.gates}
    return result


def snapshot(task, solution, plan):
    grades = task.grade(solution)
    return {
        'solution': copy.deepcopy(solution), 'plan': copy.deepcopy(plan),
        'public_grades': grades, 'leaf_statuses': statuses(plan, grades),
        'milestone_statuses': milestone_statuses(plan, grades),
        'root_status': 'awaiting_final_verification' if all_pass(grades) else 'active',
        'environment_sha256': digest(task.public_spec()), 'root_sha256': digest(task.root_contract),
    }


def run_phase(directory, specification, manifest, backend, *, phase, checkpoint=None):
    """One bounded phase. Kept injectable only for offline apparatus tests."""
    directory = Path(directory)
    if phase not in ('prepare', 'repair'):
        raise ValueError('Unknown phase')
    if phase == 'prepare':
        task = make_task(specification['task'])
        solution, plan = task.initial_solution(), None
        identifier, arm = specification['pair_id'], None
        limits = manifest['preparation_limits']
    else:
        task, plan, solution = restore_checkpoint(checkpoint, protocol_id=manifest['protocol_id'])
        identifier, arm = specification['trial_id'], specification['arm']
        if checkpoint['pair_id'] != specification['pair_id']:
            raise ValueError('Wrong paired checkpoint')
        if digest(task.root_contract) != digest(make_task(specification['task']).root_contract):
            raise ValueError('Checkpoint belongs to another task')
        plan = ordered_plan(plan, task)
        limits = manifest['limits']
    if backend.kind == 'oracle':
        backend.task = task
    root_hash, environment_hash = digest(task.root_contract), digest(task.public_spec())
    trace = Trace(directory / 'trace.jsonl', root_hash)
    initial_state = snapshot(task, solution, plan)
    trace.add('start', phase=phase, identifier=identifier, pair_id=specification['pair_id'],
              protocol_id=manifest['protocol_id'], arm=arm, task=specification['task'],
              checkpoint_sha256=checkpoint['checkpoint_sha256'] if checkpoint else None,
              state=initial_state)
    result = {
        'phase': phase, 'identifier': identifier, 'pair_id': specification['pair_id'],
        'task_id': specification['task_id'], 'arm': arm,
        'status': 'UNCERTAIN', 'diagnostic': 'INCOMPLETE', 'calls': 0,
        'input_tokens': 0, 'output_tokens': 0, 'known_input_tokens': 0,
        'known_output_tokens': 0, 'elapsed_seconds': 0.0,
        'replan_attempts': 0, 'replans': 0, 'rejected_actions': 0, 'patch_actions': 0,
        'simulated': manifest['backend'] == 'oracle', 'invariant_ok': True,
        'stop_batch': False,
    }
    history, pending = [], None
    started = time.monotonic()

    def terminate(code, *, status='FAIL', budget=None, transport_evidence=None):
        result.update(status=status, diagnostic=code, stop_batch=status == 'UNCERTAIN')
        trace.add('termination', status=status, diagnostic=code, reason=code,
                  budget=budget, transport_evidence=transport_evidence,
                  wall_seconds=max(0.0, time.monotonic() - started))

    try:
        while True:
            if (digest(task.root_contract) != root_hash or
                    digest(task.public_spec()) != environment_hash):
                result['invariant_ok'] = False
                terminate('APPARATUS_ERROR', status='UNCERTAIN')
                break
            grades = task.grade(solution)
            if plan is not None and all_pass(grades):
                hidden = task.grade(solution, hidden=True)
                passed = all_pass(hidden)
                trace.add('grade', public_grades=grades, hidden_grades=hidden,
                          passed=passed, solution_sha256=digest(solution))
                result.update(status='PASS' if passed else 'FAIL',
                              diagnostic='INDEPENDENT_GRADING_PASS' if passed else 'HIDDEN_GRADING_FAIL')
                break
            total = result['known_input_tokens'] + result['known_output_tokens']
            elapsed = max(0.0, time.monotonic() - started)
            checks = (
                ('CALL_BUDGET_BEFORE', result['calls'], limits['max_calls']),
                ('TOKEN_BUDGET_BEFORE', total, limits['max_total_tokens']),
                ('TIME_BUDGET_BEFORE', elapsed, limits['trial_timeout_seconds']),
            )
            exhausted = next(((code, value, limit) for code, value, limit in checks if value >= limit), None)
            if exhausted:
                code, value, limit = exhausted
                terminate(code, budget={'observed': value, 'limit': limit})
                break
            if phase == 'prepare' and plan is None:
                role, payload = 'plan', plan_prompt(task)
            elif phase == 'repair' and arm == 'adaptive' and result['replan_attempts'] == 0:
                role = 'replan'
                leaf = active_leaf(plan, grades)
                if leaf is None:
                    raise RuntimeError('No failed executable leaf')
                payload = action_prompt(role, task, solution, grades, plan, leaf, history)
            else:
                role = 'execute'
                shown_plan = plan if phase == 'repair' else None
                leaf = active_leaf(shown_plan, grades) if shown_plan is not None else None
                payload = action_prompt(role, task, solution, grades, shown_plan, leaf, history)
            prompt_bytes = len(canonical(payload).encode('utf-8'))
            if prompt_bytes > limits['max_prompt_bytes']:
                terminate('PROMPT_BUDGET_BEFORE', budget={'observed': prompt_bytes,
                          'limit': limits['max_prompt_bytes'], 'role': role, 'payload': payload})
                break
            allowance = min(limits['max_output_tokens'], limits['max_total_tokens'] - total)
            result['calls'] += 1
            if role == 'replan':
                result['replan_attempts'] += 1
            pending = role
            trace.add('request_started', role=role, payload=payload, call_index=result['calls'],
                      max_output_tokens=allowance, wall_seconds=elapsed)
            record = backend.respond(role, copy.deepcopy(payload), max_output_tokens=allowance)
            if (not isinstance(record, dict) or any(type(record.get(k)) is not int or record[k] < 0
                    for k in ('input_tokens', 'output_tokens'))):
                raise TransportError('Invalid response usage')
            pending = None
            for name in ('input_tokens', 'output_tokens'):
                result['known_' + name] += record[name]
                result[name] = result['known_' + name]
            result['elapsed_seconds'] += float(record.get('elapsed_seconds', 0.0))
            after_total = result['input_tokens'] + result['output_tokens']
            after_time = max(0.0, time.monotonic() - started)
            over = ('TOKEN_BUDGET_AFTER' if after_total > limits['max_total_tokens'] else
                    'TIME_BUDGET_AFTER' if after_time > limits['trial_timeout_seconds'] else None)
            action, reason = None, None
            if over:
                outcome = {'type': 'budget_exceeded', 'action': None, 'reason': over}
            else:
                try:
                    action = object_reply(record)
                    if role == 'plan':
                        plan = validate_plan(action, task)
                        effect = 'plan'
                    elif role == 'replan':
                        plan, _ = validate_replan(plan, active_leaf(plan, grades), grades, action)
                        plan = ordered_plan(plan, task)
                        result['replans'] += 1
                        effect = 'replan'
                    else:
                        solution = apply_patch(solution, action)
                        result['patch_actions'] += 1
                        grades = task.grade(solution)
                        history.append({'action': action, 'public_feedback': grades})
                        effect = 'patch'
                    outcome = {'type': effect, 'action': action, 'reason': None}
                except InvalidAction as exc:
                    reason = str(exc)
                    result['rejected_actions'] += 1
                    outcome = {'type': 'rejected', 'action': action, 'reason': reason}
                    history.append({'feedback': reason})
            trace.add('response', role=role, record=record, outcome=outcome, wall_seconds=after_time,
                      state=snapshot(task, solution, plan))
            if over:
                value = after_total if over == 'TOKEN_BUDGET_AFTER' else after_time
                limit = limits['max_total_tokens'] if over == 'TOKEN_BUDGET_AFTER' else limits['trial_timeout_seconds']
                terminate(over, budget={'observed': value, 'limit': limit})
                break
            if role == 'plan' and reason is not None:
                terminate('INVALID_PLAN')
                break
    except TransportError as exc:
        result['input_tokens'] = result['output_tokens'] = None
        evidence = copy.deepcopy(exc.evidence)
        trace.add('request_failed', role=pending, diagnostic=str(exc), transport_evidence=evidence)
        terminate('TRANSPORT_ERROR', status='UNCERTAIN', transport_evidence=evidence)
    except Exception as exc:
        # Never serialize arbitrary exception messages or credential-bearing objects.
        if pending is not None:
            result['input_tokens'] = result['output_tokens'] = None
            trace.add('request_failed', role=pending, diagnostic='APPARATUS_ERROR:' + type(exc).__name__,
                      transport_evidence=None)
        terminate('APPARATUS_ERROR', status='UNCERTAIN')
    result['invariant_ok'] = (result['invariant_ok'] and digest(task.root_contract) == root_hash
                              and digest(task.public_spec()) == environment_hash)
    result.update(
        success=True if result['status'] == 'PASS' else False if result['status'] == 'FAIL' else None,
        wall_seconds=max(0.0, time.monotonic() - started),
        final_solution=copy.deepcopy(solution), final_plan=copy.deepcopy(plan),
        final_artifact_sha256=digest(solution), final_plan_sha256=digest(plan),
        final_environment_sha256=digest(task.public_spec()),
    )
    trace.add('result', result=result)
    result['trace_final_sha256'] = trace.previous
    save(directory / 'result.json', result)
    return result


def prepare(output, *, backend='openai'):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Refusing a nonempty output directory')
    manifest = build_manifest(backend=backend)
    save(output / 'manifest.json', manifest)
    save(output / 'host.json', host_metadata())
    return manifest


def execute(output, manifest, backend):
    from hiergoal.recovery_audit import audit_phase
    from hiergoal.recovery_analysis import collect
    output = Path(output)
    validate_manifest(manifest)
    lock = output / 'execution.json'
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(canonical({'state': 'RUNNING', 'protocol_id': manifest['protocol_id'],
                                'backend': manifest['backend']}))
    started, stopped = time.monotonic(), False
    preparations, results = [], []
    save(output / 'host.json', host_metadata())
    try:
        for pair in manifest['pairs']:
            if stopped or time.monotonic() - started >= manifest['limits']['batch_timeout_seconds']:
                stopped = True
                break
            print('Preparing', pair['pair_id'], flush=True)
            path = output / 'preparations' / pair['pair_id']
            source = run_phase(path, pair, manifest, backend, phase='prepare')
            audit = audit_phase(path, pair, manifest)
            preparations.append({**source, 'audit': audit['status']})
            save(output / 'preparations.json', preparations)
            if audit['status'] != 'PASS' or source['stop_batch']:
                stopped = True
                break
            if source['status'] != 'PASS':
                print('Source preparation failed; paired slots retained without regeneration.', flush=True)
                continue
            checkpoint = make_checkpoint(make_task(pair['task']), source['final_plan'], source['final_solution'],
                         pair_id=pair['pair_id'], protocol_id=manifest['protocol_id'],
                         source_trace_sha256=source['trace_final_sha256'])
            save(output / 'checkpoints' / (pair['pair_id'] + '.json'), checkpoint)
            for arm in pair['arm_order']:
                if time.monotonic() - started >= manifest['limits']['batch_timeout_seconds']:
                    stopped = True
                    break
                trial = next(t for t in manifest['trials'] if t['pair_id'] == pair['pair_id'] and t['arm'] == arm)
                print('Repairing', trial['trial_id'], flush=True)
                path = output / 'trials' / trial['trial_id']
                row = run_phase(path, trial, manifest, backend, phase='repair', checkpoint=checkpoint)
                audit = audit_phase(path, trial, manifest, checkpoint=checkpoint)
                results.append({**row, 'audit': audit['status']})
                save(output / 'results.json', results)
                if audit['status'] != 'PASS' or row['stop_batch']:
                    stopped = True
                    break
    except Exception as exc:
        stopped = True
        save(output / 'execution.json', {'state': 'STOPPED', 'protocol_id': manifest['protocol_id'],
             'backend': manifest['backend'], 'diagnostic': 'APPARATUS_ERROR:' + type(exc).__name__,
             'wall_seconds': time.monotonic() - started})
        collect(output, manifest)
        raise
    save(output / 'execution.json', {'state': 'STOPPED' if stopped else 'COMPLETED',
         'protocol_id': manifest['protocol_id'], 'backend': manifest['backend'],
         'wall_seconds': time.monotonic() - started})
    return collect(output, manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run', 'check', 'collect'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approve-paid-api', action='store_true')
    args = parser.parse_args(argv)
    if args.mode == 'prepare':
        manifest = prepare(args.output)
        print('Frozen controlled recovery pilot:', manifest['protocol_id'])
        return 0
    if args.mode == 'check':
        if args.execute or args.approve_paid_api:
            parser.error('Offline check cannot request live inference')
        manifest = prepare(args.output, backend='oracle')
        summary = execute(args.output, manifest, OracleResponder())
    elif args.mode == 'collect':
        from hiergoal.recovery_analysis import collect
        summary = collect(args.output)
    else:
        if not args.execute or not args.approve_paid_api:
            parser.error('Live inference requires --execute --approve-paid-api')
        manifest = json.loads((args.output / 'manifest.json').read_text(encoding='utf-8'))
        validate_manifest(manifest)
        if manifest['backend'] != 'openai':
            parser.error('Live execution requires the frozen OpenAI backend')
        backend = OpenAIResponder(manifest['model'], approve_live=True,
                                  timeout=manifest['limits']['request_timeout_seconds'])
        summary = execute(args.output, manifest, backend)
    print(canonical(summary))
    if args.mode == 'collect':
        # A valid incomplete record is collectable. It is never promoted to a
        # completed experiment; run/check keep the strict apparatus gate below.
        return 1 if summary.get('audit_status') == 'FAIL' else 0
    return 0 if summary.get('apparatus_decision') == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
