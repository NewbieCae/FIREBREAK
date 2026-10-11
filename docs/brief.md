# Finswag — Secure Horizons brief

Notion page: https://app.notion.com/p/3f58c3ea1f5e81e88164e25c35e8475e

**Finswag — Secure Horizons, Team 14, Track 1 "Guardians of Value".** The team's scoping and coordination space. Track 1 is confirmed in the brief; the product to build and the role split are still to be validated.

# Project and sources
- **Private GitHub repo:** [Sc4rville/finswag](https://github.com/Sc4rville/finswag)
- **Main source:** email "\[CODEX\] brief hackathon Secure Horizons - Track 1 Guardians of Value (Avalanche + AWS)", received 2026-10-10 at 12:26 (Europe/Paris).
- **Project name:** the email mentioned "secureswag"; the repo and this page use "finswag", as currently requested by Yann.
- The event and technical information below is taken from the email. The [Candidate Guide](https://app.notion.com/p/Candidate-Guide-Track-Guidance-EN-3f400920c77e81beb3b4fad01fc5eeda) is not accessible with the current Notion connection; its guidance is reported from the brief.

# Hackathon context
- **Event:** Secure Horizons, organized by UTOPIA × KRYPTOSPHERE × ESSEC MetaLab.
- **Venue:** ESSEC Cergy, 3 avenue Bernard Hirsch.
- **Announced format:** 150 builders, 36 hours, 3 tracks; teams of up to 5 people. Free meals and accommodation.
- **Check-in:** 2026-10-10 at 09:00 (Europe/Paris); presentation from 10:00 to 11:00; team formation from 10:50 to 11:30.
- **Hacking:** announced start 2026-10-10 at 11:00 (Europe/Paris); announced end 2026-10-11 at 17:00 (Europe/Paris).
- **Track change:** possible until the checkpoint on 2026-10-10 at 18:30 (Europe/Paris); spots may be capped.
- **Team:** Team 14, AWS team. The brief reports Yann's decision at 12:25: go for Track 1.
- **Announced prizes:** about €15,000 in total, plus infrastructure credits. Split per track and judging criteria not specified in the email.
- **Support cited:** France 2030 (ANR-23-CMAS-0020) / NextGenerationEU.

# Brief — Track 1 "Guardians of Value"
## Goal
Build a defensive solution that secures financial systems, transactions or digital assets: **monitor, detect and respond to threats targeting money**, from banking to DeFi.
## Audience and need
Finance, blockchain, anti-fraud and compliance. The cited guide describes defenders drowning in alerts and false positives, unsupervised AI agents, tool and privilege abuse, as well as needs for detection, response and cyber insurance.
## Expected framework
- **Blue Team** approach, focused on defense.
- Address at least one **NIST CSF 2.0** function, ideally **Detect** or **Respond**.
- Frameworks cited: MITRE ATT&CK, MITRE ATLAS, MITRE D3FEND and OWASP Top 10 for Agentic Applications.
- **Track 1 jury:** Team1 / Avalanche, KPMG, KRYPTOSPHERE France.
- Angle suggested in the brief for KPMG: compliance, auditability and false-positive reduction.
- According to the email, the guide provides no specific challenge, scoring grid or per-track prize.
## Other tracks, for context
- Track 2 "Defenders Augmented": AI × cyber; jury GitGuardian, ESSEC MetaLab, KPMG.
- Track 3 "Uncharted Frontiers": open topics; jury Bpifrance, ESSEC Alumni, UTOPIA.

# Technical resources
## Avalanche / Team1
The brief plans Avalanche for the on-chain part, with demonstrable utility: proof, traceability or audit log.
- **Network:** Fuji testnet, EVM-compatible C-Chain.
- **Possible tools:** Solidity, MetaMask or Core, Hardhat or Foundry.
- **Announced chain ID:** 43113; test token AVAX.
- [Fuji Explorer](https://testnet.snowtrace.io)
- [Builder Hub — sign-up](https://build.avax.network/signup?ref=HGURW)
- [Faucet](https://build.avax.network/console/primary-network/faucet)
- The [Chainlist 43113](https://chainlist.org/chain/43113) link provided by the organizers describes the network. The candidate endpoint `https://api.avax-test.network/ext/bc/C/rpc` is still **to be tested**; the brief does not present it as confirmed by the organizers.
- If the faucet is not enough: contact Yassir at the address given in the organizers' email with the wallet's public EVM address.
- Use a wallet dedicated to the hackathon. Record the addresses of deployed contracts in GitHub.

## AWS / Bedrock
- Temporary, free account, isolated per team.
- **Single announced region:** `us-east-1`.
- Bedrock, Bedrock AgentCore and basic AWS services; models cited in the email: Claude, Amazon Nova, GPT-5.x, Llama and Mistral.
- **No GPU.** Stay under about one request per second per person.
- One team member must fill in the Claude usage form in the Bedrock console.
- The unique Team 14 access link is in the organizers' email of October 10 at 11:03. Retrieve it from Yann's inbox.
- **Kiro:** announced offer of 100 codes of 1,000 credits, first come first served; to be claimed before Sunday October 11 at midnight according to the email: [Kiro promotion](https://pulse.amazon/promotion/L9OJAMMY).
- The AWS account will be deleted at the end: back up the code to GitHub regularly and record a demo video before the end.

# Hackathon rules taken from the email
- Test and attack only what our team deploys in its own account.
- Do not target another team, the ESSEC network, AWS or an external site.
- No denial of service, malware, phishing or model jailbreaking.
- Use synthetic data and fake secrets, for example `FLAG{team14-canary}`; no real personal data.
- Never share a real key or seed phrase.
- Push code to GitHub at least every hour.
- Discord links must be taken from the official channel or screen on site: the brief notes two different invites in the organizers' emails.

# Product ideas — to be validated with the team
The four ideas below are proposals from the brief; **none has been validated by Yann**.
## A — Anti-fraud alert triage
Synthetic transaction stream; a Bedrock agent that classifies and explains alerts and aims to reduce false positives. Hash of decisions and evidence anchored in a Fuji contract for a verifiable audit.
## B — Contract and transaction monitor
Monitoring of Fuji transactions: drains, suspicious approvals and abnormal calls. Risk assessment with an LLM; response by alert or by pausing a demo contract via a Pausable circuit breaker. Scenarios only target our own contracts.
## C — Guardrail for paying AI agents
Proxy that controls the permissions, limits and recipients of an agent executing payments. On-chain allowlist and limits policy; verifiable action log and detection of privilege or tool abuse.
## D — Compliance audit log
Periodic anchoring of log hashes on Fuji, integrity checker and AI summary. Demonstrate traceability and evidence usable for an audit or cyber insurance.
## Recommendation contained in the email
Discuss a **B + C** combination: detection and response on contracts, with a supervised AI agent. Prepare a clear three-minute demo; the official duration is still to be confirmed.

# Proposed work plan — to be confirmed
1. **Scoping:** choose the scenario, validate the scope, roles, stack and success criteria; get AWS and Fuji access.
2. **First path:** synthetic data, Fuji demo contract, first Bedrock analysis and minimal interface.
3. **Integration:** connect suspicious event, explanation, guardrail or response, and on-chain proof.
4. **Validation:** normal / suspicious scenarios, failure behavior and measurement of the expected effect.
5. **Delivery:** README, contract addresses, recorded video and pitch. Align milestones with the official schedule and submission format.

# Team and access
Access (Notion, GitHub) is managed outside this repo; personal addresses are not stored here.

# Actions and open questions
- [x] Find and integrate the brief sent to Codex.
- [x] Create the Finswag page and link the existing repo.
- [ ] Invite the three addresses to Notion with edit access.
- [ ] Choose the product and define the MVP scope.
- [ ] Confirm the number of members, the stack, the resources already available and the role split.
- [ ] Ask the organizers: Track 1 scoring grid, prizes per track, demo length, exact submission format and deadline.
- [ ] Check AWS access, the Claude form, the dedicated wallet and the Fuji RPC.
- [ ] Record deployed contracts; push at least every hour.
- [ ] Record the demo before the AWS account is deleted.

# Repo layout
- `src/`: source code.
- `assets/`: resources.
- `scripts/`: utilities.
- `docs/`: brief and documentation.
