'use strict'
// One agent per discovered batch file. The dispatch loop itself is what the
// three incidents in lib/batch.js were found in, so this file does nothing
// except: normalize args once, discover from disk (never a count baked into
// the script), pin every call's model, and hand the plan to `parallel`.
//
// `agent`, `parallel` and `fs` are all injected via `deps` — the orchestration
// runtime that provides real ones is not available in CI, so the dispatch
// shape is exercised here with stubs instead.

const { normalizeArgs, discoverBatches, planCalls, assertModelPinned } = require('./lib/batch.js')

async function run(deps, rawArgs) {
  const args = normalizeArgs(rawArgs)
  if (!args.batchDir) {
    throw new Error('batch-fanout: no batchDir in args (normalized to {} — check the caller passed one)')
  }

  const batches = discoverBatches(args.batchDir, { pattern: args.pattern }, deps.fs)
  const calls = assertModelPinned(planCalls(batches, { model: args.model, prompt: args.prompt }))

  if (args.dryRun) {
    const plan = { batchDir: args.batchDir, calls }
    console.log(JSON.stringify(plan, null, 2))
    return { dryRun: true, ...plan }
  }

  const results = await deps.parallel(calls.map((call) => () => deps.agent(call.prompt, { model: call.model })))
  return { batchDir: args.batchDir, dispatched: calls.length, results }
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
  run({ fs: require('fs'), agent: null, parallel: null }, cliArgs).catch((err) => {
    console.error(err.message)
    process.exitCode = 1
  })
}

module.exports = { run, parseCliArgs }
