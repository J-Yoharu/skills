"""Deterministic review fingerprint of the distributed behavior, not a proof of evaluation."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
from .common import file_list


def payload_fingerprint(directory: Path) -> str:
    digest = hashlib.sha256(b"agent-skills-reviewed-payload-v1\0")
    paths = file_list(directory)
    paths.sort(key=lambda path: "SKILL.md" if path.relative_to(directory).as_posix() == "SKILL.md.template"
               else path.relative_to(directory).as_posix())
    for path in paths:
        relative = path.relative_to(directory).as_posix()
        if relative in {"version.txt", "CHANGELOG.md"} or path.name == ".gitkeep":
            continue
        if relative == "SKILL.md.template":
            relative = "SKILL.md"
        data = path.read_bytes()
        if relative == "SKILL.md":
            data = data.replace(b"\r\n", b"\n")
            data = re.sub(rb'^  version: "[0-9]+\.[0-9]+\.[0-9]+" # x-release-please-version$',
                          b'  version: "RELEASE-METADATA" # x-release-please-version', data, flags=re.M)
        encoded = relative.encode("utf-8")
        # Length-prefixed records prevent concatenation ambiguities.
        digest.update(len(encoded).to_bytes(8, "big")); digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return digest.hexdigest()
