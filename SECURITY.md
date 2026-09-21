# Security

Do not post credentials, private prompts, customer data, or exploit details in public issues.
After configuring this repository, use its private security advisory channel when available;
otherwise contact the repository owner privately. Never invent a reporting address.

## Trust boundary

A skill is executable guidance and may contain executable scripts. Review content before
running it. Static imports, local-link checks, environment filtering, and copied-payload
smoke tests detect packaging errors; they are **not** an operating-system sandbox. They do
not block every file access, network request, computed import, subprocess, or malicious action.
Run untrusted contributions on disposable machines without secrets or network privileges.

PR CI uses read-only permissions and no repository secrets. Publishing is an explicit
write command and an opt-in workflow. The publisher validates artifacts against a clean
local tag, checks the remote tag, and preflights known asset/ref conflicts before writing.
GitHub writes are not transactional; a network failure can leave a partial release.
Never overwrite conflicting artifacts or force-move a published tag.

Human review evidence and its fingerprint are integrity checks, not a signature or proof
that a reviewer ran an agent. Protect default branches and review evidence changes.
Dependency pins limit unintended changes but do not guarantee safe dependencies. Python
requirements are version-pinned, not hash-locked; pnpm's lockfile does not cover them.
