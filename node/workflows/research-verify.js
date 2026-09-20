'use strict'
// Stage one researches each item and nominates the claims worth adversarially
// checking; stage two tries to REFUTE exactly those, no more and no fewer —
// nominateWorklist reads stage one's own schema field rather than the script
// re-deriving "what needs checking" itself, so the two stages cannot disagree
// about the work-list.
//
// `agent` and `pipeline` are injected via `deps`: the orchestration runtime
// that provides real ones is not available in CI, so the dispatch shape is
// exercised here with stubs instead.

const { normalizeArgs, assertModelPinned } = require('./lib/batch.js')
const { nominateWorklist, verifyPrompt, classify, tieBreak } = require('./lib/verify.js')

function researchPrompt(item) {
  return `Research ${item} and nominate the claims that need adversarial checking.`
}

function planResearchCalls(items, { model, prompt = researchPrompt } = {}) {
  return items.map((item) => ({
    item,
    prompt: typeof prompt === 'function' ? prompt(item) : prompt,
    model,
  }))
}

function planVerifyCalls(worklist, { model, sources, tieBreak: tieBreakText } = {}) {
  return worklist.map((claim) => ({
    claim,
    prompt: verifyPrompt(claim.claim, { sources: claim.sources || sources, tieBreak: tieBreakText }),
    model,
  }))
}

async function run(deps, rawArgs) {
  const args = normalizeArgs(rawArgs)
  const items = args.items || []
  const field = args.field
  const min = args.min
  const researchCalls = assertModelPinned(planResearchCalls(items, { model: args.model, prompt: args.researchPrompt }))

  if (args.dryRun) {
    // A dry run can only plan stage one: stage two's work-list is nominated
    // from stage one's real output, and there is none to read yet. Printing
    // an empty stage two here would look like "nothing needs verifying"
    // rather than "not computed" — so it is reported, not guessed at.
    const plan = { stage1: researchCalls, stage2: 'not computed until stage one runs' }
    console.log(JSON.stringify(plan, null, 2))
    return { dryRun: true, ...plan }
  }

  const stage1Records = (
    await deps.pipeline(items, (item) => deps.agent(researchPrompt(item), { model: args.model }))
  ).filter(Boolean)

  const worklist = nominateWorklist(stage1Records, { field, min })
  const verifyCalls = assertModelPinned(
    planVerifyCalls(worklist, { model: args.model, sources: args.sources, tieBreak: args.tieBreakText })
  )

  const verdicts = await deps.pipeline(verifyCalls, async (call) => {
    const raw = await deps.agent(call.prompt, { model: call.model })
    const verdict = classify(raw)
    return { claim: call.claim.claim, verdict, resolution: tieBreak(verdict, { onUncertain: args.onUncertain }) }
  })

  return { stage1Count: stage1Records.length, stage2Count: verifyCalls.length, verdicts }
}

function parseCliArgs(argv) {
  const args = {}
  for (const raw of argv) {
    if (raw === '--dry-run') {
      args.dryRun = true
      continue
    }
    const match = raw.match(/^--([^=]+)=(.*)$/)
    if (!match) continue
    const [, key, value] = match
    try {
      args[key] = JSON.parse(value)
    } catch {
      args[key] = value
    }
  }
  return args
}

if (require.main === module) {
  const cliArgs = parseCliArgs(process.argv.slice(2))
  run({ agent: null, pipeline: null }, cliArgs).catch((err) => {
    console.error(err.message)
    process.exitCode = 1
  })
}

module.exports = { run, parseCliArgs, researchPrompt, planResearchCalls, planVerifyCalls }
