/** Executes GNU Make with recording runtimes; never contacts pnpm, GitHub, or an LLM. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { ROOT } from '../../scripts/run.mjs';
const options = { skip: process.platform === 'win32' };
function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), 'make native paths '));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  copyFileSync(join(ROOT, 'Makefile'), join(directory, 'Makefile'));
  mkdirSync(join(directory, 'tests/launchers'), { recursive: true });
  writeFileSync(join(directory, 'tests/launchers/a.test.mjs'), '');
  const log = join(directory, 'calls.jsonl');
  const commands = {};
  for (const kind of ['python', 'bootstrap', 'node', 'pnpm']) {
    commands[kind] = join(directory, `fake ${kind}`);
    writeFileSync(commands[kind], `#!/usr/bin/env node
import('node:fs').then(fs => {
  const args = process.argv.slice(2);
  fs.appendFileSync(process.env.CALL_LOG, JSON.stringify({kind:${JSON.stringify(kind)},args,cwd:process.cwd()})+'\\n'.replace('\\\\n','\\n'));
  if(process.env.FAIL_ON && args.includes(process.env.FAIL_ON)) process.exitCode=23;
});\n`, { mode: 0o755 });
  }
  return { directory, run(args, extra = {}) {
    if (existsSync(log)) rmSync(log);
    const env = { ...process.env, CALL_LOG: log, REPO: '', TAG: '', RELEASE_TAG: '', NAME: '', CODEOWNER: '', DISPLAY_NAME: '',
      SKILLS_JSON: '', SHARD_INDEX: '', SHARD_COUNT: '', CONFIRM_PUBLISH: '', GITHUB_REPOSITORY: '', ...extra };
    const result = spawnSync('make', ['--no-print-directory', '-C', directory,
      `PYTHON=${commands.python}`, `BOOTSTRAP_PYTHON=${commands.bootstrap}`, `NODE=${commands.node}`, `PNPM=${commands.pnpm}`, ...args],
      { cwd: tmpdir(), env, encoding: 'utf8', shell: false });
    result.calls = existsSync(log) ? readFileSync(log, 'utf8').trim().split('\n').filter(Boolean).map(s => JSON.parse(s)) : [];
    return result;
  }};
}
for (const args of [[], ['help']]) test(`help ${JSON.stringify(args)} needs no runtime`, options, t => {
  const result = fixture(t).run(args);
  assert.equal(result.status, 0, result.stderr); assert.deepEqual(result.calls, []); assert.match(result.stdout, /skill-preview/);
});
const commands = {
  validate: ['validate'], 'ci-check': ['ci-check'], plan: ['plan'], 'plan-ci': ['plan', '--github-output'],
  'check-pr': ['check-pr'], catalog: ['catalog'], 'catalog-update': ['catalog', '--write'],
  'release-sync': ['sync'], 'has-active': ['has-active'], 'has-active-ci': ['has-active', '--github-output'],
  interop: ['interop'], 'build-preview': ['build', '--preview', '--output', 'dist'], isolate: ['isolate'],
};
for (const [target, args] of Object.entries(commands)) test(`${target} directly executes the Python operation`, options, t => {
  const f=fixture(t), result=f.run([target]); assert.equal(result.status,0,result.stderr);
  assert.deepEqual(result.calls,[{kind:'python',args:['-m','scripts',...args],cwd:f.directory}]);
});
test('pnpm is used only for the explicit JavaScript install task', options, t => {
  const result=fixture(t).run(['install']); assert.equal(result.status,0,result.stderr);
  assert.deepEqual(result.calls.map(c=>[c.kind,...c.args]),[['pnpm','install','--frozen-lockfile']]);
});
for(const target of ['setup','bootstrap']) test(`${target} uses the stdlib bootstrap, without Node or pnpm`,options,t=>{
  const result=fixture(t).run(['-j8',target]); assert.equal(result.status,0,result.stderr);
  assert.deepEqual(result.calls.map(c=>[c.kind,...c.args]),[['bootstrap','scripts/bootstrap.py']]);
});
test('optional reference bootstrap uses the same Python implementation',options,t=>{
  const result=fixture(t).run(['bootstrap-reference']);
  assert.deepEqual(result.calls[0].args,['scripts/bootstrap.py','--reference']); assert.equal(result.calls[0].kind,'bootstrap');
});
test('Make runs Node tests directly with shell discovery',options,t=>{
  const result=fixture(t).run(['test-launchers']);
  assert.deepEqual(result.calls[0].args,['--test','tests/launchers/a.test.mjs']); assert.equal(result.calls[0].kind,'node');
});
test('Python maintenance suite runs without the Node launcher',options,t=>{
  const result=fixture(t).run(['test-python']); assert.equal(result.calls[0].kind,'python');
  assert.deepEqual(result.calls[0].args,['-m','unittest','discover','-s','tests/scripts','-v']);
});
test('all tests compose native runtimes in order',options,t=>{
  const result=fixture(t).run(['test']); assert.equal(result.status,0,result.stderr);
  assert.deepEqual(result.calls.map(c=>c.kind),['node','python','python']);
  assert.deepEqual(result.calls.at(-1).args,['-m','scripts','test-skills']);
});
test('full check does not call pnpm or run any suite twice',options,t=>{
  const result=fixture(t).run(['-j8','check']); assert.equal(result.status,0,result.stderr);
  assert.deepEqual(result.calls.map(c=>c.kind),['python','node','python','python','python','python']);
  assert.equal(result.calls.filter(c=>c.args.includes('test-skills')).length,1);
});
test('a validation failure prevents all later full-gate steps',options,t=>{
  const result=fixture(t).run(['check'],{FAIL_ON:'validate'}); assert.notEqual(result.status,0);
  assert.equal(result.calls.length,1);
});
test('bootstrap errors are not hidden by setup',options,t=>{
  assert.notEqual(fixture(t).run(['setup'],{FAIL_ON:'scripts/bootstrap.py'}).status,0);
});
test('phony targets execute even with a same-named file',options,t=>{
  const f=fixture(t); writeFileSync(join(f.directory,'validate'),''); assert.equal(f.run(['validate']).calls.length,1);
});
for(const [target,action] of [['skill-new','new'],['skill-activate','activate'],['skill-fingerprint','fingerprint'],['skill-preview','preview-skill']]){
  test(`${target} routes the canonical name without pnpm`,options,t=>{
    const result=fixture(t).run([target,'NAME=orquestrar']);
    assert.deepEqual(result.calls[0].args,['-m','scripts',action,'orquestrar']);
  });
}
test('optional unit-suite selection is an explicit Python argument',options,t=>{
  assert.deepEqual(fixture(t).run(['test-skills','NAME=orquestrar']).calls[0].args,['-m','scripts','test-skills','--name','orquestrar']);
});
test('configure preserves distinct arguments and optional ownership',options,t=>{
  const result=fixture(t).run(['configure','REPO=J-Yoharu/skills','CODEOWNER=@J-Yoharu']);
  assert.deepEqual(result.calls[0].args,['-m','scripts','configure','--github','J-Yoharu/skills','--codeowner','@J-Yoharu']);
});
test('identity check supports the workflow environment',options,t=>{
  const result=fixture(t).run(['verify-identity'],{REPO:undefined,GITHUB_REPOSITORY:'J-Yoharu/skills'});
  assert.deepEqual(result.calls[0].args,['-m','scripts','verify-identity','--github','J-Yoharu/skills']);
});
test('display names with spaces and shell punctuation are literal',options,t=>{
  const f=fixture(t), name='Example "quoted"; touch should-not-exist & literal';
  const result=f.run(['skill-new','NAME=example-skill',`DISPLAY_NAME=${name}`]);
  assert.equal(result.status,0,result.stderr); assert.equal(result.calls[0].args.at(-1),name);
  assert.equal(existsSync(join(f.directory,'should-not-exist')),false);
});
for(const target of ['configure','verify-identity','skill-new','skill-activate','skill-fingerprint','skill-preview','build-release','publish-assets']){
  test(`${target} rejects missing inputs before invoking any runtime`,options,t=>{
    const result=fixture(t).run([target]); assert.notEqual(result.status,0); assert.deepEqual(result.calls,[]);
  });
}
test('build paths with spaces remain one argument',options,t=>{
  const result=fixture(t).run(['build-release','TAG=v1.2.0','OUTPUT=dist/build artifacts']);
  assert.deepEqual(result.calls[0].args,['-m','scripts','build','--tag','v1.2.0','--output','dist/build artifacts']);
});
test('publication requires the exact acknowledgement',options,t=>{
  const result=fixture(t).run(['publish-assets','TAG=v1.2.0','CONFIRM_PUBLISH=true']);
  assert.notEqual(result.status,0); assert.deepEqual(result.calls,[]);
});
test('publication routing is simulated, never a remote write',options,t=>{
  const result=fixture(t).run(['publish-assets','TAG=v1.2.0','CONFIRM_PUBLISH=yes']);
  assert.deepEqual(result.calls[0].args,['-m','scripts','publish-assets','--tag','v1.2.0','--output','dist']);
});
test('selected isolation keeps JSON in one argument',options,t=>{
  const result=fixture(t).run(['isolate','SKILLS_JSON=["orquestrar"]']);
  assert.deepEqual(result.calls[0].args,['-m','scripts','isolate','--skills-json','["orquestrar"]']);
});
test('shard zero is preserved',options,t=>{
  const result=fixture(t).run(['isolate','SHARD_INDEX=0','SHARD_COUNT=1']);
  assert.deepEqual(result.calls[0].args,['-m','scripts','isolate','--shard-index','0','--shard-count','1']);
});
for(const args of [['SHARD_INDEX=0'],['SHARD_COUNT=1'],['SHARD_INDEX=0','SHARD_COUNT=1','SKILLS_JSON=[]']]){
  test(`invalid isolation selection ${args.join(' ')} fails before runtime`,options,t=>{
    const result=fixture(t).run(['isolate',...args]); assert.notEqual(result.status,0); assert.deepEqual(result.calls,[]);
  });
}
