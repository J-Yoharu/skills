import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ROOT, PINNED_PNPM, environmentPython, checkPackageManager } from '../../scripts/run.mjs';

function fixture(t, withPython = false) {
  const directory = mkdtempSync(join(tmpdir(), 'skill-launcher-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  mkdirSync(join(directory, 'scripts'));
  for (const name of ['package.json', '.python-version']) copyFileSync(join(ROOT, name), join(directory, name));
  copyFileSync(join(ROOT, 'scripts/run.mjs'), join(directory, 'scripts/run.mjs'));
  copyFileSync(join(ROOT, 'scripts/bootstrap.py'), join(directory, 'scripts/bootstrap.py'));
  if (withPython) {
    const bin = join(directory, '.venv/bin');
    mkdirSync(bin, { recursive: true });
    // Fake only the child process; this test verifies argv/cwd routing, not Python behavior.
    writeFileSync(join(bin, 'python'), '#!/usr/bin/env node\nconsole.log(JSON.stringify({argv:process.argv.slice(2),cwd:process.cwd()}));\n', { mode: 0o755 });
  }
  return directory;
}
function invoke(directory, args, options = {}) {
  return spawnSync(process.execPath, [join(directory, 'scripts/run.mjs'), ...args], {
    encoding: 'utf8', cwd: tmpdir(), shell: false, ...options,
  });
}

test('accepts the pinned pnpm user agent', () => {
  assert.doesNotThrow(() => checkPackageManager(`pnpm/${PINNED_PNPM} npm/? node/v22.16.0 linux x64`));
});
test('rejects npm as the repository package manager', () => {
  assert.throws(() => checkPackageManager('npm/11.0.0 node/v22.16.0'), /Use pnpm/);
});
test('rejects a different pnpm version', () => {
  assert.throws(() => checkPackageManager('pnpm/10.0.0 npm/?'), /Use pnpm/);
});
test('rejects an ambiguous matching prefix', () => {
  assert.throws(() => checkPackageManager(`pnpm/${PINNED_PNPM}9 npm/?`), /Use pnpm/);
});
test('rejects a missing user agent', () => {
  assert.throws(() => checkPackageManager(''), /Use pnpm/);
});
test('selects the Unix venv interpreter', () => {
  assert.equal(environmentPython('/fixture', 'linux'), join('/fixture', '.venv/bin/python'));
});
test('selects the Windows venv interpreter', () => {
  assert.equal(environmentPython('/fixture', 'win32'), join('/fixture', '.venv/Scripts/python.exe'));
});
test('missing environment has an actionable English error', t => {
  const result = invoke(fixture(t), ['validate']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Missing local Python environment\. Run make bootstrap or pnpm bootstrap first/);
});
test('package-manager guard does not require a Python environment', t => {
  const result = invoke(fixture(t), ['check-package-manager'], {
    env: { ...process.env, npm_config_user_agent: `pnpm/${PINNED_PNPM} npm/?` },
  });
  assert.equal(result.status, 0, result.stderr);
});
test('an existing bootstrap lock is preserved and blocks bootstrap', t => {
  const directory = fixture(t);
  writeFileSync(join(directory, '.bootstrap.lock'), 'existing owner');
  const result = invoke(directory, ['bootstrap']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Another bootstrap is running/);
  assert.equal(readFileSync(join(directory, '.bootstrap.lock'), 'utf8'), 'existing owner');
});
test('arguments with spaces and metacharacters remain literal argv', { skip: process.platform === 'win32' }, t => {
  const directory = fixture(t, true);
  const args = ['new', 'example-skill', '--display-name', 'Example ; echo not-a-shell $(pwd)'];
  const result = invoke(directory, args);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout).argv, ['-m', 'scripts', ...args]);
});
test('launcher uses its checkout root from an unrelated directory', { skip: process.platform === 'win32' }, t => {
  const directory = fixture(t, true);
  const result = invoke(directory, ['validate']);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).cwd, directory);
});


test('optional reference bootstrap requires the development environment first', t => {
  const result = invoke(fixture(t), ['bootstrap-reference']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /before installing optional reference dependencies/);
});
test('reference bootstrap respects the shared bootstrap lock', t => {
  const directory = fixture(t);
  writeFileSync(join(directory, '.bootstrap.lock'), 'existing owner');
  const result = invoke(directory, ['bootstrap-reference']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Another bootstrap is running/);
});
test('reference bootstrap routes only its pinned requirements and checks dependencies', { skip: process.platform === 'win32' }, t => {
  const directory = fixture(t, true);
  const result = invoke(directory, ['bootstrap-reference']);
  assert.equal(result.status, 0, result.stderr);
  const calls = result.stdout.split('\n').filter(line => line.startsWith('{')).map(line => JSON.parse(line).argv);
  assert.deepEqual(calls[1], ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements-reference.txt']);
  assert.deepEqual(calls[2], ['-m', 'pip', 'check']);
});


test('test-launchers discovers and executes tests without a Python environment', t => {
  const directory = fixture(t);
  mkdirSync(join(directory, 'tests/launchers'), { recursive: true });
  writeFileSync(join(directory, 'tests/launchers/future.test.mjs'), "import test from 'node:test'; import {writeFileSync} from 'node:fs'; test('future discovered test', () => writeFileSync(new URL('../future-ran', import.meta.url), 'executed'));\n");
  // Start a fresh test runner rather than inheriting the outer runner's IPC context.
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  const result = invoke(directory, ['test-launchers'], { env });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(readFileSync(join(directory, 'tests/future-ran'), 'utf8'), 'executed');
});
