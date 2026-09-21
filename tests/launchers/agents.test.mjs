/** Structural contracts only; these do not start Codex or Claude Code sessions. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, lstatSync, mkdtempSync, mkdirSync, writeFileSync, rmSync, readdirSync } from 'node:fs';
import { join, basename } from 'node:path';
import { tmpdir } from 'node:os';
import { ROOT, launcherTestFiles } from '../../scripts/run.mjs';
const text = name => readFileSync(join(ROOT, name), 'utf8');

test('Claude uses a native standalone import of the canonical AGENTS.md', () => {
  assert.equal(text('CLAUDE.md').split('\n')[0], '@AGENTS.md');
  assert.equal((text('CLAUDE.md').match(/^@/gm) ?? []).length, 1);
  assert.ok(text('CLAUDE.md').length < 512, 'Keep the adapter minimal, not a second rule set.');
  assert.ok(!lstatSync(join(ROOT, 'CLAUDE.md')).isSymbolicLink());
});
test('shared policy is a tracked plain file with review, reuse, and verification rules', () => {
  assert.ok(!lstatSync(join(ROOT, 'AGENTS.md')).isSymbolicLink());
  for (const heading of ['Start with discovery and reuse', 'Product boundaries', 'Language and compatibility',
    'Commands and dependencies', 'Implementation and evidence', 'Versioning, authorization, and safety',
    'Code Review Rules', 'Completion report']) assert.ok(text('AGENTS.md').includes(`## ${heading}`));
  assert.ok(Buffer.byteLength(text('AGENTS.md')) < 12288, 'Do not fill agent context with a growing command catalog.');
  assert.doesNotMatch(text('AGENTS.md'), /^@CLAUDE\.md/m, 'Do not create an import cycle.');
});
test('Make invokes runtimes directly and pnpm cannot call back into Make', () => {
  const scripts = JSON.parse(text('package.json')).scripts;
  for (const value of Object.values(scripts)) assert.doesNotMatch(value, /\b(?:g?make)\b/);
  assert.doesNotMatch(text('Makefile'), /"\$\$PNPM" run/);
  for (const action of ['validate', 'new', 'activate', 'fingerprint', 'build', 'isolate', 'ci-check', 'test-skills']) {
    assert.ok(text('Makefile').includes(`-m scripts ${action}`), `Missing native Python command: ${action}`);
  }
  assert.match(text('Makefile'), /"\$\$NODE" --test/);
  assert.match(text('Makefile'), /"\$\$BOOTSTRAP_PYTHON" scripts\/bootstrap\.py/);
  assert.match(text('scripts/run.mjs'), /scripts\/bootstrap\.py/);
  assert.doesNotMatch(text('scripts/run.mjs'), /'pip', 'install'/, 'Bootstrap implementation is shared, not copied into Node.');
});
test('Make recipes retain tab indentation', () => {
  assert.match(text('.editorconfig'), /\[Makefile\]\s+indent_style = tab/);
  assert.doesNotMatch(text('Makefile'), /^ +@/m);
});
test('instruction files are not inserted into the distributed starter skill', () => {
  const paths = readdirSync(join(ROOT, 'skills/orquestrar'));
  assert.ok(!paths.includes('AGENTS.md')); assert.ok(!paths.includes('CLAUDE.md'));
});
test('launcher discovery finds future test files and ignores non-test files/directories', t => {
  const directory = mkdtempSync(join(tmpdir(), 'launcher-discovery-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const tests = join(directory, 'tests/launchers'); mkdirSync(tests, { recursive: true });
  for (const name of ['z.test.mjs', 'a.test.mjs', 'README.md']) writeFileSync(join(tests, name), '');
  mkdirSync(join(tests, 'not-a-file.test.mjs'));
  assert.deepEqual(launcherTestFiles(directory), [join(tests, 'a.test.mjs'), join(tests, 'z.test.mjs')]);
});
test('all current launcher files are discovered without editing the runner', () => {
  const names = launcherTestFiles().map(name => basename(name));
  for (const name of ['run.test.mjs', 'make.test.mjs', 'agents.test.mjs']) assert.ok(names.includes(name));
  assert.doesNotMatch(text('scripts/run.mjs'), /tests\/launchers\/run\.test\.mjs/);
});
