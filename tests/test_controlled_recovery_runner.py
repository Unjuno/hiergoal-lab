# SPDX-License-Identifier: Apache-2.0
"""Exercise treatment, budget, provenance and failure policies without inference."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.recovery import run_phase
from hiergoal.recovery_checkpoint import make_checkpoint
from hiergoal.recovery_protocol import build_manifest, make_task
from hiergoal.study import OracleResponder
from hiergoal.study_api import TransportError
from hiergoal.study_planning import plan_prompt, validate_plan
from hiergoal.study_protocol import canonical, digest
from hiergoal.study_scale import ScaleTask


class Scripted:
    kind = 'scripted'

    def __init__(self, replies):
        self.replies, self.requests = list(replies), []

    def respond(self, role, payload, *, max_output_tokens):
        self.requests.append((role, copy.deepcopy(payload), max_output_tokens))
        if not self.replies:
            raise AssertionError('Unexpected extra request')
        response = self.replies.pop(0)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


def reply(value, *, input_tokens=100, output_tokens=100):
    return {'text': canonical(value), 'input_tokens': input_tokens, 'output_tokens': output_tokens,
            'usage': {'input_tokens': input_tokens, 'output_tokens': output_tokens},
            'elapsed_seconds': 0.0, 'status': 'completed', 'model': 'OFFLINE_ORACLE',
            'simulated': True, 'response_id': None}


class ControlledRecoveryRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_manifest(backend='oracle')
        cls.pair = cls.manifest['pairs'][0]
        cls.task = make_task(cls.pair['task'])
        cls.raw_plan = {'instructions': {g: 'Satisfy the requirement: ' + d for g, d in cls.task.gates.items()}}
        cls.plan = validate_plan(cls.raw_plan, cls.task)
        cls.correct = cls.task.reference_solution()
        cls.checkpoint = make_checkpoint(cls.task, cls.plan, cls.correct,
                         pair_id=cls.pair['pair_id'], protocol_id=cls.manifest['protocol_id'],
                         source_trace_sha256='a' * 64)

    def repair(self, arm, backend, manifest=None):
        trial = next(t for t in self.manifest['trials'] if t['pair_id'] == self.pair['pair_id'] and t['arm'] == arm)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        out = Path(temp.name)
        result = run_phase(out, trial, manifest or self.manifest, backend, phase='repair', checkpoint=self.checkpoint)
        events = [json.loads(line) for line in (out / 'trace.jsonl').read_text().splitlines()]
        return result, events

    def patch_response(self, **kwargs):
        return reply({'patch': self.correct, 'explanation': 'Repair the corrupted artifact from current specifications.'}, **kwargs)

    def test_identical_forks_empty_history_and_costed_revision(self):
        fixed_backend = Scripted([self.patch_response()])
        adaptive_backend = Scripted([
            reply({'diagnosis': 'The public gate rejected the corrupted field.',
                   'revised_instruction': 'Recompute the failed field using the authoritative public specification.'}),
            self.patch_response(),
        ])
        fixed, fixed_events = self.repair('fixed', fixed_backend)
        adaptive, adaptive_events = self.repair('adaptive', adaptive_backend)
        self.assertEqual(fixed_events[0]['state'], adaptive_events[0]['state'])
        for backend in (fixed_backend, adaptive_backend):
            payload = backend.requests[0][1]
            self.assertEqual(payload['history'], [])
            self.assertEqual(payload['artifact'], self.checkpoint['failed_solution'])
            for forbidden in ('source_solution', 'source_hidden_grade', 'fault_receipt', 'checkpoint'):
                self.assertNotIn(forbidden, payload)
        self.assertEqual([x[0] for x in fixed_backend.requests], ['execute'])
        self.assertEqual([x[0] for x in adaptive_backend.requests], ['replan', 'execute'])
        self.assertEqual((fixed['status'], adaptive['status']), ('PASS', 'PASS'))
        self.assertEqual((fixed['calls'], adaptive['calls']), (1, 2))
        self.assertEqual((fixed['input_tokens'], adaptive['input_tokens']), (100, 200))
        self.assertEqual(fixed['final_plan'], self.plan)
        target = self.checkpoint['target_leaf_id']
        changed = [k for k in self.plan['leaves'] if self.plan['leaves'][k] != adaptive['final_plan']['leaves'][k]]
        self.assertEqual(changed, [target])

    def test_rejected_revision_consumes_one_attempt_and_preserves_plan(self):
        backend = Scripted([reply({'diagnosis': 'Invalid global rewrite', 'revised_instruction': 'short',
                                   'root': 'Changed objective'}), self.patch_response()])
        result, events = self.repair('adaptive', backend)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual((result['replan_attempts'], result['replans'], result['rejected_actions']), (1, 0, 1))
        self.assertEqual(result['final_plan'], self.plan)
        self.assertEqual([x[0] for x in backend.requests], ['replan', 'execute'])
        self.assertEqual([e['outcome']['type'] for e in events if e['type'] == 'response'], ['rejected', 'patch'])

    def test_over_budget_correct_response_is_charged_but_not_applied(self):
        backend = Scripted([self.patch_response(input_tokens=64000, output_tokens=100)])
        result, _ = self.repair('fixed', backend)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['diagnostic'], 'TOKEN_BUDGET_AFTER')
        self.assertEqual(result['input_tokens'] + result['output_tokens'], 64100)
        self.assertEqual(result['final_solution'], self.checkpoint['failed_solution'])
        self.assertEqual(result['patch_actions'], 0)

    def test_transport_failure_counts_request_with_unknown_usage_and_no_retry(self):
        backend = Scripted([TransportError('OPENAI_HTTP_429', evidence={'http_status': 429})])
        result, events = self.repair('adaptive', backend)
        self.assertEqual(result['status'], 'UNCERTAIN')
        self.assertTrue(result['stop_batch'])
        self.assertEqual((result['calls'], result['replan_attempts']), (1, 1))
        self.assertIsNone(result['input_tokens'])
        self.assertIsNone(result['output_tokens'])
        self.assertEqual(result['known_input_tokens'], 0)
        self.assertEqual(len(backend.requests), 1)
        self.assertEqual(len([e for e in events if e['type'] == 'request_failed']), 1)

    def test_stalled_repair_terminates_at_call_limit(self):
        bad = reply({'patch': self.checkpoint['failed_solution'], 'explanation': 'Return the unchanged failed artifact.'})
        backend = Scripted([bad] * 8)
        result, _ = self.repair('fixed', backend)
        self.assertEqual((result['status'], result['diagnostic'], result['calls']), ('FAIL', 'CALL_BUDGET_BEFORE', 8))
        self.assertFalse(result['success'])

    def test_source_generation_and_repair_never_call_reference_solution(self):
        backend = Scripted([reply(self.raw_plan), self.patch_response()])
        with tempfile.TemporaryDirectory() as temp, patch.object(ScaleTask, 'reference_solution', side_effect=AssertionError('Reference leakage')):
            source = run_phase(Path(temp), self.pair, self.manifest, backend, phase='prepare')
            self.assertEqual(source['status'], 'PASS')
            cp = make_checkpoint(make_task(self.pair['task']), source['final_plan'], source['final_solution'],
                                 pair_id=self.pair['pair_id'], protocol_id=self.manifest['protocol_id'],
                                 source_trace_sha256=source['trace_final_sha256'])
            self.assertEqual(cp['failed_solution'], self.checkpoint['failed_solution'])
            repair, _ = self.repair('fixed', Scripted([self.patch_response()]))
            self.assertEqual(repair['status'], 'PASS')
        self.assertIsNone(backend.requests[1][1]['plan'])
        self.assertIsNone(backend.requests[1][1]['current_leaf'])

    def test_invalid_initial_plan_is_not_regenerated(self):
        backend = Scripted([reply({'instructions': {}})])
        with tempfile.TemporaryDirectory() as temp:
            result = run_phase(Path(temp), self.pair, self.manifest, backend, phase='prepare')
        self.assertEqual((result['status'], result['diagnostic'], result['calls']), ('FAIL', 'INVALID_PLAN', 1))
        self.assertEqual(len(backend.requests), 1)
        self.assertFalse(result['stop_batch'])

    def test_false_success_claim_cannot_replace_grading(self):
        claim = reply({'success': True, 'patch': {}, 'explanation': 'Everything is complete.'})
        result, _ = self.repair('fixed', Scripted([claim] * 8))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['patch_actions'], 0)
        self.assertEqual(result['rejected_actions'], 8)
        self.assertEqual(result['final_artifact_sha256'], self.checkpoint['failed_solution_sha256'])


if __name__ == '__main__':
    unittest.main()
