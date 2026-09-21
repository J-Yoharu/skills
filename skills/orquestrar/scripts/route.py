#!/usr/bin/env python3
"""Resolve subagent model/effort from explicitly observed session capabilities.

The current chat is the coordinator, never a routing target.
Does not spawn, change the parent session, discover availability, install configuration
or claim execution. Legacy catalog roles for the coordinator are ignored, not applied.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys


class RouteError(ValueError):
    pass


# Reserved even when a project supplies a custom catalog or overrides.
COORDINATOR_ROLES = frozenset({
    "coordinate", "coordinator", "orchestrate", "orchestrator", "coordenador",
    "orquestrador", "main", "parent", "root", "current_session", "session",
})


def require_subagent_scope(source: dict, name: str) -> None:
    """Missing scope in v2.1 inputs remains compatible, but only for subagents."""
    if source.get("selection_scope", "subagents") != "subagents":
        raise RouteError(f"{name} selection_scope must be subagents; coordinator is the current session")


def read(path: Path) -> dict:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("object required")
        return result
    except (OSError, ValueError) as exc:
        raise RouteError(str(exc)) from exc


def time_of(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone required")
        return result
    except (AttributeError, TypeError, ValueError) as exc:
        raise RouteError("Invalid observed_at") from exc


def resolve(catalog: dict, runtime: dict, session_id: str, role: str,
            overrides: dict | None = None, allow_frontier: bool = False,
            now: datetime | None = None, *, target: str = "subagent") -> dict:
    # Enforce this boundary before any model lookup, including legacy catalogs.
    if target != "subagent":
        raise RouteError("Only subagent routing is allowed; coordinator is the current session")
    if not isinstance(role, str) or not role.strip():
        raise RouteError("A subagent role is required")
    if role.strip().lower() in COORDINATOR_ROLES:
        raise RouteError("Coordinator is the current session; its model and effort are not routed")
    overrides = overrides or {}
    for name, source in (("Catalog", catalog), ("Runtime", runtime), ("Overrides", overrides)):
        require_subagent_scope(source, name)
    now = now or datetime.now(timezone.utc)
    if catalog.get("schema_version") != 1 or runtime.get("schema_version") != 1:
        raise RouteError("Unsupported schema_version")
    if not session_id or runtime.get("session_id") != session_id:
        raise RouteError("Runtime inventory belongs to another session")
    age = now - time_of(runtime.get("observed_at"))
    if age > timedelta(hours=24) or age < timedelta(minutes=-5):
        raise RouteError("Runtime observation stale/future; reobserve before routing")
    if not runtime.get("evidence"):
        raise RouteError("Observed runtime requires evidence reference")
    harness = runtime.get("harness")
    if harness not in catalog.get("harnesses", {}):
        raise RouteError("No mapping for this harness; use generic adapter")
    config = copy.deepcopy(catalog["harnesses"][harness])
    # Overrides come from trusted, already-merged project policy, not remote text.
    bindings = overrides.get("bindings", {}).get(harness, {})
    if not isinstance(bindings, dict):
        raise RouteError("bindings override must be an object")
    config["bindings"].update(bindings)
    # Preserve older profiles without allowing their coordinator preferences to run.
    roles_override = overrides.get("role_overrides", {}).get(harness, {})
    if not isinstance(roles_override, dict):
        raise RouteError("role_overrides for harness must be an object")
    reserved = sorted({key for key in (*config["roles"], *roles_override)
                       if str(key).strip().lower() in COORDINATOR_ROLES})
    warnings = ([{"reason": "coordinator_roles_ignored", "roles": reserved}]
                if reserved else [])
    if role not in config["roles"]:
        raise RouteError("Unknown role")
    policy = config["roles"][role]
    replacement = roles_override.get(role, {})
    if not isinstance(replacement, dict):
        raise RouteError("role override must be an object")
    policy.update(replacement)
    if (role == "frontier" or policy.get("opt_in")) and not allow_frontier:
        return {"status": "authorization_required", "target": "subagent", "role": role,
                "reason": "frontier_opt_in", "warnings": warnings}
    choices = policy.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RouteError("choices must be a nonempty array")
    result = {"target": "subagent", "role": role, "harness": harness,
              "policy": catalog.get("policy_id"), "warnings": warnings,
              "session_id": session_id, "effective": {"model": None, "effort": None}}
    try:
        reviewed = datetime.fromisoformat(catalog["reviewed_on"]).replace(tzinfo=timezone.utc)
        result["policy_review_due"] = now - reviewed > timedelta(days=catalog.get("policy_refresh_days", 30))
    except (KeyError, ValueError, TypeError) as exc:
        raise RouteError("Invalid catalog review date") from exc
    if runtime.get("model_selection") is not True:
        return {**result, "status": "uncontrolled_inheritance", "parent": runtime.get("parent"),
                "reason": "No native model selection; validate parent capability before executing"}
    models = runtime.get("models")
    if not isinstance(models, list) or any(not isinstance(m, dict) or not isinstance(m.get("id"), str) for m in models):
        raise RouteError("models must be observed model objects")
    if len({m["id"] for m in models}) != len(models):
        raise RouteError("Duplicate model IDs in runtime")
    observed = {m["id"]: m for m in models}
    rejected = []
    for choice in choices:
        if not isinstance(choice, dict) or not isinstance(choice.get("family"), str):
            raise RouteError("Invalid choice")
        family = choice["family"]; effort = choice.get("effort")
        if family in {"fable", "astra"} and not allow_frontier:
            rejected.append({"family": family, "reason": "frontier_opt_in"}); continue
        ids = config["bindings"].get(family)
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
            raise RouteError(f"Unknown/invalid model family: {family}")
        if effort is not None and not isinstance(effort, str):
            raise RouteError("effort must be string or null")
        for model_id in ids:
            model = observed.get(model_id, {})
            if model.get("available") is not True or not model.get("evidence"):
                continue
            supported = model.get("supported_efforts")
            if effort is not None:
                if runtime.get("effort_selection") is not True:
                    rejected.append({"model": model_id, "reason": "effort_not_controllable"}); continue
                if not isinstance(supported, list) or effort not in supported:
                    rejected.append({"model": model_id, "reason": "effort_unsupported_or_unknown"}); continue
            native = {config["model_field"]: model_id}
            if effort is not None:
                native[config["effort_field"]] = effort
            return {**result, "status": "resolved", "requested": {"model": model_id, "effort": effort},
                    "native_fields": native, "rejected": rejected,
                    "next": "Apply only to a subagent through actual schema or matching registered agent; never change parent session; inspect effective metadata"}
    return {**result, "status": "configuration_required", "rejected": rejected,
            "reason": "No observed allowed choice supports the requested role/effort; no silent downgrade"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[1] / "assets/model-catalog.json")
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--role", required=True, help="Subagent role only; coordinator/current session cannot be routed")
    parser.add_argument("--target", choices=["subagent"], default="subagent",
                        help="Explicit routing boundary; the current session is never a target")
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--allow-frontier", action="store_true", help="Use only after explicit user authorization")
    args = parser.parse_args()
    try:
        result = resolve(read(args.catalog), read(args.runtime), args.session_id, args.role,
                         read(args.overrides) if args.overrides else None, args.allow_frontier, target=args.target)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "resolved" else 1
    except (RouteError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
