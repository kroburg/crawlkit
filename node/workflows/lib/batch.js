'use strict'
// Dispatch shape for "one agent per discovered file". Three incidents shaped
// every function here, and each one shipped silently — the fanout reported
// success while doing less work than it looked like it did.
//
// 1. Stringified args. The orchestration runtime sometimes hands `args`
//    through as a JSON string instead of an object. Code that reached
//    straight for `args.batchDir` then read `undefined`, discovered nothing,
//    dispatched zero agents, and returned a clean summary. normalizeArgs is
//    the one place that has to know about the string form.
// 2. A hardcoded batch count. `const n = 31` kept dispatching 31 agents long
//    after the work-list grew past that. discoverBatches always re-reads the
//    directory, so the count can only ever come from what's actually there.
// 3. An unpinned model. An agent call with no model inherits whatever the
//    session happens to be running, so a fleet drifts model between runs with
//    nothing in the output to say so. assertModelPinned makes the omission an
//    error instead of a silent inheritance.

const nodeFs = require('fs')

function normalizeArgs(args) {
  if (args === null || args === undefined) return {}
  if (typeof args === 'string') return JSON.parse(args)
  return args
}

function discoverBatches(dir, { pattern = /^[^.]/ } = {}, fs = nodeFs) {
  // The regex may arrive as a string when args came through JSON (see
  // normalizeArgs) — a RegExp has no JSON form, so a string is the only way
  // a caller can hand one through the runtime boundary.
  const re = typeof pattern === 'string' ? new RegExp(pattern) : pattern
  return fs.readdirSync(dir).filter((name) => re.test(name)).sort()
}

function planCalls(batches, { model, prompt } = {}) {
  // `prompt` may be a function(file) for a per-file prompt, or a string
  // template containing `{{file}}`. A plain string with no placeholder would
  // dispatch a fleet of agents that cannot tell which file is theirs — the
  // substitution surfaces that mistake in a unit test instead of in a live
  // fanout where every agent quietly works the same batch.
  return batches.map((file) => ({
    file,
    prompt: typeof prompt === 'function' ? prompt(file) : String(prompt).replace(/\{\{file\}\}/g, file),
    model,
  }))
}

function assertModelPinned(calls) {
  const offender = calls.find((call) => !call.model)
  if (offender) {
    throw new Error(
      `no model pinned for ${offender.file}: an agent call with no model inherits the ` +
        'session model, so a fleet silently changes model between runs and the results ' +
        'stop being comparable'
    )
  }
  return calls
}

module.exports = { normalizeArgs, discoverBatches, planCalls, assertModelPinned }
