'use strict'
// Two-stage research -> verify. Stage one researches an item and, in a schema
// field, nominates the claims that need adversarial checking; stage two tries
// to REFUTE each one. "Check this claim" returns agreement — "try to refute
// it" returns evidence — so the prompt must ask for the second, never the
// first.
//
// classify() is the Node twin of crawlkit.agents.verdicts.validate(from_agent
// =True): it reads the accepted verdicts from the same contract vocabulary
// the prompt-side guide is rendered from, and only ever accepts the subset
// marked offer_to_agent. Two runtimes maintaining that enum as separate lists
// is exactly how they skew, and the symptom is a whole fanout's worth of
// rejected verdicts with no obvious cause.

const contract = require('../../lib/contract.js')

function nominateWorklist(stage1Records, { field = 'safety_claims', min = 1 } = {}) {
  const worklist = []
  for (const record of stage1Records) {
    for (const entry of record[field] || []) {
      // A claim with fewer than `min` sources has nothing for stage two to
      // try to refute against; nominating it anyway sends an agent a call it
      // cannot honestly answer, and a guess there is indistinguishable from a
      // genuine confirmation.
      if ((entry.sources || []).length >= min) worklist.push(entry)
    }
  }
  return worklist
}

function verifyPrompt(
  claim,
  { sources = 'independent, primary sources', tieBreak = 'keep the original claim and flag it for a human' } = {}
) {
  return (
    `Adversarially fact-check this claim: "${claim}"\n` +
    `Try to REFUTE it using ${sources}.\n` +
    'If the evidence is mixed, stale, or you cannot settle it, return `uncertain` — never split ' +
    `the difference. Tie-break: ${tieBreak}.`
  )
}

function classify(raw, { vocab = 'verify_verdict' } = {}) {
  const allowed = contract.get(`vocabularies.${vocab}`)
  const entry = allowed[raw]
  if (!entry || entry.offer_to_agent !== true) {
    const offered = Object.keys(allowed).filter((name) => allowed[name].offer_to_agent === true)
    throw new Error(
      `${JSON.stringify(raw)} is not an agent-offered ${vocab} verdict; allowed: ${offered.join(', ')}`
    )
  }
  return raw
}

function tieBreak(verdict, { onUncertain = 'keep' } = {}) {
  if (verdict !== 'uncertain') return { verdict, keepOriginal: false, flagForHuman: false }
  if (onUncertain !== 'keep') {
    // The only implemented policy is the safe one. Splitting the difference
    // by whichever way the model leans is the exact failure this function
    // exists to close off, so any other policy is an error, not a guess.
    throw new Error(`unsupported onUncertain policy ${JSON.stringify(onUncertain)}; only 'keep' is safe`)
  }
  return { verdict, keepOriginal: true, flagForHuman: true }
}

module.exports = { nominateWorklist, verifyPrompt, classify, tieBreak }
