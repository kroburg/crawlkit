'use strict'
// Dispatch-shape tests. The bugs worth pinning here were all in how a script
// decides what to send `agent`, not in the pure helpers, so every test either
// stubs `agent`/`parallel`/`pipeline` and inspects the recorded calls, or
// exercises a helper the way a dispatcher would.

const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const os = require('os')
const path = require('path')

const batch = require('../workflows/lib/batch.js')
const verify = require('../workflows/lib/verify.js')
const batchFanout = require('../workflows/batch-fanout.js')
const researchVerify = require('../workflows/research-verify.js')

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ck-workflows-'))
}

function writeBatches(dir, names) {
  for (const name of names) fs.writeFileSync(path.join(dir, name), '{}')
}

// -- lib/batch.js ----------------------------------------------------------

test('a stringified args payload produces exactly the same dispatch as the object form', async () => {
  const dir = tmpdir()
  writeBatches(dir, ['a.json', 'b.json'])
  const calls = []
  const deps = {
    fs,
    agent: async (prompt, opts) => {
      calls.push({ prompt, opts })
      return 'ok'
    },
    parallel: async (thunks) => Promise.all(thunks.map((t) => t())),
  }
  const objectArgs = { batchDir: dir, model: 'the-model', prompt: 'process {{file}}' }
  const stringArgs = JSON.stringify(objectArgs)

  const fromObject = await batchFanout.run(deps, objectArgs)
  calls.length = 0
  const fromString = await batchFanout.run(deps, stringArgs)

  assert.strictEqual(fromObject.dispatched, fromString.dispatched)
  assert.deepStrictEqual(fromObject.results, fromString.results)
})

test('normalizeArgs turns null, undefined and a JSON string into a plain object', () => {
  assert.deepStrictEqual(batch.normalizeArgs(null), {})
  assert.deepStrictEqual(batch.normalizeArgs(undefined), {})
  assert.deepStrictEqual(batch.normalizeArgs('{"a":1}'), { a: 1 })
  const passthrough = { a: 1 }
  assert.strictEqual(batch.normalizeArgs(passthrough), passthrough)
})

test('seven files in a tmpdir produce seven calls, an eighth makes eight with no code change', () => {
  const dir = tmpdir()
  writeBatches(dir, Array.from({ length: 7 }, (_, i) => `batch-${i}.json`))
  assert.strictEqual(batch.discoverBatches(dir).length, 7)

  fs.writeFileSync(path.join(dir, 'batch-7.json'), '{}')
  assert.strictEqual(batch.discoverBatches(dir).length, 8)
})

test('discoverBatches never returns a hardcoded count and filters + sorts by pattern', () => {
  const dir = tmpdir()
  writeBatches(dir, ['b.json', 'a.json', 'README.md', '.hidden'])
  assert.deepStrictEqual(batch.discoverBatches(dir, { pattern: /\.json$/ }), ['a.json', 'b.json'])
})

test('every dispatched call names a model; a call built without one makes assertModelPinned throw', () => {
  const pinned = batch.planCalls(['a.json'], { model: 'the-model', prompt: 'x' })
  assert.doesNotThrow(() => batch.assertModelPinned(pinned))

  const unpinned = batch.planCalls(['a.json', 'b.json'], { model: undefined, prompt: 'x' })
  assert.throws(() => batch.assertModelPinned(unpinned), /a\.json/)
})

test('planCalls substitutes {{file}} into a string prompt and calls a function prompt per file', () => {
  const templated = batch.planCalls(['a.json'], { model: 'm', prompt: 'process {{file}}' })
  assert.strictEqual(templated[0].prompt, 'process a.json')

  const fn = batch.planCalls(['a.json', 'b.json'], { model: 'm', prompt: (file) => `handle ${file}!` })
  assert.deepStrictEqual(fn.map((c) => c.prompt), ['handle a.json!', 'handle b.json!'])
})

// -- lib/verify.js -----------------------------------------------------------

test("stage two's work-list is exactly what stage one nominated, no more, no fewer", () => {
  const stage1Records = [
    { id: 1, safety_claims: [{ claim: 'A', sources: ['s1'] }, { claim: 'B', sources: ['s2'] }] },
    { id: 2, safety_claims: [{ claim: 'C', sources: ['s3'] }] },
  ]
  const worklist = verify.nominateWorklist(stage1Records, { field: 'safety_claims', min: 1 })
  assert.deepStrictEqual(
    worklist.map((c) => c.claim),
    ['A', 'B', 'C']
  )
})

test('nominateWorklist drops a claim below the source-count floor rather than sending it unverifiable', () => {
  const stage1Records = [
    { safety_claims: [{ claim: 'grounded', sources: ['s1', 's2'] }, { claim: 'bare', sources: [] }] },
  ]
  const worklist = verify.nominateWorklist(stage1Records, { min: 1 })
  assert.deepStrictEqual(worklist.map((c) => c.claim), ['grounded'])
})

test('the verify prompt asks for refutation and states the tie-break', () => {
  const prompt = verify.verifyPrompt('the bridge opened in 1990', {
    sources: 'municipal records',
    tieBreak: 'keep the original and flag it',
  })
  assert.match(prompt, /REFUTE/)
  assert.match(prompt, /keep the original and flag it/)
  assert.match(prompt, /municipal records/)
})

test('classify rejects a verdict outside the contract vocabulary', () => {
  assert.throws(() => verify.classify('maybe'), /maybe/)
})

test('classify rejects a verdict that exists but is not offered to agents', () => {
  // verify_verdict itself offers everything it accepts, so the not-offered
  // case is exercised against another vocabulary in the same contract file
  // (content_status.unchecked, offer_to_agent: false) — classify reads
  // whichever vocabulary it is pointed at, the same way the prompt-side guide
  // in crawlkit.agents.sections does.
  assert.throws(() => verify.classify('unchecked', { vocab: 'content_status' }), /unchecked/)
  assert.doesNotThrow(() => verify.classify('confirmed'))
})

test('tieBreak keeps the original and flags a human on uncertain, and rejects any other policy', () => {
  assert.deepStrictEqual(verify.tieBreak('uncertain'), {
    verdict: 'uncertain',
    keepOriginal: true,
    flagForHuman: true,
  })
  assert.deepStrictEqual(verify.tieBreak('confirmed'), {
    verdict: 'confirmed',
    keepOriginal: false,
    flagForHuman: false,
  })
  assert.throws(() => verify.tieBreak('uncertain', { onUncertain: 'discard' }))
})

// -- research-verify.js dispatch shape ---------------------------------------

test('research-verify pins the model on both stages and dispatches exactly the nominated claims', async () => {
  const agentCalls = []
  const deps = {
    agent: async (prompt, opts) => {
      agentCalls.push({ prompt, opts })
      if (prompt.startsWith('Research')) {
        return {
          safety_claims: [
            { claim: 'grounded claim', sources: ['src-1'] },
            { claim: 'unsourced claim', sources: [] },
          ],
        }
      }
      return 'confirmed'
    },
    pipeline: async (items, ...stages) =>
      Promise.all(
        items.map(async (item, index) => {
          let value = item
          for (const stage of stages) value = await stage(value, item, index)
          return value
        })
      ),
  }

  const result = await researchVerify.run(deps, { items: ['x'], model: 'the-model' })

  assert.strictEqual(result.stage1Count, 1)
  assert.strictEqual(result.stage2Count, 1)
  assert.deepStrictEqual(
    result.verdicts.map((v) => v.claim),
    ['grounded claim']
  )
  assert.ok(agentCalls.every((call) => call.opts.model === 'the-model'))
})

test('research-verify dry-run plans stage one and dispatches nothing', async () => {
  let called = false
  const deps = {
    agent: async () => {
      called = true
    },
    pipeline: async () => {
      called = true
    },
  }
  const result = await researchVerify.run(deps, { items: ['x', 'y'], model: 'the-model', dryRun: true })
  assert.strictEqual(result.dryRun, true)
  assert.strictEqual(result.stage1.length, 2)
  assert.ok(result.stage1.every((call) => call.model === 'the-model'))
  assert.ok(!called)
})

test('batch-fanout dry-run plans the calls and dispatches nothing', async () => {
  const dir = tmpdir()
  writeBatches(dir, ['a.json', 'b.json'])
  let called = false
  const deps = {
    fs,
    agent: async () => {
      called = true
    },
    parallel: async () => {
      called = true
    },
  }
  const result = await batchFanout.run(deps, { batchDir: dir, model: 'the-model', prompt: 'x', dryRun: true })
  assert.strictEqual(result.dryRun, true)
  assert.strictEqual(result.calls.length, 2)
  assert.ok(!called)
})
