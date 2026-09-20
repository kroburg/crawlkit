'use strict'
// Start the SAME fixture server the Python suite uses. One definition of each
// wall, two clients — so the runtimes' tests cannot drift apart in what they
// think a challenge looks like.

const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const REPO = path.join(__dirname, '..', '..', '..')
const VENV_PY = path.join(REPO, '.venv', 'bin', 'python')

function python() {
  return fs.existsSync(VENV_PY) ? VENV_PY : 'python3'
}

function hasChrome() {
  const contract = require('../../lib/contract.js')
  return fs.existsSync(process.env.CRAWLKIT_CHROME || contract.get('browser.branded_chrome'))
}

async function start() {
  const proc = spawn(python(), ['-m', 'fixtures.server', '--port', '0'], {
    cwd: REPO,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  const base = await new Promise((resolve, reject) => {
    // Kill the child on any failure: an orphaned server keeps the node test
    // runner's event loop alive and the suite hangs instead of reporting.
    const fail = (err) => {
      proc.kill('SIGKILL')
      reject(err)
    }
    const timer = setTimeout(() => fail(new Error('fixture server did not start in 20s')), 20000)
    let buffer = ''
    proc.stderr.on('data', (chunk) => {
      buffer += chunk.toString()
    })
    proc.stdout.on('data', (chunk) => {
      buffer += chunk.toString()
      const m = buffer.match(/LISTENING (http:\/\/\S+)/)
      if (m) {
        clearTimeout(timer)
        resolve(m[1])
      }
    })
    proc.on('error', fail)
    proc.on('exit', (code) => fail(new Error(`fixture server exited (${code}): ${buffer}`)))
  })

  // Wait until it really answers, not merely until it printed.
  for (let i = 0; i < 100; i++) {
    try {
      const res = await fetch(`${base}/health`)
      if (res.ok) break
    } catch {}
    await new Promise((r) => setTimeout(r, 50))
  }

  return {
    base,
    stop: () => proc.kill('SIGTERM'),
    stats: async () => (await fetch(`${base}/stats`)).json(),
  }
}

module.exports = { start, hasChrome, python }
