#!/usr/bin/env python3
"""Show one subagent role's model/effort policy from the catalog.

The current chat is the coordinator, never a routing target.
Does not spawn, change the parent session, check availability, install configuration
or claim execution. Legacy catalog roles for the coordinator are ignored, not applied.
"""
from __future__ import annotations
import argparse
import copy
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


def role_config(catalog: dict, harness: str, role: str, overrides: dict) -> tuple[dict, dict, list]:
    """Merge trusted overrides into one harness/role policy without mutating the catalog."""
    for name, source in (("Catalog", catalog), ("Overrides", overrides)):
        require_subagent_scope(source, name)
    if not isinstance(role, str) or role.strip().lower() in COORDINATOR_ROLES:
        raise RouteError("Coordinator is the current session; only subagent roles can be queried")
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
        available = sorted(key for key in config["roles"]
                           if key.strip().lower() not in COORDINATOR_ROLES)
        raise RouteError(f"Unknown role {role!r} for {harness}. Valid subagent roles: {', '.join(available)}")
    policy = config["roles"][role]
    replacement = roles_override.get(role, {})
    if not isinstance(replacement, dict):
        raise RouteError("role override must be an object")
    policy.update(replacement)
    return config, policy, warnings


def policy_view(catalog: dict, harness: str, role: str, overrides: dict | None = None) -> dict:
    config, policy, warnings = role_config(catalog, harness, role, overrides or {})
    families = {choice["family"] for choice in policy["choices"]}
    # Frontier families need authorization in any role; overrides cannot drop that.
    catalog_frontier = catalog["harnesses"][harness]["roles"].get("frontier", {}).get("choices", [])
    if role == "frontier" or families & {choice.get("family") for choice in catalog_frontier}:
        policy["opt_in"] = True
    return {"status": "policy_only", "target": "subagent", "harness": harness,
            "role": role, "policy": policy,
            "bindings": {f: config["bindings"][f] for f in sorted(families)},
            "model_field": config["model_field"], "effort_field": config["effort_field"],
            "warnings": warnings, "availability": "unverified", "effective": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[1] / "assets/model-catalog.json")
    parser.add_argument("--role", required=True, help="Subagent role only; coordinator/current session cannot be routed")
    parser.add_argument("--harness", required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--show-policy", action="store_true", help="Accepted for existing invocations; policy display is the only mode")
    args = parser.parse_args()
    try:
        overrides = read(args.overrides) if args.overrides else None
        # A project profile keeps model policy under sections.models; accept it directly.
        if overrides and isinstance(overrides.get("sections"), dict):
            overrides = overrides["sections"].get("models", {})
        result = policy_view(read(args.catalog), args.harness, args.role, overrides)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RouteError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
