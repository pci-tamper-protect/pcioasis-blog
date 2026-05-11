# Sources: zkTLS / Reclaim Protocol + Claude × Blender Visual Pipeline

*Fetched May 9, 2026. All URLs verified.*

---

## PART 1: CRYPTOGRAPHIC RESEARCH — zkTLS / Proof of Provenance

---

### [1] Reclaim Protocol Whitepaper v2.0 *(In-project PDF)*
**Authors:** Reclaim Protocol Team  
**Date:** September 19, 2025  
**URL:** https://reclaimprotocol.org  
**PDF:** `Reclaim_Whitepaper_v2.pdf` *(attached to this project)*

**What it is:** The primary reference. Describes a proxy-based zkTLS approach where an Attestor routes encrypted TLS traffic and the user generates zero-knowledge proofs of selective data — without revealing session keys. Includes the decentralized attestation mechanism with game-theoretic economic security, honeypot mechanism, and formal proofs against fake key reveal attacks.

**Diagram quality:** Moderate. Two sequence diagrams (Figures 1 & 3), one cipher diagram (Figure 2 — ChaCha20). Sparse by academic standards — good target for 3D visual reimagining.

**Key concepts to visualize:**
- User ↔ Attestor ↔ Website three-party proxy flow
- ZKP selective reveal of TLS response bytes
- Decentralized attestor selection (auction mechanism)
- Honeypot trap dynamic (user vs. attestor game)

---

### [2] DECO: Liberating Web Data Using Decentralized Oracles for TLS
**Authors:** Fan Zhang, Deepak Maram, Harjasleen Malvai, Steven Goldfeder, Ari Juels (Cornell Tech / IC3)  
**Venue:** ACM CCS 2020  
**arXiv:** arXiv:1909.00938v4 (Aug 18, 2020)  
**PDF:** https://research.chain.link/deco.pdf  
**DOI:** https://dl.acm.org/doi/10.1145/3372297.3417239

**What it is:** The foundational academic paper for the whole space. DECO introduces a three-party TLS handshake (prover + verifier + server) that creates an unforgeable commitment to session data without trusted hardware or server-side changes. The first system to work with modern TLS 1.2 and 1.3.

**Core innovations:**
- Three-party handshake protocol — verifier co-derives TLS MAC key via 2PC, preventing session forgery
- Selective opening: efficient substring ZK proofs using CBC-HMAC structure (3 AES invocations vs. 1024 for naïve approach)
- Context-integrity framework — two-stage parsing to prevent out-of-context data attacks
- Performance: 2.85s three-party handshake (WAN), 2.52s 2PC query execution, 3–13s ZK proof generation

**Applications implemented:** Private financial instrument via smart contract; legacy-to-anonymous credential conversion; verifiable claims against price discrimination.

**Diagram quality:** High. Multiple protocol flow diagrams, MPC circuit diagrams, performance tables.

**Why it matters for Reclaim:** Reclaim cites DECO as a predecessor. DECO uses MPC (more trust-minimized); Reclaim uses a simpler proxy model (more performant). Reading both gives you the full design tradeoff space.

---

### [3] A Comprehensive Review of TLSNotary Protocol
**Authors:** Maciej Kalka, Marek Kirejczyk (vlayer Labs)  
**Date:** September 26–27, 2024  
**arXiv:** arXiv:2409.17670v2  
**PDF:** https://arxiv.org/pdf/2409.17670  
**Abstract:** https://arxiv.org/abs/2409.17670  
**License:** CC BY 4.0  
**Size:** 993 KB (diagram-heavy)

**What it is:** The most diagram-rich paper in the space. A thorough walkthrough of the TLSNotary MPC-TLS protocol, written by the vlayer team who are building on top of it in production. Covers cryptographic primitives from scratch (garbled circuits, OT, DEAP) before reaching the protocol itself.

**Structure:**
- Phase 1: MPC-TLS (Client + Notary jointly execute TLS with Server)
- Phase 1.5: Notarization (integral, given its own phase)
- Phase 2: Selective Disclosure
- Phase 3: Data Verification

**Diagram quality:** Excellent. Includes:
- Garbled circuit AND gate diagrams (before/after encryption)
- Schematic MPC-TLS workflow (Client ↔ Notary ↔ Server)
- Protocol flow sequence diagrams

**Why it matters:** TLSNotary is the MPC-based alternative to Reclaim's proxy approach. vlayer (the authors) are a major production implementer. This paper is the best single document for understanding what the whole zkTLS landscape is actually doing cryptographically.

---

### [4] zkTLS Day at Devconnect 2025
**Organizer:** TLSNotary  
**Date:** November 19, 2025  
**Location:** Buenos Aires, Argentina (Devconnect 2025)  
**URL:** https://tlsnotary.org/zktls-day/

**What it is:** A full-day conference bringing together the four major zkTLS protocol teams — vlayer, Primus Labs, Reclaim Protocol, and TLSNotary — for technical talks and hands-on workshops.

**Agenda highlights:**
- *zkTLS Fundamentals* (Thomas, TLSNotary) — evolution of zkTLS; TEE vs. proxy vs. MPC tradeoffs
- *Building Online Trust, On-Chain* (Maciek Kalka, vlayer) — on-chain attestation design space
- *Cryptography of zkTLS* (Xiang Xie, Primus Labs) — Ferret, QuickSilver, OT, Garbled Circuits
- *The OTHER Hard Part* (0xWildHare, Opacity)
- Use case demos: Mansa (instant liquidity via deposit proofs), Bring ID (proof of personhood via MPC-TLS), TLShare (zkTLS → MPC/FHE workflows)

**Workshop tutorials (all public):**
- Primus Labs: https://github.com/primus-labs/zkTLS-tutorial
- Reclaim Protocol: https://youtu.be/wvcZPSiqn5Y
- TLSNotary: https://tlsnotary.org/zktls-day-tlsnotary-tutorial/
- vlayer GitHub Contribution Verifier: https://github.com/vlayer-xyz/github-contribution-verifier-demo/blob/main/TUTORIAL.md

**Why it matters:** Best single source for understanding the competitive landscape and how Reclaim positions vs. peers.

---

### [5] zkTLS: Verifiable Data Composability
**Author:** "wisdom" (Shoal Research)  
**Date:** March 10, 2025  
**URL:** https://www.shoal.gg/p/zktls-verifiable-data-composability

**What it is:** A well-structured research explainer covering:
- The TLS provenance problem (why Web2 data can't be exported with integrity)
- zkTLS landscape overview (MPC-TLS, TEE, proxy approaches)
- Web2→Web3 use case framing
- Concrete application examples: Nike verifying marathon participation; Uber Eats cross-platform incentives

**Why it matters:** Best non-academic primer with application-level diagrams and business logic framing. Good for communicating Reclaim's use cases to a general audience.

---

### [6] zk-X509: Privacy-Preserving On-Chain Identity from Legacy PKI via Zero-Knowledge Proofs
**Authors:** Yeongju Bak (Tokamak Network)  
**Date:** March 31, 2026 (arXiv preprint v2)  
**PDF:** https://arxiv.org/pdf/2603.25190

**What it is:** Very recent (2026) paper on using ZK proofs over the existing X.509 certificate infrastructure (4B+ active certs globally) for decentralized on-chain identity — without centralized KYC, NFC scanners, or new DID infrastructure.

**Why it matters:** Adjacent to Reclaim's use cases (identity, credential proofs). Shows where the research frontier is moving: from proving TLS *data content* toward proving TLS *certificate identity*.

---

### [7] DiStefano Protocol: Commitments and ZK Attestations over TLS 1.3
**Authors:** Brave Research  
**Date:** December 4, 2024  
**URL:** https://brave.com/blog/distefano/

**What it is:** Brave's proposed Designated-Commitment TLS (DCTLS) protocol — a three-party handshake variant that lets users generate ZK proofs of TLS session data for a designated verifier. Also referred to as 3PH (three-party handshake) or zkTLS.

**Why it matters:** Browser-native angle on the problem. Brave is one of the few teams approaching this from the browser side rather than the SDK side.

---

### [8] zkTLS: Zero-Knowledge TLS (Singh et al., December 2025)
**URL:** https://www.emergentmind.com/topics/zero-knowledge-transport-layer-security-zktls  
**Date:** December 19, 2025

**What it is:** Formalizes zkTLS for Lightning Network balance attestations. Integrates MPC, SNARKs, and TEEs. Provides Theorem 1 security reduction: if an adversary can forge zkTLS proofs, they break either TLS PRF security, SNARK soundness, or the notary signing key.

---

## PART 2: CLAUDE × BLENDER PIPELINE

---

### [9] Claude for Creative Work (Official Anthropic Announcement)
**Date:** April 28, 2026 (updated May 1, 2026)  
**URL:** https://www.anthropic.com/news/claude-for-creative-work

**What it is:** Anthropic's official launch of nine creative tool MCP connectors including the official Blender connector. Key details:
- Blender MCP connector built by Blender developers, now officially available for Claude
- Natural-language interface to Blender's full Python API
- Anthropic made a donation to the Blender project in support
- Connector is MCP-based and works with other LLMs too (open standard)
- Other connectors: Adobe Creative Cloud, Autodesk Fusion, Affinity by Canva, SketchUp, Splice, Resolume, Ableton

**Also announced:** Claude Design (Anthropic Labs) for software UX exploration, exporting to Canva. Education partnerships with RISD, Ringling College, and Goldsmiths.

---

### [10] blender-mcp — Official GitHub Repository
**Author:** ahujasid (community, MIT License)  
**URL:** https://github.com/ahujasid/blender-mcp  
**Install:** `uvx blender-mcp`

**What it is:** The reference open-source MCP server for connecting Claude to Blender. Architecture:
- **Blender Addon** (`addon.py`): Creates a TCP socket server inside Blender to receive/execute commands
- **MCP Server** (`src/blender_mcp/server.py`): Implements Model Context Protocol, connects to addon

**Capabilities:**
- Create, modify, delete 3D objects
- Apply and modify materials and colors
- Camera and lighting control
- Run arbitrary Python code in Blender via Claude (`execute_blender_code` tool)
- Polyhaven asset integration
- Hyper3D Rodin / Hunyuan3D model generation
- Viewport screenshot capture
- Sketchfab upload

**Claude Desktop config:**
```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["blender-mcp"]
    }
  }
}
```

**Requirements:** Blender 3.0+ (4.x recommended), Python 3.10+

**Known limits:** Single connection only (not Claude Desktop + Cursor simultaneously). Complex requests should be decomposed into steps. Sculpt mode uses a different API — organic modeling not supported.

---

### [11] blender-remote — Claude Code Plugin (Headless/CLI)
**Author:** boernmaster  
**URL:** https://www.claudepluginhub.com/plugins/boernmaster-blender-remote-blender-remote  
**Install:** `npx claudepluginhub boernmaster/blender_skill --plugin blender-remote`

**What it is:** The CLI-first, headless Blender control plugin for Claude Code. This is the path for automated rendering pipelines without a GUI.

**Requirements:** Linux + NVIDIA GPU + CUDA drivers, `uv` package manager, Claude Code CLI

**Skills included (4):**
1. `session-setup` — Start/stop/restart headless Blender, troubleshoot MCP connection
2. `scene-materials` — Set up scenes, lighting (studio/three-point/HDRI), assign materials, ambient occlusion
3. `rendering` — Configure Cycles/CUDA, set resolution/samples, render PNG/EXR, create animated GIFs, combine frames to video
4. `cad-import` — Import STP/STEP/STL/OBJ/FBX/GLTF, load CAD assemblies, read Excel BOM for material mapping

**Session management aliases:**
```bash
alias blender-start='cd <project-dir> && source .venv/bin/activate && fuser -k 6688/tcp 2>/dev/null; pkill -f blender 2>/dev/null; sleep 1 && blender-remote-cli start --background --port 6688'
alias blender-stop='fuser -k 6688/tcp 2>/dev/null; pkill -f blender 2>/dev/null'
alias blender-restart='blender-stop && sleep 1 && blender-start'
```

**Two-terminal workflow:** Terminal 1 runs `blender-start` (keeps Blender headless); Terminal 2 runs `claude` with plugin active.

---

### [12] 2 Ways to Create 3D Models with Claude Code
**Author:** Awesome Claude Community  
**URL:** https://awesomeclaude.ai/how-to/create-3d-with-claude

**What it is:** Quick comparison guide for the two main Claude Code → Blender approaches:

| Approach | MCP Server | Best For | Install |
|---|---|---|---|
| Filesystem + Blender Scripts | `anthropics/mcp-server-filesystem` | Script authoring, procedural geometry | `npx @modelcontextprotocol/server-filesystem` |
| Shell + Blender CLI | `anthropics/mcp-server-shell` | Headless rendering, batch processing | `npx @modelcontextprotocol/server-shell` |

**Example CLI invocation:**
```bash
blender --background --python your_script.py
```

**Example prompt:**
> "Create a Blender Python script that generates a spiral staircase with customizable step count and radius."

---

### [13] Claude Blender MCP Connector Setup Guide
**URL:** https://blendermcp.org/setup/claude  
**Date:** April 2026

**What it is:** Community setup guide covering Claude Desktop, Claude Code, and Anthropic API paths for Blender MCP. Confirms Claude Pro ($20/mo) gives significantly better results for complex 3D scenes vs. free tier. Also documents Ollama local model option for zero-API-cost setup.

---

## PART 3: RECOMMENDED READING ORDER

For building zkTLS visuals, read in this order:

1. **Reclaim Whitepaper v2.0** — understand what you're visualizing
2. **DECO** — understand the cryptographic foundation and where the ZK magic actually lives
3. **TLSNotary Review (vlayer)** — get the MPC detail and best diagrams in the field
4. **Shoal Research** — understand the use-case framing for general audiences
5. **zkTLS Day agenda** — understand the competitive positioning

For building with Claude + Blender:

1. **Start** with `blender-mcp` (GUI, fast iteration) on Claude Desktop
2. **Prototype** your zkTLS scene concepts in dialogue with Claude
3. **Migrate** to `blender-remote` (headless) via Claude Code for automated rendering
4. **Render pipeline** uses Shell MCP + `blender --background --python` for batch output

---

*All sources fetched and verified May 9, 2026.*
