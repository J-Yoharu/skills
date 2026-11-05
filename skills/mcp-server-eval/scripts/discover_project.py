#!/usr/bin/env python3
"""Discovery: read the project before touching it, so the kit fits what already exists.

It only reads. It reports the test runner, the fixture and test folders, the CI, where
the MCP server seems to live, and signs of authentication, then suggests where the kit
should go. The result is a starting point to confirm with the person, not a decision.

Usage:
  discover_project.py --root .
  discover_project.py --root . --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__", "target", ".next", "coverage", ".mcp-eval", ".cache", "docs", ".claude", ".agents"}
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".php", ".go", ".rs", ".rb", ".java", ".kt", ".cs"}
MAX_FILES, MAX_BYTES = 4000, 200_000

RUNNER_FILES = {
    "pytest": ["pytest.ini", "conftest.py", "tox.ini"],
    "phpunit": ["phpunit.xml", "phpunit.xml.dist"],
    "go test": ["go.mod"],
    "cargo test": ["Cargo.toml"],
    "rspec": [".rspec"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
}
RUNNER_DEPENDENCIES = {"vitest": "vitest", "jest": "jest", "mocha": "mocha", "ava": "ava", "@playwright/test": "playwright", "pestphp/pest": "pest", "phpunit/phpunit": "phpunit", "pytest": "pytest"}
FIXTURE_DIRS = {"fixtures", "__fixtures__", "testdata", "factories", "seeds", "seeders"}
TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "e2e"}
MCP_DEPENDENCIES = {"@modelcontextprotocol/sdk", "mcp", "fastmcp", "laravel/mcp", "mcp-go", "rmcp", "modelcontextprotocol"}
MCP_CODE = re.compile(r"McpServer\(|FastMCP\(|Mcp::web\(|Mcp::local\(|server\.tool\(|registerTool\(|@mcp\.tool|mcp\.NewServer|Server\(\s*\{\s*name:")
AUTH_CODE = re.compile(r"oauth-protected-resource|oauth-authorization-server|code_challenge|WWW-Authenticate|resource_metadata", re.I)
AUTH_DEPENDENCIES = {"passport", "laravel/passport", "league/oauth2-server", "next-auth", "authlib", "django-oauth-toolkit", "oidc-provider", "keycloak", "auth0", "@auth0/auth0-spa-js", "spring-security-oauth2-authorization-server"}
GATES = {
    "vitest": "describe.skipIf", "jest": "describe.skipIf", "mocha": "describe.skipIf", "pytest": "pytest.mark.skipif",
    "phpunit": "PHPUnit group", "pest": "PHPUnit group", "go test": "go:build tag",
}


def walk(root: Path) -> list[Path]:
    files: list[Path] = []
    stack = [root]
    while stack and len(files) < MAX_FILES:
        for entry in sorted(stack.pop().iterdir(), key=lambda path: path.name):
            if entry.is_dir():
                if entry.name not in SKIP_DIRS and not entry.is_symlink():
                    stack.append(entry)
            else:
                files.append(entry)
    return files


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore") if path.stat().st_size <= MAX_BYTES else ""
    except OSError:
        return ""


def dependencies(files: list[Path]) -> set[str]:
    """Dependency names from the manifests of the usual stacks."""
    found: set[str] = set()
    for path in files:
        if path.name in ("package.json", "composer.json"):
            try:
                data = json.loads(read_text(path) or "{}")
            except ValueError:
                continue
            for key in ("dependencies", "devDependencies", "peerDependencies", "require", "require-dev"):
                found |= set(data.get(key) or {})
        elif path.name in ("requirements.txt", "requirements-dev.txt"):
            found |= {re.split(r"[=<>~\[ ;]", line.strip())[0].lower() for line in read_text(path).splitlines() if line.strip() and not line.startswith("#")}
        elif path.name == "pyproject.toml":
            found |= {match.lower() for match in re.findall(r'"([A-Za-z0-9_.-]+)[^"]*"', read_text(path))}
            if "[tool.pytest" in read_text(path):
                found.add("pytest")
        elif path.name == "go.mod" and "mcp" in read_text(path).lower():
            found.add("mcp-go")
    return found


def relative(root: Path, paths: list[Path]) -> list[str]:
    return sorted({str(path.relative_to(root)) for path in paths})


def from_root(root: Path, patterns: tuple[str, ...]) -> list[str]:
    """Look these up directly: a big repository can exhaust the walk before reaching them."""
    return relative(root, [path for pattern in patterns for path in root.glob(pattern) if path.is_file()])


def shared_depth(left: str, right: str) -> int:
    depth = 0
    for a, b in zip(Path(left).parts, Path(right).parts):
        if a != b:
            break
        depth += 1
    return depth


def suggest_target(mcp_code: list[str], fixture_dirs: list[str], test_dirs: list[str]) -> str:
    """Prefer a test or fixture folder close to the server, so the kit lives next to it."""
    near = mcp_code[0] if mcp_code else ""
    candidates = [folder for folder in fixture_dirs if any(part in TEST_DIRS or part.startswith("__") for part in Path(folder).parts)] + test_dirs
    if not candidates:
        return "tools/mcp-eval"
    best = max(candidates, key=lambda folder: (shared_depth(folder, near), -folder.count("/")))
    return f"{best}/mcp-golden"


def discover(root: Path) -> dict:
    files = walk(root)
    names = {path.name for path in files}
    deps = dependencies(files)
    runners = sorted({runner for runner, markers in RUNNER_FILES.items() if names & set(markers)} | {label for dep, label in RUNNER_DEPENDENCIES.items() if dep in deps})
    folders = {parent for path in files for parent in path.relative_to(root).parents if str(parent) != "."}
    fixture_dirs = sorted(str(folder) for folder in folders if folder.name in FIXTURE_DIRS)
    test_dirs = sorted(str(folder) for folder in folders if folder.name in TEST_DIRS)
    ci = from_root(root, (".github/workflows/*", ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml", ".circleci/*"))
    hooks = from_root(root, (".githooks/*", ".husky/*"))
    mcp_code, auth_code = [], []
    for path in files:
        in_tests = any(part in TEST_DIRS or part in FIXTURE_DIRS for part in path.relative_to(root).parts)
        if path.suffix in SOURCE_SUFFIXES and not in_tests and "test" not in path.name.lower():
            text = read_text(path)
            if MCP_CODE.search(text):
                mcp_code.append(path)
            if AUTH_CODE.search(text):
                auth_code.append(path)
    server_files = relative(root, mcp_code)
    return {
        "test_runners": runners,
        "gate_snippets": sorted({GATES[runner] for runner in runners if runner in GATES}),
        "test_folders": test_dirs[:10],
        "fixture_folders": fixture_dirs[:10],
        "ci": ci[:8],
        "git_hooks": hooks[:5],
        "mcp_config": from_root(root, (".mcp.json",)),
        "mcp_dependencies": sorted(deps & MCP_DEPENDENCIES),
        "mcp_server_code": server_files[:8],
        "auth_dependencies": sorted(deps & AUTH_DEPENDENCIES),
        "auth_code": relative(root, auth_code)[:8],
        "suggested_target": suggest_target(server_files, fixture_dirs, test_dirs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAILED: not a folder: {root}", file=sys.stderr)
        return 2
    result = discover(root)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    for key, value in result.items():
        print(f"{key}: {', '.join(value) if isinstance(value, list) and value else value or 'none found'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
