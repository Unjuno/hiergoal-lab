# SPDX-License-Identifier: Apache-2.0
"""Deterministic scale and locality fixtures for the bounded mechanism study.

Each task composes independent instances of one existing domain.  Domain
artifacts and graders remain substantive: expressions use the bounded AST
interpreter, records use integer cents, and schedules use the finite calendar.
Every additional grouping level has an executable certification gate, whose
artifact names its direct prerequisites and the component environment revision.
The grader verifies those prerequisites; a string claiming success never passes.

The prescribed hierarchy measures operation at a known depth, not discovery of
an optimal hierarchy.  Increasing depth adds certification leaves, so it is not
a fixed-leaf causal intervention.  Dense graphs explicitly list more direct
prerequisites within a component; independent components remain disconnected.
Certificates are engineering checks, not extra independent domain observations.

No submission is executed as Python, and reference_solution is offline only.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any

from hiergoal.study_tasks import FAMILIES, SPLITS, Task, make_task as make_domain_task


SCALE_LEVELS = {"small": 2, "medium": 4, "large": 8}
DEPTH_LEVELS = (3, 4, 5)
DENSITIES = ("sparse", "dense")
SCALE_SETTINGS = (
    {"size": "small", "depth": 3, "density": "sparse"},
    {"size": "medium", "depth": 3, "density": "sparse"},
    {"size": "large", "depth": 3, "density": "sparse"},
    {"size": "small", "depth": 4, "density": "sparse"},
    {"size": "small", "depth": 5, "density": "sparse"},
    {"size": "small", "depth": 3, "density": "dense"},
    {"size": "large", "depth": 5, "density": "dense"},
)


def _all_pass(grades: dict) -> bool:
    return bool(grades) and all(item["passed"] for item in grades.values())


def _same_json(left: Any, right: Any) -> bool:
    """Equality for the bounded JSON contract, rejecting bool-as-int aliases."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _same_json(left[key], value) for key, value in right.items()
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            _same_json(a, b) for a, b in zip(left, right)
        )
    return type(left) in (str, int, bool, type(None)) and left == right


def _descendants(dependencies: dict[str, list[str]], target: str) -> list[str]:
    if target not in dependencies:
        raise ValueError("Unknown dependency target")
    affected = {target}
    while True:
        expanded = affected | {
            gate for gate, prerequisites in dependencies.items()
            if any(dependency in affected for dependency in prerequisites)
        }
        if expanded == affected:
            return [gate for gate in dependencies if gate in affected]
        affected = expanded


def topology_stats(hierarchy: dict, dependencies: dict[str, list[str]]) -> dict:
    """Compute structural measurements from the actual graph, not scale labels.

    Depth is the number of edges from G0.  Density divides the number of direct
    leaf dependency edges by n*(n-1)/2, the maximum for an ordered acyclic graph.
    Tree edges and dependency edges are counted separately.
    """
    if (type(hierarchy) is not dict or set(hierarchy) != {
            "groups", "gate_parents", "depth_levels"}
            or type(hierarchy["groups"]) is not list
            or type(hierarchy["gate_parents"]) is not dict
            or type(dependencies) is not dict or not dependencies):
        raise ValueError("Malformed scale hierarchy or dependency graph")
    groups = {}
    for item in hierarchy["groups"]:
        if (type(item) is not dict or set(item) != {"id", "parent", "title"}
                or type(item["id"]) is not str or not item["id"] or item["id"] == "G0"
                or item["id"] in groups or type(item["parent"]) is not str
                or type(item["title"]) is not str or not item["title"].strip()):
            raise ValueError("Malformed scale group")
        groups[item["id"]] = item
    if set(hierarchy["gate_parents"]) != set(dependencies):
        raise ValueError("Hierarchy must cover every gate exactly once")
    depths, visiting = {"G0": 0}, set()

    def group_depth(group: str) -> int:
        if group in depths:
            return depths[group]
        if group not in groups or group in visiting:
            raise ValueError("Cyclic or dangling scale hierarchy")
        visiting.add(group)
        depths[group] = group_depth(groups[group]["parent"]) + 1
        visiting.remove(group)
        return depths[group]

    for group in groups:
        group_depth(group)
    children = {group: 0 for group in groups}
    for group in groups.values():
        if group["parent"] != "G0":
            children[group["parent"]] += 1
    leaf_depths = []
    for gate, group in hierarchy["gate_parents"].items():
        if (type(gate) is not str or not gate or gate in groups
                or type(group) is not str or group not in groups):
            raise ValueError("Every leaf must have a known grouping parent")
        children[group] += 1
        leaf_depths.append(group_depth(group) + 1)
    if not groups or any(count == 0 for count in children.values()):
        raise ValueError("Scale groups cannot be empty")
    visiting, visited = set(), set()

    def visit(gate: str) -> None:
        if gate in visited:
            return
        if gate not in dependencies or gate in visiting:
            raise ValueError("Cyclic or dangling scale dependency")
        visiting.add(gate)
        prerequisites = dependencies[gate]
        if (type(prerequisites) is not list
                or any(type(item) is not str for item in prerequisites)
                or len(set(prerequisites)) != len(prerequisites)):
            raise ValueError("Malformed direct dependencies")
        for dependency in prerequisites:
            visit(dependency)
        visiting.remove(gate)
        visited.add(gate)

    for gate in dependencies:
        visit(gate)
    leaf_count = len(dependencies)
    edges = sum(len(values) for values in dependencies.values())
    maximum = leaf_count * (leaf_count - 1) // 2
    depth = max(leaf_depths)
    if (type(hierarchy["depth_levels"]) is not int
            or hierarchy["depth_levels"] != depth + 1):
        raise ValueError("Declared scale depth differs from the actual tree")
    return {
        "leaf_count": leaf_count,
        "group_count": len(groups),
        "goal_count": 1 + len(groups) + leaf_count,
        "max_depth": depth,
        "depth_levels": depth + 1,
        "depth_unit": "edges_from_root",
        "tree_edges": len(groups) + leaf_count,
        "dependency_edges": edges,
        "dependency_density": edges / maximum if maximum else 0.0,
        "independent_branch_count": sum(
            item["parent"] == "G0" for item in groups.values()
        ),
    }


class ScaleTask:
    """Task-compatible composite with immutable contracts and local faults."""

    def __init__(self, family: str, instance: int, split: str, seed: int,
                 *, scale: str, depth: int, density: str):
        if family not in FAMILIES or split not in SPLITS:
            raise ValueError("Unknown task family or split")
        if type(instance) is not int or instance < 0 or type(seed) is not int:
            raise ValueError("Instance must be nonnegative and seed an integer")
        if (type(scale) is not str or scale not in SCALE_LEVELS
                or type(depth) is not int or depth not in DEPTH_LEVELS
                or type(density) is not str or density not in DENSITIES):
            raise ValueError("Unknown scale size, hierarchy depth, or density")
        digest = hashlib.sha256(
            f"hiergoal-scale-v1:{family}:{split}:{seed}:{instance}:{scale}:{depth}:{density}".encode()
        ).hexdigest()
        # Component definitions are paired across the size/depth/density factors.
        # No condition, arm, or submitted artifact enters any component seed.
        self._components: dict[str, Task] = {
            f"c{index + 1:02d}": make_domain_task(
                family, instance * max(SCALE_LEVELS.values()) + index, split, seed
            ) for index in range(SCALE_LEVELS[scale])
        }
        self._perturbations = 0
        self._subgoal_faults = 0
        self._gate_components, self._domain_gates, self._certificates = {}, {}, {}
        self._gate_fields, self._field_components = {}, {}
        gates, dependencies, shapes, groups, parents = {}, {}, {}, [], {}
        component_contracts = {}
        for cid, component in self._components.items():
            contract = component.root_contract
            component_contracts[cid] = contract
            group_ids = []
            for level in range(depth - 2):
                gid = f"M{len(groups) + 1}"
                groups.append({
                    "id": gid,
                    "parent": "G0" if not group_ids else group_ids[-1],
                    "title": f"Verify component {cid} at grouping level {level + 1}",
                })
                group_ids.append(gid)
            component_gates = []
            for local, description in component.gates.items():
                gate = f"{cid}_{local}"
                gates[gate] = f"Component {cid}: {description}"
                self._gate_components[gate] = cid
                self._domain_gates[gate] = local
                parents[gate] = group_ids[-1]
                dependencies[gate] = (
                    component_gates[:] if density == "dense" else
                    [f"{cid}_{item}" for item in component.dependencies[local]]
                )
                component_gates.append(gate)
                if family == "code_repair":
                    self._gate_fields[gate] = [gate]
                    shapes[gate] = contract["solution_shape"]["expressions"][local]
                elif family == "data_transform":
                    self._gate_fields[gate] = [gate]
                    shapes[gate] = contract["solution_shape"][local]
                else:
                    field = f"{cid}_assignments"
                    self._gate_fields[gate] = [field]
                    shapes[field] = contract["solution_shape"]["assignments"]
            for level in range(1, depth - 1):
                gate = f"{cid}_certify_{level}"
                prerequisites = (component_gates[:] if density == "dense"
                                 else [component_gates[-1]])
                gates[gate] = (
                    f"Certify component {cid} grouping level {level}: provide its current "
                    "environment_revision and checked_gates in the published direct "
                    "dependency order. Every referenced gate must actually pass."
                )
                self._gate_components[gate] = cid
                self._certificates[gate] = cid
                self._gate_fields[gate] = [gate]
                dependencies[gate] = prerequisites
                parents[gate] = group_ids[-level]
                shapes[gate] = {
                    "environment_revision": "nonnegative integer, current component revision",
                    "checked_gates": prerequisites[:],
                }
                component_gates.append(gate)
            for gate in component_gates:
                for field in self._gate_fields[gate]:
                    self._field_components[field] = cid
        self._hierarchy = {"groups": groups, "gate_parents": parents, "depth_levels": depth}
        self._contract = {
            "task_id": f"scale-{family}-{split}-{instance:03d}-{scale}-d{depth}-{density}-{digest[:8]}",
            "family": family, "split": split, "seed": seed, "instance": instance,
            "instance_seed": int(digest[:16], 16), "contract_version": 1,
            "objective": "Satisfy every domain and certification gate against the current component environments.",
            "environment_policy": "An environment update changes one component only. Task objectives, hierarchy, and acceptance rules remain fixed.",
            "benchmark_scope": "Prescribed-hierarchy bounded scale fixture; domain gates and certification gates are not independent task observations.",
            "scale": {"size": scale, "depth": depth, "density": density},
            "gates": gates, "dependencies": dependencies,
            "solution_shape": shapes, "hierarchy": copy.deepcopy(self._hierarchy),
            "gate_artifact_fields": copy.deepcopy(self._gate_fields),
            "domain_gates": list(self._domain_gates),
            "certification_gates": list(self._certificates),
            "component_contracts": component_contracts,
            "composition_rules": [
                "Prefix all artifact fields with the component ID. For code_repair, each stage expression is a separate prefixed field, without an expressions wrapper.",
                "Grade each component with its published domain rules. A gate passes only when its own artifact and every declared prerequisite pass.",
                "Certification fields have exactly environment_revision and checked_gates. The integer must equal the current component revision; checked_gates must exactly equal that gate's ordered direct prerequisites.",
                "Additional direct dependencies are explicit verification obligations. Dense and sparse variants may have the same transitive closure; density is a direct-edge burden, not a claim of additional independent information.",
                "Independent components have no cross-component dependencies or shared resources; same-named jobs and resources in distinct components are separate namespaces.",
                "Increasing prescribed depth adds executable certification leaves. It does not hold the leaf count fixed or demonstrate autonomous hierarchy discovery.",
            ],
        }
        self._contract["topology"] = self.topology_stats()

    @property
    def task_id(self) -> str:
        return self._contract["task_id"]

    @property
    def family(self) -> str:
        return self._contract["family"]

    @property
    def split(self) -> str:
        return self._contract["split"]

    @property
    def root_contract(self) -> dict:
        return copy.deepcopy(self._contract)

    @property
    def gates(self) -> dict[str, str]:
        return copy.deepcopy(self._contract["gates"])

    @property
    def dependencies(self) -> dict[str, list[str]]:
        return copy.deepcopy(self._contract["dependencies"])

    @property
    def scale_config(self) -> dict:
        return copy.deepcopy(self._contract["scale"])

    @property
    def hierarchy_spec(self) -> dict:
        return copy.deepcopy(self._hierarchy)

    @property
    def gate_artifact_fields(self) -> dict[str, list[str]]:
        return copy.deepcopy(self._gate_fields)

    @property
    def gate_artifact_paths(self) -> dict[str, list[list[str]]]:
        return {gate: [[field] for field in fields] for gate, fields in self._gate_fields.items()}

    def topology_stats(self) -> dict:
        stats = topology_stats(self._hierarchy, self._contract["dependencies"])
        stats.update({
            "component_count": len(self._components),
            "domain_gate_count": len(self._domain_gates),
            "certification_gate_count": len(self._certificates),
        })
        return stats

    def _environment(self) -> dict:
        return {
            "components": {
                cid: component.public_spec()["environment"]
                for cid, component in self._components.items()
            },
            "component_revisions": {
                cid: component.public_spec()["environment_revision"]
                for cid, component in self._components.items()
            },
        }

    def public_spec(self) -> dict:
        spec = self.root_contract
        spec["environment"] = self._environment()
        spec["environment_revision"] = self._perturbations
        if self.family == "code_repair":
            spec["public_probes"] = {
                cid: component.public_spec()["public_probes"]
                for cid, component in self._components.items()
            }
        return spec

    def _component_artifact(self, solution: dict, cid: str) -> dict:
        if self.family == "code_repair":
            return {"expressions": {
                local: solution.get(f"{cid}_{local}")
                for local in self._components[cid].gates
            }}
        return {
            field: solution.get(f"{cid}_{field}")
            for field in self._components[cid].root_contract["solution_shape"]
        }

    def _flatten_artifact(self, artifact: dict, cid: str) -> dict:
        contents = artifact["expressions"] if self.family == "code_repair" else artifact
        return {f"{cid}_{key}": copy.deepcopy(value) for key, value in contents.items()}

    def _certificate(self, gate: str) -> dict:
        cid = self._certificates[gate]
        return {
            "environment_revision": self._components[cid].public_spec()["environment_revision"],
            "checked_gates": self._contract["dependencies"][gate][:],
        }

    def initial_solution(self) -> dict:
        result = {}
        for cid, component in self._components.items():
            result.update(self._flatten_artifact(component.initial_solution(), cid))
        result.update({gate: {"environment_revision": 0, "checked_gates": []}
                       for gate in self._certificates})
        return result

    def reference_solution(self) -> dict:
        """Offline apparatus oracle; this must not enter a live prompt."""
        result = {}
        for cid, component in self._components.items():
            result.update(self._flatten_artifact(component.reference_solution(), cid))
        result.update({gate: self._certificate(gate) for gate in self._certificates})
        return result

    def grade(self, solution: dict, *, hidden: bool = False) -> dict[str, dict]:
        gates = self._contract["gates"]
        if type(solution) is not dict or set(solution) != set(self._contract["solution_shape"]):
            return {gate: {"passed": False, "message": "Expected exactly the published namespaced artifact fields."}
                    for gate in gates}
        raw = {}
        for cid, component in self._components.items():
            raw.update({
                f"{cid}_{gate}": result
                for gate, result in component.grade(
                    self._component_artifact(solution, cid), hidden=hidden
                ).items()
            })
        for gate in self._certificates:
            passed = _same_json(solution[gate], self._certificate(gate))
            raw[gate] = {
                "passed": passed,
                "message": "Current component certification passed." if passed else
                           "Certification revision or checked prerequisites are invalid.",
            }
        # Construction is topological; every dependency is earlier in its branch.
        graded = {}
        for gate in gates:
            own = raw[gate]
            prerequisites_pass = all(
                graded[dependency]["passed"]
                for dependency in self._contract["dependencies"][gate]
            )
            graded[gate] = {
                "passed": own["passed"] and prerequisites_pass,
                "message": own["message"] if prerequisites_pass else
                           "At least one authoritative prerequisite has not passed.",
            }
        return graded

    def artifact_projection(self, solution: dict, gates: list[str]) -> dict:
        """Copy the actual fields owned by gates; overlapping ownership is explicit."""
        if (type(solution) is not dict or type(gates) is not list
                or any(type(gate) is not str or gate not in self._gate_fields for gate in gates)):
            raise ValueError("Projection requires known gate IDs")
        fields = {field for gate in gates for field in self._gate_fields[gate]}
        if not fields.issubset(solution):
            raise ValueError("Projection is missing a required artifact field")
        return {field: copy.deepcopy(solution[field]) for field in sorted(fields)}

    def affected_gates(self, target: str) -> list[str]:
        return _descendants(self._contract["dependencies"], target)

    def _fault_receipt(self, *, kind: str, perturbation_type: str, target: str,
                       cid: str, before_solution: dict, after_solution: dict,
                       before_environment: dict, changed_fields: list[str],
                       domain_delivered: bool, raw_after: dict) -> dict:
        before_grade = self.grade(before_solution)
        # Environment faults need the pre-update verdict supplied by their caller.
        after_grade = self.grade(after_solution)
        affected = self.affected_gates(target)
        unaffected = [gate for gate in self.gates if gate not in affected]
        return {
            "kind": kind, "perturbation_type": perturbation_type,
            "target_component": cid, "target_gate": target,
            "affected_gates": affected, "unaffected_gates": unaffected,
            "changed_fields": changed_fields,
            "delivered": domain_delivered,
            "domain_fault_delivered": domain_delivered,
            "certification_invalidated": any(
                not after_grade[gate]["passed"] for gate in self._certificates
            ),
            "status": "delivered" if domain_delivered else "perturbation_no_impact",
            "seed": self._contract["seed"], "instance_seed": self._contract["instance_seed"],
            "environment_revision": self._perturbations,
            "environment_before": copy.deepcopy(before_environment),
            "environment_after": self._environment(),
            "before_grade": before_grade, "after_grade": after_grade,
            "raw_domain_after_grade": copy.deepcopy(raw_after),
            "unaffected_artifacts_unchanged": _same_json(
                self.artifact_projection(before_solution, unaffected),
                self.artifact_projection(after_solution, unaffected),
            ),
            "unrelated_component_gates": [
                gate for gate in self.gates if self._gate_components[gate] != cid
            ],
            "subgoal_fault_count": self._subgoal_faults,
        }

    def inject_fault(self, solution: dict) -> tuple[dict, dict]:
        """Persistently update one component; preserve every submitted artifact.

        A stale certificate alone does not count as a delivered domain fault.
        Robust parameterized expressions and schedules retain an explicit
        perturbation_no_impact classification even if recertification is needed.
        """
        before_grade = self.grade(solution)
        if not _all_pass(before_grade):
            raise ValueError("An environment update requires a public all-pass solution")
        cids = list(self._components)
        cid = cids[(self._contract["instance_seed"] + self._perturbations) % len(cids)]
        before_environment = self._environment()
        component = self._components[cid]
        _, component_info = component.inject_fault(self._component_artifact(solution, cid))
        self._perturbations += 1
        after_solution = copy.deepcopy(solution)
        target = f"{cid}_{component_info['target_gate']}"
        changed = [
            f"environment.components.{cid}." + field.removeprefix("environment.")
            for field in component_info["changed_fields"]
        ]
        changed.append(f"environment.component_revisions.{cid}")
        info = self._fault_receipt(
            kind=component_info["kind"], perturbation_type="environment", target=target,
            cid=cid, before_solution=solution, after_solution=after_solution,
            before_environment=before_environment, changed_fields=changed,
            domain_delivered=component_info["delivered"],
            raw_after={f"{cid}_{gate}": value
                       for gate, value in component_info["after_grade"].items()},
        )
        info["before_grade"] = before_grade
        return after_solution, info

    def inject_subgoal_fault(self, solution: dict) -> tuple[dict, dict]:
        """Corrupt one substantive domain artifact without changing any environment.

        The corruption is predetermined from task metadata.  It is followed by
        an actual public pass-to-fail check; this is not a certificate-only fault.
        """
        if not _all_pass(self.grade(solution)):
            raise ValueError("A forced subgoal fault requires a public all-pass solution")
        cids = list(self._components)
        cid = cids[(self._contract["instance_seed"] + self._subgoal_faults) % len(cids)]
        after_solution = copy.deepcopy(solution)
        before_environment = self._environment()
        if self.family == "code_repair":
            target = f"{cid}_base"
            after_solution[target] = "0"
            changed = [target]
        elif self.family == "data_transform":
            target = f"{cid}_rows"
            after_solution[target][0]["net_cents"] += 1
            changed = [target]
        else:
            target = f"{cid}_assignments"
            after_solution[target][0]["start"] = -1
            changed = [target]
        self._subgoal_faults += 1
        component_grades = self._components[cid].grade(
            self._component_artifact(after_solution, cid)
        )
        if component_grades[self._domain_gates[target]]["passed"]:
            raise RuntimeError("Forced domain fault failed its pass-to-fail check")
        info = self._fault_receipt(
            kind="forced_subgoal", perturbation_type="subgoal", target=target, cid=cid,
            before_solution=solution, after_solution=after_solution,
            before_environment=before_environment, changed_fields=changed,
            domain_delivered=True,
            raw_after={f"{cid}_{gate}": value for gate, value in component_grades.items()},
        )
        return after_solution, info


def make_task(family: str, instance: int, split: str = "heldout", seed: int = 1729,
              *, scale: str = "small", depth: int = 3, density: str = "sparse") -> ScaleTask:
    """Create a reproducible composite without inference, network, or external I/O."""
    return ScaleTask(family, instance, split, seed, scale=scale, depth=depth, density=density)
