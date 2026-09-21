"""Format, links, boundaries and repository contracts. Not a security sandbox."""
from __future__ import annotations

import ast
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

from .common import (
    ToolError, file_list, inside, load_json, load_yaml, local_path, require,
    stable_version, validate_schema,
)
from .repository import (
    DRAFT_MARKER, VERSION_MARKER, expected_release_config, registry, render_catalog,
    settings, skill_version,
)

FORMAT_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
BANNED_PARTS = {".git", ".github", ".venv", "node_modules", "__pycache__", ".pytest_cache", "tests", "tooling"}
CODE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".sh"}
TEXT_SUFFIXES = {".md", ".template", ".txt", ".json", ".yaml", ".yml", *CODE_SUFFIXES}


def frontmatter(path: Path) -> tuple[dict, str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolError(f"{path}: expected UTF-8 text: {exc}") from exc
    lines = text.splitlines(keepends=True)
    require(lines and lines[0].strip() == "---" and text.startswith("---"), f"{path}: missing YAML frontmatter.")
    end = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    require(end is not None, f"{path}: unclosed frontmatter.")
    data = load_yaml("".join(lines[1:end]), str(path))
    require(isinstance(data, dict), f"{path}: frontmatter must be a mapping.")
    body = "".join(lines[end + 1:]).strip()
    require(body, f"{path}: empty instructions.")
    return data, body, text


def check_format(path: Path, name: str, version: str, line_limit: int) -> dict:
    data, body, text = frontmatter(path)
    require(not (set(data) - FORMAT_FIELDS), f"{path}: unsupported frontmatter fields: {set(data) - FORMAT_FIELDS}")
    require(data.get("name") == name, f"{path}: name must equal directory name {name!r}.")
    description = data.get("description")
    require(isinstance(description, str) and 1 <= len(description.strip()) <= 1024,
            f"{path}: description must be a nonempty string of at most 1024 characters.")
    for optional, maximum in (("compatibility", 500), ("license", 1024), ("allowed-tools", 4096)):
        if optional in data:
            require(isinstance(data[optional], str) and 0 < len(data[optional]) <= maximum,
                    f"{path}: {optional} must be a string of 1..{maximum} characters.")
    metadata = data.get("metadata")
    require(isinstance(metadata, dict), f"{path}: repository policy requires metadata.version.")
    require(all(isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()),
            f"{path}: metadata must map strings to strings (quote booleans and versions).")
    require(metadata.get("version") == version, f"{path}: metadata.version != version.txt ({version}).")
    # The generic release updater must target exactly one line, not examples elsewhere.
    marker_lines = [line for line in text.splitlines() if VERSION_MARKER in line]
    require(len(marker_lines) == 1 and re.fullmatch(
        r'  version: "' + re.escape(version) + r'" # x-release-please-version', marker_lines[0]),
        f"{path}: preserve exactly:   version: \"{version}\" # {VERSION_MARKER}")
    require(len(text.splitlines()) <= line_limit, f"{path}: exceeds {line_limit} lines; split reference material.")
    return data


def without_fences(text: str) -> str:
    result = []
    fence: str | None = None
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            current = marker.group(1)
            if fence is None:
                fence = current
            elif current[0] == fence[0] and len(current) >= len(fence):
                fence = None
            result.append("")
        else:
            result.append(line if fence is None else "")
    return "\n".join(result)


class _HTMLLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.links.append(value)


def markdown_links(text: str) -> list[str]:
    """Recognize inline links, reference definitions and HTML href/src.

    This is intentionally not a complete CommonMark renderer. Complex constructs
    should use reference-style links. Code examples are not interpreted as links.
    """
    text = without_fences(text)
    result = []
    # Definitions catch both full and collapsed reference-style links.
    for match in re.finditer(r'^\s{0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))', text, re.M):
        result.append(match.group(1) or match.group(2))
    # Inline targets with balanced parentheses; escaped parens remain part of a filename.
    for match in re.finditer(r'!?\[[^\]\n]*\]\(', text):
        index, depth, chars, escaped = match.end(), 1, [], False
        while index < len(text) and depth:
            char = text[index]
            if escaped:
                chars.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "(":
                depth += 1
                chars.append(char)
            elif char == ")":
                depth -= 1
                if depth:
                    chars.append(char)
            else:
                chars.append(char)
            index += 1
        if depth == 0:
            target = "".join(chars).strip()
            if target.startswith("<") and ">" in target:
                target = target[1:target.index(">")]
            else:
                target = re.split(r'\s+["\']', target, maxsplit=1)[0]
            result.append(target)
    parser = _HTMLLinks()
    parser.feed(text)
    result.extend(parser.links)
    return result


def validate_links(skill_dir: Path, path: Path, text: str) -> None:
    for target in markdown_links(text):
        if not target or target.startswith("#"):
            continue
        parts = urlsplit(target)
        if parts.scheme in {"https", "http", "mailto"}:
            continue
        require(not parts.scheme and not parts.netloc, f"{path}: unsupported/absolute link: {target}")
        target_path = unquote(parts.path)
        require("\\" not in target_path and not target_path.startswith("/"), f"{path}: absolute link: {target}")
        resolved = path.parent / target_path
        require(inside(skill_dir, resolved), f"{path}: link escapes skill: {target}")
        require(resolved.exists(), f"{path}: broken local link: {target}")
    # Inline code references to bundled assets are checkable without interpreting shell commands.
    for target in re.findall(r'`((?:scripts|references|assets)/[^`\s]+)`', without_fences(text)):
        if not any(char in target for char in "*{}<>"):
            local_path(skill_dir, target)


def _python_imports(skill_dir: Path, path: Path, text: str) -> None:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise ToolError(f"{path}: Python syntax: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
                require(inside(skill_dir, base), f"{path}: relative import escapes skill.")
                continue
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            first = module.split(".")[0]
            require(first not in {"tooling", "tests"}, f"{path}: imports repository tooling/tests.")
            if first in sys.stdlib_module_names:
                continue
            # Check the complete module, not just a directory named "scripts".
            # Namespace packages are allowed, but a missing nested module is not.
            relative = Path(*module.split("."))
            candidates = [path.parent / relative.with_suffix(".py"), path.parent / relative,
                          skill_dir / relative.with_suffix(".py"), skill_dir / relative]
            require(any(item.exists() and inside(skill_dir, item) for item in candidates),
                    f"{path}: non-bundled import {module!r}; skills must not depend on dev/site packages.")


def _javascript_imports(skill_dir: Path, path: Path, text: str) -> None:
    # Conservative guardrails, not a JavaScript AST proof. Isolated execution is the second gate.
    targets = re.findall(r'''(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*|\bimport\s*)["']([^"']+)["']''', text)
    for target in targets:
        if target.startswith("node:"):
            continue
        require(target.startswith("."), f"{path}: use node: built-ins or bundled relative modules, not {target!r}.")
        resolved = path.parent / target
        require(inside(skill_dir, resolved), f"{path}: import escapes skill: {target}")
        candidates = [resolved, resolved.with_suffix(".js"), resolved.with_suffix(".mjs"), resolved / "index.js"]
        require(any(candidate.exists() for candidate in candidates), f"{path}: missing imported module: {target}")
    require(not re.search(r"\bimport\s*\(\s*(?![\s\"'])", text),
            f"{path}: computed imports need an explicit policy/test extension before release.")


def validate_files(skill_dir: Path, limits: dict) -> list[Path]:
    total = 0
    files = file_list(skill_dir)
    casefold_paths: set[str] = set()
    for path in files:
        relative = path.relative_to(skill_dir)
        key = relative.as_posix().casefold()
        require(key not in casefold_paths, f"Case-insensitive path collision: {relative}")
        casefold_paths.add(key)
        require(not (set(relative.parts) & BANNED_PARTS), f"Development-only content inside skill: {relative}")
        require(not any(part.startswith(".env") for part in relative.parts), f"Environment file inside skill: {relative}")
        require(path.suffix not in {".pem", ".key", ".pyc"}, f"Secret/cache file inside skill: {relative}")
        require(path.name != "SKILL.md" or path.parent == skill_dir, f"Nested SKILL.md: {relative}")
        require(not (path.name == "SKILL.md.template" and path.parent != skill_dir), f"Nested template: {relative}")
        size = path.stat().st_size
        total += size
        require(size <= limits["max_file_bytes"], f"File too large: {relative}")
        if path.suffix in TEXT_SUFFIXES or path.name in {"LICENSE", "SKILL.md.template"}:
            text = path.read_text(encoding="utf-8")
            require("\x00" not in text, f"Binary/NUL content in text file: {relative}")
            require(not re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text),
                    f"Private key material found: {relative}")
            if path.suffix in {".md", ".template"}:
                validate_links(skill_dir, path, text)
            if path.suffix == ".py":
                _python_imports(skill_dir, path, text)
            if path.suffix in {".js", ".mjs", ".cjs"}:
                _javascript_imports(skill_dir, path, text)
            if path.suffix in CODE_SUFFIXES:
                require(not re.search(r"(?:\.\./){2,}(?:tooling|tests|catalog|skills)\b", text),
                        f"Repository runtime dependency found: {relative}")
    require(total <= limits["max_skill_bytes"], "Skill exceeds configured total size limit.")
    return files


def validate_evals(root: Path, item: dict, *, active: bool, skill_dir: Path | None = None) -> dict:
    path = root / "tests" / "skills" / item["name"] / "evals.json"
    data = load_json(path)
    validate_schema(root, "evals", data, str(path.relative_to(root)))
    require(data["skill"] == item["name"], f"{path}: skill name mismatch.")
    ids = [case["id"] for case in data["cases"]]
    require(len(set(ids)) == len(ids), f"{path}: duplicate case ids.")
    if active:
        require({case["should_trigger"] for case in data["cases"]} == {True, False},
                f"{path}: active skills require both positive and negative trigger cases.")
        require(data["review"]["status"] == "approved" and len(data["review"]["evidence"].strip()) >= 20,
                f"{path}: record an approved human evaluation with concrete evidence before activation.")
        from .fingerprints import payload_fingerprint
        expected = payload_fingerprint(skill_dir or root / "skills" / item["name"])
        require(data["review"].get("payload_sha256") == expected,
                f"{path}: reviewed payload has changed or its fingerprint is missing. Re-evaluate before recording new evidence.")
    return data


def validate_skill(root: Path, item: dict, *, skill_dir: Path | None = None) -> dict:
    config = settings(root)
    name = item["name"]
    active = item["status"] == "active"
    directory = skill_dir or root / "skills" / name
    expected = "SKILL.md" if active else "SKILL.md.template"
    wrong = "SKILL.md.template" if active else "SKILL.md"
    require((directory / expected).is_file(), f"{name}: expected {expected} for status {item['status']}.")
    require(not (directory / wrong).exists(), f"{name}: {wrong} disagrees with lifecycle status.")
    version = stable_version((directory / "version.txt").read_text(encoding="utf-8").strip())
    data = check_format(directory / expected, name, version, config["limits"]["max_skill_lines"])
    for filename in ("LICENSE", "CHANGELOG.md"):
        require((directory / filename).is_file() and (directory / filename).stat().st_size > 0,
                f"{name}: missing {filename}.")
    files = validate_files(directory, config["limits"])
    if active:
        for path in files:
            if path.suffix in {".md", ".template"}:
                text = path.read_text(encoding="utf-8")
                require(not re.search(r"\b(?:TODO|TBD|FIXME)\b|" + re.escape(DRAFT_MARKER), text),
                        f"{name}: unfinished placeholder in {path.name}; not ready for activation.")
    else:
        require(version == "0.0.0", f"{name}: unpublished drafts must remain at 0.0.0.")
    validate_evals(root, item, active=active, skill_dir=directory)
    entrypoints = item["entrypoints"]
    top_scripts = {path.relative_to(directory).as_posix() for path in files
                   if path.parent == directory / "scripts" and path.suffix in CODE_SUFFIXES}
    require(top_scripts <= set(entrypoints), f"{name}: register script entrypoints: {sorted(top_scripts - set(entrypoints))}")
    for point in entrypoints:
        require(local_path(directory, point).is_file(), f"{name}: entrypoint must be a file: {point}")
        require(any(f"{{skill}}/{point}" in smoke["command"] for smoke in item["smoke_tests"]),
                f"{name}: no isolated smoke test for {point}.")
    test_names: set[str] = set()
    for smoke in item["smoke_tests"]:
        require(smoke["name"] not in test_names, f"{name}: duplicate smoke test name.")
        test_names.add(smoke["name"])
        command = smoke["command"]
        require(command[0] in {"python", "node", "bash"}, "Smoke executables: python, node or bash only.")
        require(command[1] in {f"{{skill}}/{point}" for point in entrypoints},
                f"{name}: command must execute an explicit bundled entrypoint as its second argument.")
        require("stdout_contains" in smoke, f"{name}: assert stdout_contains; exit code alone is insufficient.")
        for argument in command:
            for token in re.findall(r"\{([^{}]+)\}", argument):
                require(token in {"skill", "work"}, f"Unsupported smoke placeholder: {{{token}}}")
    return {"name": name, "status": item["status"], "version": version,
            "files": len(files), "description": data["description"]}


def validate_repository(root: Path) -> list[dict]:
    config = settings(root)
    items = registry(root)
    names = {item["name"] for item in items}
    skill_root = root / "skills"
    directories = {path.name for path in skill_root.iterdir() if path.is_dir()}
    require(directories == names, f"Unregistered or missing skill directories: {sorted(directories ^ names)}")
    require(not any(path.is_file() for path in skill_root.iterdir()), "Files directly under skills/ are not allowed.")
    expected_paths = {f"skills/{item['name']}/SKILL.md" for item in items if item["status"] == "active"}
    found = {path.relative_to(root).as_posix() for path in file_list(root, skip_dev=True) if path.name == "SKILL.md"}
    require(found == expected_paths, f"Unexpected discoverable SKILL.md files: {sorted(found ^ expected_paths)}")
    results = [validate_skill(root, item) for item in items]
    actual_config = load_json(root / "release-please-config.json")
    require(actual_config == expected_release_config(root), "Release config drift. Run: make release-sync")
    manifest = load_json(root / ".release-please-manifest.json")
    expected_manifest = {".": stable_version((root / "version.txt").read_text(encoding="utf-8").strip())}
    expected_manifest.update({f"skills/{item['name']}": skill_version(root, item["name"])
                              for item in items if item["status"] == "active"})
    require(manifest == expected_manifest, "Release manifest and component versions differ. Do not silently reset versions.")
    require((root / "docs/CATALOG.md").read_text(encoding="utf-8") == render_catalog(root),
            "Generated catalog drift. Run: make catalog-update")
    # Syntax checks for repository-owned Python/JSON/YAML. Never execute YAML or eval JSON.
    for directory in (root / "scripts", root / "tests/scripts", root / "schemas", root / ".github"):
        for path in file_list(directory, skip_dev=True):
            if path.suffix == ".py":
                try:
                    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                except SyntaxError as exc:
                    raise ToolError(f"{path}: {exc}") from exc
            elif path.suffix in {".yaml", ".yml"}:
                load_yaml(path.read_text(encoding="utf-8"), str(path))
            elif path.suffix == ".json":
                load_json(path)
    validate_documentation(root)
    return results


def validate_documentation(root: Path) -> None:
    """Check local file targets in maintained Markdown; not remote HTTP availability or anchors."""
    documents = list(root.glob("*.md"))
    for folder in (root / "docs", root / ".github", root / "tests" / "skills"):
        if folder.exists():
            documents.extend(folder.rglob("*.md"))
    for path in documents:
        require(not path.is_symlink(), f"Documentation symlink is not allowed: {path}")
        text = path.read_text(encoding="utf-8")
        for target in markdown_links(text):
            if not target or target.startswith("#"):
                continue
            parts = urlsplit(target)
            if parts.scheme in {"http", "https", "mailto"}:
                continue
            require(not parts.scheme and not parts.netloc, f"{path}: unsupported documentation link: {target}")
            local = unquote(parts.path)
            require(not local.startswith("/") and "\\" not in local, f"{path}: absolute documentation link: {target}")
            resolved = path.parent / local
            require(inside(root, resolved), f"{path}: documentation link escapes repository: {target}")
            require(resolved.exists(), f"{path}: broken documentation link: {target}")
