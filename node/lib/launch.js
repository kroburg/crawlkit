'use strict'
// The warm-session launcher.
//
// Four choices in here are load-bearing, and the first one is the whole reason
// this runtime exists separately from the Python renderer:
//
//   userDataDir      a persistent profile SHARED by every script in the repo.
//                    The clearance cookie plus the challenge's local storage
//                    survive process exit, so the first script to pass a wall
//                    warms the profile and everything afterwards starts
//                    already-cleared. It is also why harvesting must be
//                    sequential — see profileLock.js.
//   executablePath   real branded Chrome, not a bundled Chromium. Chromium
//                    for Testing advertises a different brand set and is
//                    fingerprinted on sight.
//   AutomationControlled  clears navigator.webdriver, the cheapest tell.
//   offscreen headful     when 'new' headless is not enough, a genuine headed
//                    window passes far more checks; positioning it at 6000,6000
//                    keeps it off the visible desktop instead of stealing focus.

const fs = require('fs')
const path = require('path')
const puppeteer = require('puppeteer-core')

const contract = require('./contract.js')
const { ProfileLock } = require('./profileLock.js')

const REPO = path.join(__dirname, '..', '..')

function profileDir(dir) {
  return path.resolve(dir || process.env.CRAWLKIT_PROFILE || path.join(REPO, contract.get('browser.profile_dir_default')))
}

function chromePath() {
  return process.env.CRAWLKIT_CHROME || contract.get('browser.branded_chrome')
}

function resolverRules(map) {
  if (!map) return []
  const rules = Object.entries(map).map(([host, addr]) => `MAP ${host} ${addr}`)
  return rules.length ? [`--host-resolver-rules=${rules.join(',')}`] : []
}

/**
 * Launch Chrome on the warm profile. Returns {browser, page, lock, release}.
 * ALWAYS call release() — it closes the browser and frees the profile lock.
 */
async function open({ headful = false, profile, resolve: resolveMap, lock = true, extraArgs = [] } = {}) {
  const dir = profileDir(profile)
  fs.mkdirSync(dir, { recursive: true })

  const held = lock ? ProfileLock.acquire(dir) : null

  const args = [
    ...contract.get('browser.launch_args'),
    ...resolverRules(resolveMap),
    ...extraArgs,
  ]
  if (headful) args.push(`--window-position=${contract.get('browser.offscreen_window_position')}`)

  let browser
  try {
    browser = await puppeteer.launch({
      executablePath: chromePath(),
      headless: headful ? false : 'new',
      userDataDir: dir,
      args,
    })
  } catch (err) {
    if (held) held.release()
    throw err
  }

  const page = (await browser.pages())[0] || (await browser.newPage())
  await page.setUserAgent(contract.ua())

  const release = async () => {
    try {
      await browser.close()
    } finally {
      if (held) held.release()
    }
  }

  return { browser, page, lock: held, release }
}

module.exports = { open, profileDir, chromePath, resolverRules }
