"""Usage: python -m scripts --help. No operation pushes unless publish-assets is requested."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .common import DEFAULT_ROOT, ToolError, atomic_write, json_text, mutation_lock, output_github, require, run
from .repository import activate_skill, configure, new_skill, registry, render_catalog, settings, sync_release_config
from .validation import validate_repository, validate_skill
from .isolation import isolate_skill
from .packaging import build
from .planning import changed_files, check_pr, plan, verify_metadata_only_diff


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Self-contained Agent Skills monorepo tooling")
    result.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (defaults to this checkout)")
    sub = result.add_subparsers(dest="action", required=True)
    config = sub.add_parser("configure", help="set GitHub identity; does not create or push a repository")
    config.add_argument("--github", required=True)
    config.add_argument("--codeowner")
    identity = sub.add_parser("verify-identity", help="compare local GitHub identity without network calls")
    identity.add_argument("--github", required=True)
    new = sub.add_parser("new", help="create a non-discoverable draft and its operational/test contracts")
    new.add_argument("name")
    new.add_argument("--display-name")
    activate = sub.add_parser("activate", help="promote a genuinely reviewed draft to an installable skill")
    activate.add_argument("name")
    sub.add_parser("sync", help="regenerate release config without resetting existing versions")
    catalog = sub.add_parser("catalog", help="render/update the documentation catalog")
    catalog.add_argument("--write", action="store_true")
    fingerprint = sub.add_parser("fingerprint", help="print the content fingerprint; does not approve or alter evaluation evidence")
    fingerprint.add_argument("name")
    sub.add_parser("validate", help="validate all repository and skill contracts without executing scripts")
    sub.add_parser("check", help="validation + maintenance/skill tests + isolated smoke tests + preview packaging")
    preview = sub.add_parser("preview-skill", help="materialize a local installable evaluation copy without activation")
    preview.add_argument("name")
    tested = sub.add_parser("test-skills", help="run registered deterministic skill suites, not LLM evaluations")
    tested.add_argument("--name")
    ci = sub.add_parser("ci-check", help="validate everything and execute regressions only for affected code")
    ci.add_argument("--base", default=os.environ.get("BASE_SHA"))
    ci.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
    isolate = sub.add_parser("isolate", help="copy skills outside the repository and run declared smoke tests")
    isolate.add_argument("--skills-json", help='explicit JSON list, e.g. ["orquestrar"]')
    isolate.add_argument("--shard-index", type=int)
    isolate.add_argument("--shard-count", type=int)
    isolate.add_argument("--base", default=os.environ.get("BASE_SHA"))
    isolate.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
    planned = sub.add_parser("plan", help="select changed skills and produce a bounded CI matrix")
    planned.add_argument("--base", default=os.environ.get("BASE_SHA"))
    planned.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
    planned.add_argument("--github-output", action="store_true")
    pr = sub.add_parser("check-pr", help="validate Conventional Commit title and payload bump intent")
    pr.add_argument("--title", default=os.environ.get("PR_TITLE", ""))
    pr.add_argument("--base", default=os.environ.get("BASE_SHA"))
    pr.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
    pr.add_argument("--branch", default=os.environ.get("PR_BRANCH", ""))
    active = sub.add_parser("has-active", help="report whether release-eligible skills exist")
    active.add_argument("--github-output", action="store_true")
    packed = sub.add_parser("build", help="build per-skill archives and catalog/checksums")
    packed.add_argument("--preview", action="store_true")
    packed.add_argument("--tag", default=os.environ.get("RELEASE_TAG"))
    packed.add_argument("--output", type=Path, default=Path("dist"))
    publish = sub.add_parser("publish-assets", help="EXPLICIT WRITE: upload artifacts and create immutable component tags on GitHub")
    publish.add_argument("--tag", required=True)
    publish.add_argument("--output", type=Path, default=Path("dist"))
    interop = sub.add_parser("interop", help="external reference/installer integration; needs extra dependencies/network")
    interop.add_argument("--reference-only", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.action == "configure":
            configure(root, args.github, args.codeowner)
            print("GitHub identity configured locally. No remote writes were performed.")
        elif args.action == "verify-identity":
            require(settings(root)["github"] == args.github,
                    "Repository identity mismatch. Run make configure REPO=OWNER/REPO with the exact target.")
            print("Configured GitHub identity matches the expected repository. No remote calls performed.")
        elif args.action == "new":
            new_skill(root, args.name, args.display_name)
            print(f"Created draft skills/{args.name}/SKILL.md.template. Nothing was published.")
        elif args.action == "activate":
            activate_skill(root, args.name)
            print(f"Activated {args.name} locally. Commit with feat({args.name}): ...; Release Please owns version bumps.")
        elif args.action == "sync":
            with mutation_lock(root):
                sync_release_config(root)
            print("Release configuration synchronized; existing versions preserved.")
        elif args.action == "catalog":
            text = render_catalog(root)
            if args.write:
                with mutation_lock(root):
                    atomic_write(root / "docs/CATALOG.md", text)
                print("Updated docs/CATALOG.md")
            else:
                print(text, end="")
        elif args.action == "fingerprint":
            from .fingerprints import payload_fingerprint
            from .repository import entry
            entry(root, args.name)
            print(payload_fingerprint(root / "skills" / args.name))
        elif args.action == "validate":
            print(json_text({"valid": True, "skills": validate_repository(root)}), end="")
        elif args.action == "isolate":
            items = registry(root)
            if args.skills_json is not None:
                selected = json.loads(args.skills_json)
                require(isinstance(selected, list) and all(isinstance(name, str) for name in selected),
                        "--skills-json must be a JSON list of skill names.")
                require(set(selected) <= {item["name"] for item in items}, "Unknown skill in isolation selection.")
                items = [item for item in items if item["name"] in selected]
            if args.shard_index is not None or args.shard_count is not None:
                require(args.skills_json is None, "Do not combine explicit skill names and shard selection.")
                require(args.shard_index is not None and args.shard_count is not None
                        and 0 <= args.shard_index < args.shard_count <= 64, "Invalid shard selection.")
                selected_plan = plan(root, args.base, args.head)
                require(args.shard_count == len(selected_plan["matrix"]["include"]), "Shard count differs from the plan.")
                selected = set(selected_plan["selected"][args.shard_index::args.shard_count])
                items = [item for item in items if item["name"] in selected]
            print(json_text([isolate_skill(root, item) for item in items]), end="")
        elif args.action == "plan":
            value = plan(root, args.base, args.head)
            if args.github_output:
                output_github({"matrix": value["matrix"], "has_skills": value["has_skills"], "maintenance": value["maintenance"]})
            print(json_text(value), end="")
        elif args.action == "check-pr":
            paths = changed_files(root, args.base, args.head)
            check_pr(args.title, paths, release_branch=args.branch.startswith("release-please--"),
                     metadata_only=verify_metadata_only_diff(root, args.base, args.head, paths))
            print("PR title and release intent validated.")
        elif args.action == "has-active":
            value = any(item["status"] == "active" for item in registry(root))
            if args.github_output:
                output_github({"active": value})
            print(json_text({"active": value}), end="")
        elif args.action == "build":
            output = args.output if args.output.is_absolute() else root / args.output
            print(json_text(build(root, output, preview=args.preview, tag=args.tag)), end="")
        elif args.action == "publish-assets":
            from .publishing import publish_assets
            output = args.output if args.output.is_absolute() else root / args.output
            print(json_text(publish_assets(root, args.tag, output)), end="")
        elif args.action == "interop":
            from .interoperability import check_interoperability
            validate_repository(root)
            print(json_text(check_interoperability(root, cli=not args.reference_only)), end="")
        elif args.action == "preview-skill":
            from .packaging import preview_skill
            print(json_text(preview_skill(root, args.name)), end="")
        elif args.action == "test-skills":
            from .testing import skill_tests
            print(json_text(skill_tests(root, [args.name] if args.name else None)), end="")
        elif args.action == "ci-check":
            from .testing import selective_check
            print(json_text(selective_check(root, args.base, args.head)), end="")
        elif args.action == "check":
            print("[1/4] Repository validation", flush=True)
            validate_repository(root)
            print("[2/4] Tooling regression tests", flush=True)
            from .testing import maintenance_tests, skill_tests
            maintenance_tests(root)
            skill_tests(root)
            print("[3/4] Copy-only skill checks", flush=True)
            for item in registry(root):
                print(json.dumps(isolate_skill(root, item), ensure_ascii=False))
            print("[4/4] Preview packaging (drafts excluded)", flush=True)
            value = build(root, root / "dist", preview=True)
            print(f"OK: {len(value['skills'])} active skill(s) packaged. No remote publication performed.")
        return 0
    except (ToolError, OSError, UnicodeError, json.JSONDecodeError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
