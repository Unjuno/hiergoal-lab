# Conformance to Hermes Issue #156054

Specification: https://github.com/NousResearch/hermes-agent/issues/156054

This research repository is an **experimental prototype of the proposed behavior**, not the upstream Hermes implementation. The H-JEPA paper motivates hierarchical planning but does not establish LLM-agent benefits.

## Requirement-by-requirement status

| Issue contract | Implementation | Status |
|---|---|---|
| User owns root objective and acceptance criteria | `ROOT_GOAL` plus fixed deterministic `GATES` | Implemented for one fixed coding experiment; arbitrary user-supplied goals still missing |
| Agent generates mid-/short-horizon goals | `build_plan_prompt` and validated `milestones`/`leaves` | Implemented with a fixed three-level tree, not arbitrary optional hierarchy depth |
| Inspectable parent, dependencies, status, verification, evidence, revision reason | `core.py`, `state.json`, gate evidence files, superseded leaves | Implemented for this prototype |
| Leaf success requires evidence | `grade()` executes external acceptance tests | Implemented for fixture |
| **Parent success requires independent evidence** | `_verify_parent_contracts()` reruns aggregate acceptance gates even when children are complete | Implemented with regression-triggered leaf replanning; validated offline |
| Root success requires independent evidence | `finish()` checks final independent test suite and validated parent contracts | Implemented for fixture |
| Local bounded replanning with root authority preserved | `_replan_leaf` and `replace_failed_leaf` rewire dependents | Implemented for leaf gate or parent regression failures; external assumption-change detection is not implemented |
| Persistence and interruption handling | `state.json`, `records.json`, durable streams, lock and manual-verified resume | Implemented as **external** persisted state, not Hermes `state_meta` |
| Reuse Hermes `/goal`, `/subgoal` and Kanban execution ledger | Controller runs Hermes CLI but manages a separate experimental state/schedule | **Not yet implemented.** This is the key architectural gap |
| Opt-in optional feature with unchanged flat `/goal` behavior | No changes are applied to Hermes' internal feature switches | Not implemented upstream; normal Hermes behavior is unaffected because prototype is separate |
| Controlled quantitative comparison | User elected one real-task observational case instead of baseline/30-task study | Not attempted; no claim about performance improvement is possible |

## Research protocol

The task itself is a Python CSV-ledger repair fixture. This is only a reproducible workload. It is not the core research idea. The relevant behavior is **root ownership → adaptive hierarchy → executable subgoal selection → evidence-based child and parent verification → minimal local replan → persistence**.

Offline CI tests validate the controller using **fake Hermes CLI outputs** and independent Python tests. No actual Hermes model run, tool-use capability, or provider billing claim follows from CI PASS.

The repository supports an explicit direct OpenAI API Luna route (`--backend luna --approve-paid-api`) and an optional OpenCode Free ACP route (`--backend free`). The model route is recorded per run; neither backend has completed a live model-inference experiment in CI. Model choice is not part of the Issue #156054 mechanism.

## Publication rule

Do not report the proposal as implemented in Hermes upstream. Results can inform the issue after a live run with full trace and evaluation evidence; native `/goal`/Kanban integration requires separate implementation and tests.
