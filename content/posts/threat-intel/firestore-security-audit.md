---
title: "How We Found and Fixed a JWT Privilege Escalation in a Payment App"
slug: "firestore-security-audit"
date: 2026-06-23
description: "A developer's walkthrough of a real security audit on a Firebase + Stripe payment app — covering a HIGH-severity JWT privilege escalation, client-side deletion of payment records, and five other findings that changed how I think about Firestore security rules."
categories: ["threat-intel"]
tags: ["firebase", "firestore", "security-audit", "jwt", "stripe", "webhooks", "pci-dss", "privilege-escalation"]
author: "Aya Ibrahim Mehjez"
canonicalURL: "https://blog.pcioasis.com/posts/threat-intel/firestore-security-audit/"
ShowToc: true
TocOpen: true
---

## What a Security Audit Actually Looks Like

I went into this audit expecting a checklist. Run a scanner, get a report, apply patches, close tickets. That is not what happened.

A real security audit of a live payment app is a slow, methodical process of asking "what would happen if...?" for every entry point, every trust boundary, every place where the app takes something from a user and acts on it. For a Firebase + Stripe app, those questions center on one thing more than anything else: **what does your Firestore security rules file actually enforce, versus what you assumed it enforced?**

We audited a payment application built on Firebase Authentication, Cloud Firestore, and Stripe. The app let users save cards, initiate charges, and view their payment history. PCI DSS scope was limited — Stripe handles card data directly — but the application layer between user authentication and payment records was entirely under our control, and that is where the vulnerabilities lived.

Seven findings came out of the audit. Two of them required immediate remediation. This post covers those two in depth, then briefly covers the rest.

---

## FINDING-002 (HIGH): JWT Privilege Escalation via Unvalidated Custom Claims

### What the Vulnerability Was

Firebase Authentication issues JWTs that can carry **custom claims** — key-value pairs set server-side via the Admin SDK. Our app used a custom claim called `authorization` to distinguish regular users from admins:

```javascript
// Cloud Function: setUserRole.js
await admin.auth().setCustomUserClaims(uid, { authorization: 'admin' });
```

The Firestore security rules then checked this claim to gate access to sensitive collections:

```javascript
// firestore.rules (vulnerable version)
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    match /payments/{paymentId} {
      allow read: if request.auth != null
        && request.auth.token.authorization == 'admin';
    }

    match /users/{userId}/profile {
      allow write: if request.auth != null
        && request.auth.token.authorization == 'user';
    }

  }
}
```

This looks reasonable. The rules check `request.auth.token.authorization` — the value of the custom claim in the JWT. The problem is that **custom claims in Firebase JWTs are not signed separately from the rest of the token**. The entire JWT is signed by Firebase, but the claim values themselves are set by whoever has Admin SDK access — and until our Cloud Function ran, a freshly registered user's token carried no `authorization` claim at all.

The rules checked `== 'admin'` for the payments collection and `== 'user'` for the profile collection. But they never checked what happened when `authorization` was `null`, `undefined`, or an arbitrary string the attacker supplied.

### How an Attacker Could Exploit It

Firebase custom claims propagate to the client only after the token is refreshed. An attacker who registered a new account, intercepted the token refresh cycle, and injected a forged `authorization` claim into a locally modified token would fail — Firebase tokens are properly signed, and Firestore rejects tampered JWTs.

But the actual attack surface was subtler. The `users/{userId}/profile` write rule required `authorization == 'user'`. A newly registered user whose token had not yet gone through the `setUserRole` Cloud Function had `authorization` equal to nothing — `null` in the token, `undefined` in the rules evaluation.

In Firestore rules, `undefined == 'user'` evaluates to `false`. So far, so good. But the profile document itself stored a `role` field. Another part of the application read `role` from Firestore directly and used it to determine UI permissions client-side. If a user could write to their own profile before the Cloud Function ran, they could set `role: 'admin'` on their Firestore document.

This created a **race condition privilege escalation**:

1. Attacker registers an account.
2. Before the `setUserRole` Cloud Function assigns `authorization: 'user'` to the JWT, attacker calls `updateDoc` on their own profile with `{ role: 'admin' }`.
3. The write rule checks `request.auth.token.authorization == 'user'`. The claim is not yet set — the check evaluates to `false`.
4. The write is blocked. But the client-side code, which checks the Firestore `role` field rather than the JWT claim, now sees `role: 'admin'` from a previous write that succeeded in the window before rules enforcement.

The window was narrow but real, and the impact was compounded by a second issue: the client-side code trusting Firestore fields over JWT claims for UI rendering meant that any Firestore write race could produce an inconsistent privilege state that the UI would honor.

### The Quick Fix: Remove the Race Condition

The immediate remediation was to stop checking `request.auth.token.authorization == 'user'` for profile writes, and instead **hardcode the authorization level expected for the operation**:

```javascript
// firestore.rules (quick fix)
match /users/{userId}/profile {
  allow write: if request.auth != null
    && request.auth.uid == userId
    && request.resource.data.role == 'user';  // Never allow writing a non-'user' role
}
```

This eliminated the race condition by making the rule self-enforcing: regardless of JWT claims, no client can write a `role` value other than `'user'` to their own profile document. The rules no longer depend on a claim that may not yet exist.

### The Full Fix: Admin SDK Claims + Payments Collection Rules

The quick fix closed the race, but the architecture needed a deeper correction. Custom claims should be the **single source of truth** for authorization, not one of two competing sources. The full fix had two parts.

**Part 1**: The `setUserRole` Cloud Function was changed to run on user creation via an `onCreate` trigger rather than being called manually. This eliminated the window where a new user had no claim at all:

```javascript
// Cloud Function: onUserCreated.js
exports.onUserCreated = functions.auth.user().onCreate(async (user) => {
  await admin.auth().setCustomUserClaims(user.uid, { authorization: 'user' });
});
```

**Part 2**: The payments collection rules were rewritten to use the Admin SDK claim exclusively, and the client-side code was updated to derive UI permissions from the JWT rather than from Firestore fields:

```javascript
// firestore.rules (full fix)
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    match /payments/{paymentId} {
      allow read: if request.auth != null
        && request.auth.token.authorization == 'admin';
      allow write: if false;  // All payment writes go through Admin SDK only
    }

    match /users/{userId}/profile {
      allow read: if request.auth != null && request.auth.uid == userId;
      allow write: if request.auth != null
        && request.auth.uid == userId
        && request.resource.data.keys().hasOnly(['displayName', 'avatarUrl', 'updatedAt'])
        && request.resource.data.get('role', null) == null;  // role field not writable by clients
    }

  }
}
```

The `hasOnly` check is the part that matters most: it specifies an explicit allowlist of fields the client can write. Any field not on that list — including `role`, `authorization`, `stripeCustomerId`, or anything else sensitive — is rejected at the rules layer before it reaches the database.

---

## FINDING-006: Client-Side `deleteDoc` on Payment Records

### Why This Matters for Financial Data Integrity

This finding did not involve privilege escalation or authentication bypass. It was simpler, and in some ways more alarming: the application's `paymentService.js` file called `deleteDoc` directly from the client on payment records.

```javascript
// paymentService.js (vulnerable — since deleted)
import { doc, deleteDoc } from 'firebase/firestore';

export async function removePaymentRecord(paymentId) {
  const ref = doc(db, 'payments', paymentId);
  await deleteDoc(ref);
}
```

The Firestore rules at the time did not explicitly deny client-side deletes. Under Firestore's default-deny model, an unspecified operation is blocked — but the rules had an `allow write` clause that covered `create`, `update`, and `delete` together:

```javascript
// The rule that made this possible
match /payments/{paymentId} {
  allow write: if request.auth != null && request.auth.uid == resource.data.userId;
}
```

`write` in Firestore rules is shorthand for all three of `create`, `update`, and `delete`. A user could delete their own payment records.

For a payment application, this is a financial data integrity problem before it is a security problem. Payment records are an audit trail. PCI DSS Requirement 10.3 requires audit log protection against modification and deletion. If a user can remove their own payment history, the audit trail is meaningless. If an attacker gains access to any authenticated session, they can wipe the evidence of fraudulent transactions.

The Firestore security rules documentation is clear on this, but the `write` shorthand is a trap that is easy to fall into when you are thinking about create and update and not specifically about delete.

### How We Fixed It

The fix had two parts. First, `paymentService.js` was deleted entirely. No client-side code should own payment record lifecycle — that is a server concern.

Second, payment record creation and updates were moved entirely to a Cloud Function triggered by Stripe webhooks. The client never writes to the payments collection directly:

```javascript
// Cloud Function: stripeWebhook.js
exports.stripeWebhook = functions.https.onRequest(async (req, res) => {
  const sig = req.headers['stripe-signature'];
  let event;

  try {
    event = stripe.webhooks.constructEvent(req.rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  if (event.type === 'payment_intent.succeeded') {
    const paymentIntent = event.data.object;
    await admin.firestore().collection('payments').doc(paymentIntent.id).set({
      userId: paymentIntent.metadata.userId,
      amount: paymentIntent.amount,
      currency: paymentIntent.currency,
      status: 'succeeded',
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
    });
  }

  res.json({ received: true });
});
```

The updated Firestore rules for the payments collection now deny all client writes explicitly:

```javascript
match /payments/{paymentId} {
  allow read: if request.auth != null && request.auth.uid == resource.data.userId;
  allow create, update, delete: if false;  // Admin SDK only, via webhook handler
}
```

Using `create, update, delete: if false` rather than `write: if false` is intentional — it is self-documenting. When someone reads this rule in six months, they will not wonder whether the `write` shorthand was intended to cover deletes.

---

## The Other Five Findings

**FINDING-001 (MEDIUM) — Overly Permissive Firestore Default Rules**
The initial rules file used `allow read, write: if request.auth != null` as a catch-all on several collections. Any authenticated user could read and write any document in those collections. This was replaced with per-collection rules with explicit field-level constraints.

**FINDING-003 (MEDIUM) — Stripe Webhook Signature Not Verified**
The original webhook handler called `stripe.webhooks.constructEvent` but swallowed the signature verification error silently, continuing to process the event body regardless. A malicious POST to the webhook endpoint could fake payment success events. Fixed by letting the error propagate and returning a 400 immediately.

**FINDING-004 (LOW) — Firebase App Check Not Enforced**
The app had Firebase App Check configured but not enforced — it was running in debug mode in production. App Check attestation prevents unauthorized clients from calling Firebase services with your project credentials. Enforcement was enabled with a 7-day grace period to avoid disrupting existing clients.

**FINDING-005 (LOW) — Stripe Customer ID Stored Client-Readable**
The `users/{userId}/profile` document stored `stripeCustomerId` in a field any authenticated client could read. While a Stripe customer ID is not directly exploitable, it reduces the cost of targeted phishing and is unnecessary client-side. The field was removed from profile and kept only in a server-side collection inaccessible to clients.

**FINDING-007 (INFORMATIONAL) — No Rate Limiting on Payment-Triggering Cloud Functions**
The Cloud Functions that initiated Stripe payment intents had no request rate limiting per user. A compromised account could trigger repeated payment attempts. Cloud Armor rate limiting rules were added at the Firebase Hosting layer.

---

## Lessons Learned

The most useful thing this audit taught me is the difference between **security by default** and **security by configuration**.

Firestore's default-deny model feels safe. If you do not write a rule for something, it is blocked. But the moment you add a `allow write` for legitimate reasons, you have to think about every operation that falls under `write` — including the ones you did not have in mind when you wrote it. The `deleteDoc` finding existed not because someone made an obvious mistake but because the author was thinking about create and update and the word `delete` never entered the picture.

JWT custom claims felt like a clean separation of concerns: server sets the claim, rules check the claim, done. What the audit forced me to see is that any gap between "when the claim is set" and "when the rules check it" is an attack surface. The race condition in FINDING-002 was small, but it was real, and it existed precisely because two different authorization sources — JWT claims and Firestore document fields — were allowed to coexist without a clear hierarchy.

The fix that surprised me most was the `hasOnly` check. I had been writing Firestore rules for two years without reaching for it. Allowlisting exactly which fields a client can write is the kind of rule that costs five minutes to write and closes a wide category of future vulnerabilities by default. Now it is the first thing I add to any writable document rule.

Working through a real audit as the developer who wrote the code is uncomfortable in a way that synthetic exercises are not. The finding is not abstract. It is in code you shipped. The question is not "could this vulnerability exist?" but "how long has it been there?" That discomfort is productive. It changes how you read your own code afterward.

For any team running a Firebase payment integration: pull your Firestore rules file, go through every `allow write`, and ask whether `delete` being in scope for that rule is intentional. Then check whether anything in your client code calls `deleteDoc` on a collection that contains financial records. That audit takes twenty minutes. It is worth doing before someone else does it for you.
