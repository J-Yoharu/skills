/** Optional pnpm entry point. Make invokes runtimes directly; both reuse Python operations. No implicit installs, shell interpolation, or remote writes. */
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const PINNED_PNPM = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).packageManager.split('@')[1];
const PYTHON_MINOR = readFileSync(join(ROOT, '.python-version'), 'utf8').trim();

export function environmentPython(root = ROOT, platform = process.platform) {
  return join(root, '.venv', platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
}

export function checkPackageManager(agent = process.env.npm_config_user_agent ?? '') {
  if (!agent.startsWith(`pnpm/${PINNED_PNPM} `)) {
    throw new Error(`Use pnpm ${PINNED_PNPM}: npm install --global pnpm@${PINNED_PNPM}, then pnpm install --frozen-lockfile.`);
  }
}

function execute(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: ROOT, stdio: 'inherit', shell: false, ...options });
  if (result.error) throw new Error(`Could not execute ${command}: ${result.error.message}`);
  if (result.signal) throw new Error(`${command} was terminated by ${result.signal}`);
  if (result.status !== 0) throw new Error(`${command} exited with status ${result.status}`);
}

function systemPython() {
  const candidates = process.platform === 'win32'
    ? [['py', [`-${PYTHON_MINOR}`]], ['python', []]]
    : [[`python${PYTHON_MINOR}`, []], ['python3', []], ['python', []]];
  for (const [command, prefix] of candidates) {
    const result = spawnSync(command, [...prefix, '-c', 'import sys; print("%s.%s" % sys.version_info[:2])'], {
      cwd: ROOT, encoding: 'utf8', shell: false,
    });
    if (result.status === 0 && result.stdout.trim() === PYTHON_MINOR) return [command, prefix];
  }
  throw new Error(`Install Python ${PYTHON_MINOR}; pnpm manages commands, not the Python runtime.`);
}

export function launcherTestFiles(root = ROOT) {
  return readdirSync(join(root, 'tests/launchers'), { withFileTypes: true })
    .filter(entry => entry.isFile() && entry.name.endsWith('.test.mjs'))
    .map(entry => entry.name)
    .sort()
    .map(name => join(root, 'tests/launchers', name));
}

export function launch(action, args = []) {
  if (action === 'check-package-manager') return checkPackageManager();
  if (action === 'test-launchers') return execute(process.execPath, ['--test', ...args, ...launcherTestFiles()]);
  const python = environmentPython();
  if (action === 'bootstrap' || action === 'bootstrap-reference') {
    const [command, prefix] = systemPython();
    execute(command, [...prefix, join(ROOT, 'scripts/bootstrap.py'),
      ...(action === 'bootstrap-reference' ? ['--reference'] : [])]);
    return;
  }
  if (!existsSync(python)) throw new Error('Missing local Python environment. Run make bootstrap or pnpm bootstrap first.');
  if (action === 'test') {
    execute(process.execPath, ['--test', ...launcherTestFiles()]);
    execute(python, ['-m', 'unittest', 'discover', '-s', 'tests/scripts', '-v', ...args]);
    return execute(python, ['-m', 'scripts', 'test-skills']);
  }
  if (action === 'check') execute(process.execPath, ['--test', ...launcherTestFiles()]);
  // Arguments remain individual argv values, including spaces and metacharacters.
  execute(python, ['-m', 'scripts', action, ...args]);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const [action = '--help', ...args] = process.argv.slice(2);
    launch(action, args);
  } catch (error) {
    console.error(`ERROR: ${error.message}`);
    process.exitCode = 1;
  }
}
