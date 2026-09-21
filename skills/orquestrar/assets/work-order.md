# Work order — fill only relevant fields

Logical role: implementer | researcher | reviewer
Unit/batch: <ID and outcome>
Run objective: <verifiable result>
Mode/model: <required capacity; actual selection or inheritance; no invented settings>
Checkout/revision: <absolute path, branch/base/HEAD, or file identity>
Ownership: <editable files/modules; none for read-only work>
Completion boundary: <current unit and required acceptance/review/tests/integration>
Run control: <running | draining; IDs authorized for closure>

## Required context
- Acceptance criteria: <essential text, source, ID/revision, and section>.
- Invariants/decisions: <material constraints and settled decisions>.
- Canonical owner/reuse: <capability, file/symbol, reuse/extend>.
- Dependency contracts: <revision actually available here>.
- Anchor files: <only useful files and applicable local rules>.
- Sources unavailable to the worker: <necessary excerpts without secrets>.

## Execution and boundaries
<Expected outcome and relevant checks; do not prescribe every small edit.>
Use the user's language for communication and repository conventions for artifacts;
apply any specific language instructions supplied by the coordinator. Preserve
literal identifiers, commands, paths, states, and source references.
Do not open agents, change branches, publish, write to trackers, or include others'
work. No destructive operations or real-data/service changes without specific
permission. Follow project locks/resource limits: <discovered constraints>.
Report needed ownership expansion before editing; the coordinator decides.
Use existing patterns for reversible implementation details and state assumptions.
A missing material product decision blocks the affected part.

When the coordinator requests graceful pause, finish only the current unit and
its evidence, not the next batch unit. For a multi-unit batch, return each unit's
result and start the next only after coordinator clearance, without asking the
user. This retains worker/context continuity without an invisible autonomous queue.
Report completion, pending review, and owned processes. For an immediate stop,
preserve existing work and describe incomplete steps. Do not declare a clean
pause or release the queue: the coordinator confirms closure.

Implementer: implement within contract, run authorized tests, and self-review.
Researcher: answer the question with sources; do not write product code.
Reviewer: inspect the scoped diff and necessary code for compliance and engineering;
do not edit, delegate, or treat the author's report as proof.

## Return
Status: implemented | researched | reviewed | blocked | partial
Files/revision: <actual list or referenced artifact, not just a count>
Result/contract: <changes; consumed/produced contract>
Evidence: <command, revision, result, exit code, and log/artifact>
Review: <self | independent; coverage/findings, or pending>
Findings: <file:line, condition, consequence, evidence, blocking/nonblocking>
Gaps/decisions: <unverified items, risks, and assumptions>
Processes/resources: <owned resources still active; IDs>
Next action: <necessary action>

For long details, save an artifact and return a referenced summary. Never omit a
requirement, failure, or risk merely to meet a line limit. These headings are a
template, not a requirement to change the user's language.

## Resolved profile and route
- Profile/revision and sections used: <accessible references; no global rediscovery>.
- Requested role, model, and effort: <subagent route resolved by the coordinator>.
- You are a subagent; coordination remains in the chat that delegated this unit.
  Do not change its model/effort or take over coordination.
- Selected native configuration/profile: <actual mechanism or uncontrolled inheritance>.
- Effective model/effort: <actual metadata or unknown; do not guess>.
- Do not change model policy or project overrides in this unit.
