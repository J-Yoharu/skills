"""Shared I/O, strict parsers, safe paths and command execution."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "dist"}


class ToolError(ValueError):
    """An actionable validation or operation failure, not an internal traceback."""


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ToolError(message)


def slug(value: str) -> str:
    require(isinstance(value, str) and 1 <= len(value) <= 64 and SLUG.fullmatch(value),
            f"Invalid skill slug: {value!r}; use lowercase-kebab-case, max 64 characters.")
    return value


def stable_version(value: str) -> str:
    require(isinstance(value, str) and SEMVER.fullmatch(value),
            f"Invalid stable SemVer: {value!r}. This repository uses MAJOR.MINOR.PATCH.")
    return value


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolError(f"{path}: {exc}") from exc


def json_text(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def atomic_write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(text.encode("utf-8") if isinstance(text, str) else text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path: Path, data: Any) -> None:
    atomic_write(path, json_text(data))


class StrictLoader(yaml.SafeLoader):
    """Safe YAML with duplicate-key rejection and YAML-1.2-style booleans."""


StrictLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in values if tag != "tag:yaml.org,2002:bool"]
    for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.I), list("tTfF"))


def _mapping(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        require(isinstance(key, str), "YAML mapping keys must be strings.")
        require(key not in result, f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(text: str, label: str = "YAML") -> Any:
    try:
        # Anchors/aliases are unnecessary in these configuration files; reject cycles and bombs.
        for token in yaml.scan(text):
            require(not isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)),
                    f"{label}: YAML anchors and aliases are not allowed.")
        return yaml.load(text, Loader=StrictLoader)
    except yaml.YAMLError as exc:
        raise ToolError(f"{label}: invalid YAML: {exc}") from exc


def validate_schema(root: Path, name: str, value: Any, label: str) -> None:
    schema = load_json(root / "schemas" / f"{name}.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda err: str(list(err.path)))
    if errors:
        details = "; ".join(f"{'/'.join(map(str, err.path)) or '$'}: {err.message}" for err in errors[:8])
        raise ToolError(f"{label}: {details}")


def inside(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def local_path(base: Path, value: str, *, must_exist: bool = True) -> Path:
    require(value and "\x00" not in value and "\\" not in value, f"Invalid relative path: {value!r}")
    require(not PurePosixPath(value).is_absolute() and not re.match(r"^[A-Za-z]:", value),
            f"Absolute path not allowed: {value}")
    target = base / value
    require(inside(base, target), f"Path escapes skill: {value}")
    if must_exist:
        require(target.exists(), f"Missing file or directory: {value}")
    return target


def file_list(base: Path, *, skip_dev: bool = False) -> list[Path]:
    result = []
    require(base.is_dir() and not base.is_symlink(), f"Not a real directory: {base}")
    for parent, directories, files in os.walk(base, followlinks=False):
        if skip_dev:
            directories[:] = [item for item in directories if item not in SKIP_DIRS]
        for item in list(directories):
            require(not (Path(parent) / item).is_symlink(), f"Symlink not allowed: {Path(parent) / item}")
        for item in files:
            path = Path(parent) / item
            require(not path.is_symlink(), f"Symlink not allowed: {path}")
            require(path.is_file(), f"Non-regular file not allowed: {path}")
            result.append(path)
    return sorted(result)


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None,
        timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(command, cwd=cwd, env=env, timeout=timeout, check=False,
                                text=True, encoding="utf-8", errors="replace",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"Command failed: {command[0]}: {exc}") from exc
    if check and result.returncode:
        raise ToolError(f"Command exited {result.returncode}: {command!r}\n{result.stderr[-6000:]}\n{result.stdout[-2000:]}")
    return result


@contextlib.contextmanager
def mutation_lock(root: Path) -> Iterator[None]:
    path = root / ".repository.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ToolError("Another tooling mutation is running. Remove stale .repository.lock only after checking.") from exc
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(f"pid={os.getpid()}\n")
        yield
    finally:
        path.unlink(missing_ok=True)


@contextlib.contextmanager
def rollback_files(paths: list[Path]) -> Iterator[None]:
    previous = {path: path.read_bytes() if path.exists() else None for path in paths}
    try:
        yield
    except Exception:
        for path, value in previous.items():
            if value is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, value)
        raise


def output_github(values: dict[str, Any]) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    require(output, "GITHUB_OUTPUT is not set.")
    with open(output, "a", encoding="utf-8") as stream:
        for key, value in values.items():
            require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key), "Invalid output key")
            rendered = json.dumps(value, separators=(",", ":")) if not isinstance(value, str) else value
            require("\n" not in rendered and "\r" not in rendered, "Multiline output not allowed.")
            stream.write(f"{key}={rendered}\n")
