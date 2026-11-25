# SPDX-License-Identifier: Apache-2.0
"""Deterministic, lossless transport compaction and strict initial-plan format."""
from __future__ import annotations

import copy
import hashlib
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


WIRE_GUIDANCE = (
    "When task_inherits_root_contract is present, the listed omitted task keys "
    "have exactly the corresponding root_contract values. When root_contract_aliases "
    "is present, each omitted top-level key has the value of the named root_contract key. "
    "Interpret the data exactly as if these fields were expanded. "
)


def wire_input(role, payload):
    value = {"role": role, **copy.deepcopy(payload)}
    reserved = {"task_inherits_root_contract", "root_contract_aliases"}
    if reserved.intersection(value):
        raise ValueError("Reserved wire field in logical request")
    root, task = value.get("root_contract"), value.get("task")
    if not isinstance(root, dict):
        return value
    if isinstance(task, dict):
        inherited = sorted(k for k, v in task.items()
                           if k in root and canonical(v) == canonical(root[k]))
        if inherited:
            value["task_inherits_root_contract"] = inherited
            for k in inherited:
                del task[k]
    aliases = {}
    for key, source in (("gates", "gates"), ("gate_dependencies", "dependencies")):
        if key in value and source in root and canonical(value[key]) == canonical(root[source]):
            aliases[key] = source
            del value[key]
    if aliases:
        value["root_contract_aliases"] = aliases
    return value


def expand_wire(value):
    """Inverse used for tests; no inference or state changes."""
    result = copy.deepcopy(value)
    root = result.get("root_contract", {})
    for k in result.pop("task_inherits_root_contract", []):
        result["task"][k] = copy.deepcopy(root[k])
    for k, source in result.pop("root_contract_aliases", {}).items():
        result[k] = copy.deepcopy(root[source])
    return result


def _object(properties):
    return {"type": "object", "properties": properties,
            "required": sorted(properties), "additionalProperties": False}


def response_format(role, payload):
    gates = payload.get("gates")
    if role != "plan" or not isinstance(gates, dict) or not gates:
        return {"type": "json_object"}
    string = {"type": "string"}
    root = payload.get("root_contract", {})
    hierarchy = root.get("hierarchy") if isinstance(root, dict) else None
    if isinstance(hierarchy, dict) and "gate_parents" in hierarchy:
        schema = _object({"instructions": _object({gate: string for gate in sorted(gates)})})
    else:
        leaf = _object({"id": string, "instruction": string,
                        "checks": {"type": "array", "items": {"type": "string", "enum": sorted(gates)}},
                        "depends_on": {"type": "array", "items": string}})
        milestone = _object({"id": string, "title": string,
                             "subgoals": {"type": "array", "items": leaf}})
        schema = _object({"milestones": {"type": "array", "items": milestone}})
    return {"type": "json_schema", "name": "hiergoal_initial_plan",
            "strict": True, "schema": schema}


def wire_metadata(role, payload):
    encoded = canonical(wire_input(role, payload)).encode("utf-8")
    fmt = canonical(response_format(role, payload)).encode("utf-8")
    return {"input_sha256": hashlib.sha256(encoded).hexdigest(),
            "input_bytes": len(encoded),
            "format_sha256": hashlib.sha256(fmt).hexdigest()}
