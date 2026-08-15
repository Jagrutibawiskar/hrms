#!/usr/bin/env node
/**
 * Guards the two-stylesheet setup.
 *
 * `styles.css` came from the original marketing prototype; `app-ui.css` styles the
 * data-driven workspace. Three failure modes have bitten us, all silent — the page
 * just renders wrong:
 *
 *   1. A `var(--token)` with no definition  -> the whole declaration is dropped.
 *   2. A className with no rule anywhere    -> element renders unstyled.
 *   3. A class styled in BOTH files where the marketing rule wins (via `!important`
 *      or a more specific selector) -> the app's layout is silently overridden.
 *
 * Run with:  npm run check:styles
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src')

// Marketing pages keep the original design; they're not part of the app layer.
const IGNORE_FILES = new Set(['marketing.jsx'])
// Classes the app deliberately borrows from the marketing stylesheet.
const INTENTIONAL_REUSE = new Set([
  'primary-button', 'quiet-button', 'text-action', 'eyebrow', 'brand', 'brand-mark',
  'dash-sidebar', 'dash-brand', 'dash-workspace', 'dash-help', 'dash-user', 'dash-main',
  'dash-top', 'dash-toast', 'dash-tool', 'dashboard', 'card-heading', 'password-field',
  'auth-page', 'auth-brand', 'auth-brand-panel', 'auth-message', 'auth-form-panel',
  'auth-card', 'auth-form', 'auth-subtitle', 'auth-submit', 'back-home', 'forgot-link',
  'switch-auth', 'form-error', 'form-success', 'onboarding', 'onboard-progress',
  'progress', 'settings-layout', 'settings-nav', 'settings-cards', 'inner-page',
  'inner-hero', 'active', 'unread', 'avatar', 'num', 'empty-row', 'grow', 'spacer',
  'banner', 'clock', 'ghost', 'controls', 'actions', 'panel', 'approve', 'decline',
])

const styles = fs.readFileSync(path.join(SRC, 'styles.css'), 'utf8')
const app = fs.readFileSync(path.join(SRC, 'app-ui.css'), 'utf8')
const allCss = `${styles}\n${app}`

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (entry.name.endsWith('.jsx') && !IGNORE_FILES.has(entry.name)) out.push(p)
  }
  return out
}

/** Class tokens the app actually renders. */
function usedClasses() {
  const used = new Map()
  for (const file of walk(SRC)) {
    const text = fs.readFileSync(file, 'utf8')
    const add = c => {
      if (!used.has(c)) used.set(c, new Set())
      used.get(c).add(path.basename(file))
    }
    for (const m of text.matchAll(/className="([^"{}]*)"/g))
      m[1].split(/\s+/).filter(Boolean).forEach(add)
    for (const m of text.matchAll(/className=\{`([^`]*)`/g))
      m[1].split(/[\s${}]+/).filter(c => /^[a-z][\w-]*$/.test(c)).forEach(add)
  }
  return used
}

/** Rules whose selector targets exactly this class (not `.foo-bar` when asking for `.foo`). */
function rulesFor(css, cls) {
  const re = new RegExp(`(^|[,}])\\s*([^{}]*\\.${cls}(?![\\w-])[^{}]*)\\{([^}]*)\\}`, 'g')
  return [...css.matchAll(re)].map(m => ({ selector: m[2].trim(), body: m[3] }))
}

const specificity = sel => (sel.match(/[.#[]|:[a-z-]+\(/g) || []).length

let problems = 0
const report = (level, message) => {
  console.log(`  ${level}  ${message}`)
  if (level === 'FAIL') problems++
}

console.log('\n1. CSS custom properties')
const varsUsed = new Set([...app.matchAll(/var\((--[\w-]+)/g)].map(m => m[1]))
const varsDefined = new Set([...allCss.matchAll(/(--[\w-]+)\s*:/g)].map(m => m[1]))
const undefinedVars = [...varsUsed].filter(v => !varsDefined.has(v))
if (undefinedVars.length === 0) report('ok  ', `${varsUsed.size} used, all defined`)
else undefinedVars.forEach(v => report('FAIL', `${v} is used but never defined`))

console.log('\n2. Classes with no styling rule')
const used = usedClasses()
const orphans = [...used].filter(([c]) => !INTENTIONAL_REUSE.has(c) && rulesFor(allCss, c).length === 0)
if (orphans.length === 0) report('ok  ', `${used.size} classes, all styled`)
else orphans.forEach(([c, files]) => report('FAIL', `.${c} has no rule (used in ${[...files].join(', ')})`))

console.log('\n3. Marketing rules that would override the app layer')
let overrides = 0
for (const [cls] of used) {
  if (INTENTIONAL_REUSE.has(cls)) continue
  const mine = rulesFor(app, cls)
  if (mine.length === 0) continue
  const theirs = rulesFor(styles, cls)
  const maxMine = Math.max(...mine.map(r => specificity(r.selector)))

  for (const rule of theirs) {
    const wins = rule.body.includes('!important') || specificity(rule.selector) > maxMine
    if (wins) {
      report('FAIL', `.${cls}: "${rule.selector}" in styles.css beats app-ui.css`)
      overrides++
    }
  }
}
if (overrides === 0) report('ok  ', 'no marketing rule outranks the app layer')

/*
 * The check above compares class names only, which missed a real bug:
 * `.settings-cards article { display:flex }` reshaped every panel the app rendered
 * inside that container, without ever naming a class the app owns. Any marketing
 * rule of the form `.container <element>` reaches into the app's markup and
 * outranks a bare `.class` rule, so those need flagging too.
 */
console.log('\n4. Marketing rules that reach into app markup via element selectors')
const LAYOUT = /(^|;)\s*(display|position|grid-template|flex-direction|float|justify-content)\s*:/
const appClasses = new Set([...used.keys()])
const fullRules = [...styles.matchAll(/([^{}]+)\{([^}]*)\}/g)].map(m => ({
  selector: m[1].trim().replace(/\s+/g, ' '),
  body: m[2],
}))

/*
 * Reviewed and deliberate: the app reuses this marketing markup, so the marketing
 * rule styling its children is exactly what we want. Anything NOT on this list is
 * a new collision and fails the build.
 */
const REVIEWED_SAFE = new Set([
  'brand-mark i',        // the three-bar logo mark
  'progress span',       // leave-balance progress fill
  'onboard-progress span', // onboarding wizard progress fill
  'dash-sidebar nav',    // sidebar nav column + its mobile row layout
  'dash-user b',
  'dash-user small',
  'pay-summary small',
  'pay-summary strong',
  'pay-summary span',
  'payroll-note b',
  'payroll-note small',
  'settings-nav button', // app-ui.css redefines this at equal specificity, later
])

let reachIns = 0
for (const rule of fullRules) {
  if (!LAYOUT.test(rule.body)) continue
  for (const part of rule.selector.split(',')) {
    // `.some-class element` — a class the app renders, followed by a bare tag name.
    const m = part.trim().match(/^\.([\w-]+)\s+([a-z]+)$/)
    if (!m) continue
    const [, cls, tag] = m
    if (!appClasses.has(cls) || REVIEWED_SAFE.has(`${cls} ${tag}`)) continue
    report('FAIL', `"${part.trim()}" restyles every <${tag}> the app puts inside .${cls}`)
    report('    ', `  -> ${rule.body.trim().replace(/\s+/g, ' ').slice(0, 90)}`)
    report('    ', '  Either rename the container, or add it to REVIEWED_SAFE if intended.')
    reachIns++
  }
}
if (reachIns === 0) report('ok  ', `no unreviewed element rules reach into app containers`)

console.log(`\n${problems === 0 ? 'All style checks passed.' : `${problems} problem(s) found.`}\n`)
process.exit(problems ? 1 : 0)
