# ATS & Recruiter Scoring Report

**Candidate:** Deepak Arora — *Deepak_Arora_Resume_Zscaler_Principal_SDE.pdf* (2 pages, 1,070 words)
**Target role:** Principal Software Development Engineer — Zscaler, San Jose, CA (Hybrid)
**Compensation band:** $185,500 – $265,000 base
**Report date:** August 30, 2026
**Scoring lenses:** (A) Machine / ATS keyword-and-parse scoring · (B) Human recruiter & hiring-manager assessment

---

## 1. Headline Result

| Lens | Score | Band | Interpretation |
|---|---|---|---|
| **A. ATS Machine Score** | **68 / 100** | 🟡 Borderline | Parses cleanly and ranks mid-pile. Below the ~75–80 threshold where a keyword-ranked ATS surfaces a resume in the recruiter's top slate for a protocol-dense requisition. |
| **B. Recruiter / Hiring-Manager Score** | **60 / 100** | 🟡 Conditional | Credible Principal-level systems engineer with exceptional AI/ML depth, but missing the named protocol stack and Go, which are the JD's load-bearing requirements. |
| **Blended (40% ATS / 60% Human)** | **63 / 100** | 🟡 Tier 2 | Likely reaches a human reviewer at a company hungry for AI-forward systems architects; unlikely to survive a strict requirement-gate screen. |

**Minimum-qualification gate: 3 of 5 met, 2 not met.** The two unmet items (Item 2 — protocol/routing stack; Item 3 — Go) are the ones most commonly hard-coded as knockout filters for this class of requisition.

---

## 2. Minimum Qualification Gate (JD "What We're Looking for")

| # | Minimum Qualification | Status | Evidence Found in Resume |
|---|---|---|---|
| 1 | Bachelor's/Master's (preferred) in CS or related + **10+ years** in system engineering for high-performance networking | 🟡 **Partial Pass** | MCA (Master of Computer Applications, GGSIP 2004); B.Sc. Mathematics (DU 2001). 20+ years stated; dated history 2005 → present. Degree is a *related* field but not literally "Computer Science" — a literal degree-string matcher may not score it. Networking-specific years ≈ 2005–2014 hands-on + architecture ownership thereafter. |
| 2 | Expertise in **Linux kernel networking (L2/L3), stateful firewalls, NAT, network drivers, BGP/OSPF/PIM**, and **VLANs, DHCP, DNS, SSL, DTLS, QUIC, IPsec, GRE, WireGuard** | 🔴 **Not Met** | Present: Linux kernel modules, network/device drivers, L3 forwarding & routing, NAT, packet classification, TCP/IP + IPv6 (RFC 2461), DNS caching, 802.3/802.11. **Absent: BGP, OSPF, PIM, stateful firewall, VLAN, DHCP, SSL/TLS, DTLS, QUIC, IPsec, GRE, WireGuard.** 12 of 18 named technologies have zero occurrence in the document. |
| 3 | Proficiency in **Go** and **Python** | 🔴 **Not Met** | Python: strong and repeatedly evidenced (ML pipelines, GitHub projects, tooling). **Go: zero occurrences.** Languages listed are C, C++, Python, Bash, ARM/x86 assembly. |
| 4 | Foundational understanding of AI/ML; experience leveraging/securing/positioning AI-driven solutions | 🟢 **Exceeds** | Far beyond "foundational": PyTorch, CUDA optimization & profiling, NVIDIA DGX A100 / Tesla, Whisper ASR + LLM inference pipelines, embeddings & clustering, LangGraph multi-agent pipelines, model-benchmark framework, GPU-accelerated catalog matching. |
| 5 | Strong communication & collaboration with cross-functional teams; designing scalable systems | 🟢 **Pass** | 25+ cross-functional HW/FW/SW teams led; architecture review boards established; design and architecture specifications authored for ODM and internal build; works directly with a product manager; engineer development through formal review. |

---

## 3. Lens A — ATS Machine Score (68 / 100)

Machine scoring treats the resume as a document to be parsed and keyword-ranked. No inference, no benefit of the doubt: a term either appears or it does not.

### 3.1 Component Breakdown

| Component | Weight | Earned | Notes |
|---|---:|---:|---|
| Weighted JD keyword coverage | 55 | **29.8** | 54.1% weighted coverage (73 of 135 weighted points) — see §3.2 |
| Job-title alignment | 10 | **8.0** | Resume headline reads "Principal Software Engineer"; PDF metadata title is literally "Principal Software Development Engineer" (exact match, indexed by some parsers). Current *employment* title is "Senior AI Systems Architect" — not a Principal-SDE string. |
| Years-of-experience extraction | 8 | **8.0** | "20+ years" explicit in summary; continuous dated roles 2005 → present. Comfortably clears the 10+ gate. |
| Education extraction | 7 | **5.0** | Master's-level degree present and parseable. Loses points because the degree string is "Master of Computer Applications," not "Computer Science"; strict degree-taxonomy matchers may classify it as unmatched. |
| Location / work-model match | 5 | **3.0** | Requisition is San Jose hybrid. Resume header: "Irving, TX (open to San Jose, CA — hybrid)". Geo-filters keying on candidate city will down-rank; the explicit relocation statement recovers partial credit with human-reviewed pipelines. |
| Parse-ability & file hygiene | 10 | **9.0** | Excellent. Tagged PDF 1.7, LibreOffice-generated, embedded subset TrueType fonts, **zero images**, no tables, no multi-column layout, linear reading order verified. Contact line, email, phone, LinkedIn and GitHub all extract cleanly. Minor deduction: interpunct (·) separators in the contact/header line and mixed date formats ("2014 – 2017" vs "February 2026 – Present") can confuse older regex-based date and contact parsers. |
| Standard section headers | 5 | **5.0** | SUMMARY · CORE TECHNICAL SKILLS · PROFESSIONAL EXPERIENCE · EARLIER EXPERIENCE · PATENTS, PUBLICATIONS & OPEN SOURCE · EDUCATION & CERTIFICATIONS. All map to canonical ATS sections. |
| **Total** | **100** | **67.8 → 68** | |

### 3.2 Weighted Keyword Coverage by Category

Terms extracted from the JD, weighted 2–5 by prominence and by whether they sit in the minimum or preferred qualifications. Matching was done case-insensitively with word-boundary anchoring on acronyms (this is how the false positive "GRE" inside "greenfield" was excluded).

| Category | Earned / Possible | Coverage | Verdict |
|---|---:|---:|---|
| Role Expectations (spec authoring, mentoring, troubleshooting, cross-functional, PM/PRD, optimization) | 24 / 24 | **100.0%** | 🟢 Perfect |
| Kernel & Datapath Engineering | 20 / 23 | **87.0%** | 🟢 Strong |
| Cloud & Infrastructure | 10 / 12 | **83.3%** | 🟢 Strong |
| AI/ML | 6 / 8 | **75.0%** | 🟢 Strong |
| Security | 5 / 7 | **71.4%** | 🟡 Adequate |
| Languages (Go, Python) | 4 / 9 | **44.4%** | 🔴 Weak |
| Compliance & Certification | 2 / 12 | **16.7%** | 🔴 Weak |
| Protocols (VLAN/DHCP/DNS/SSL/DTLS/QUIC/IPsec/GRE/WireGuard/L2VPN/VRRP) | 2 / 32 | **6.3%** | 🔴 Critical gap |
| Routing Protocols (BGP/OSPF/PIM) | 0 / 8 | **0.0%** | 🔴 Critical gap |
| **TOTAL** | **73 / 135** | **54.1%** | 🟡 Below competitive threshold |

### 3.3 Keyword Hit Register

**Matched (28 terms)**

| Term | Weight | Surface form found in resume |
|---|---:|---|
| Linux kernel-based networking | 3 | "Linux kernel modules", "Linux kernel" |
| L3 networking | 3 | "L3 forwarding and routing" |
| Network drivers | 3 | "network and device drivers", "MoCA 2.0 network driver" |
| NAT | 3 | "L3 forwarding and routing, NAT, packet classification" |
| Data path / datapath | 3 | "datapath" (×4: summary, skills, Verizon bullet, headline) |
| High-performance networking | 3 | "DPDK kernel-bypass", "high-throughput I/O", "packet-processing offload" |
| L2 networking | 2 | "802.3 Ethernet", "802.11 Wi-Fi PHY/MAC" |
| DNS | 2 | "DNS caching", "STB DNS caching" |
| Python | 4 | Skills + GitHub projects |
| AI/ML | 3 | "AI/ML", "ML pipeline", "LLM", "embeddings" |
| AI/ML frameworks | 3 | "PyTorch", "CUDA", "LangGraph" |
| Zero Trust | 3 | "Zero-trust architecture", "zero-trust security" |
| Design & functional specification documents | 3 | "design and architecture specifications", "production design and architecture specifications" |
| Troubleshooting / debugging expertise | 3 | "deep field troubleshooting", "Root-caused systemic field failures", "Debugged" |
| Cross-functional collaboration | 3 | "25+ cross-functional HW/FW/SW teams" |
| Mentoring / coaching engineers | 3 | "developed engineers through formal architecture review" |
| AWS · Azure · Docker · Kubernetes | 2 ea | Skills line: "AWS, GCP, Azure, Docker, Kubernetes" |
| Virtualization / containerization | 2 | "Android containerization at the MEC tier" |
| Security features / hardening | 2 | "secure boot and chain of trust", "ARM TEE", "firmware hardening", "endpoint security" |
| Certification program ownership | 2 | "Certification & Compliance Programs", "from design review through lab submission and grant" |
| Unit testing & automation | 2 | "QA automation" |
| Scalable / resilient systems | 2 | "Scaled channel fulfillment 6.6×", "scalable" |
| Software design principles | 2 | "system decomposition", "reference architectures" |
| Product Managers / PRD review | 2 | "leads a 10-person engineering team and a product manager" |
| Performance optimization | 2 | "performance tuning against latency and throughput budgets" |
| Architects / Solution Architects | 2 | "Senior AI Systems Architect", "Architecture lead" |

**Not matched (23 terms — 62 weighted points forfeited)**

| Term | Weight | JD source | Impact |
|---|---:|---|---|
| **Go / Golang** | 5 | Min qual #3 | 🔴 Knockout risk — explicitly named language |
| **BGP** | 3 | Min qual #2 | 🔴 Named routing protocol |
| **OSPF** | 3 | Min qual #2 | 🔴 Named routing protocol |
| **PIM** | 2 | Min qual #2 | 🔴 Named routing protocol |
| **Stateful firewalls** | 3 | Min qual #2 | 🔴 Core datapath function |
| **IPsec** | 3 | Min qual #2 + preferred | 🔴 Core tunneling |
| **GRE** | 3 | Min qual #2 + preferred | 🔴 Core tunneling (verified absent — "greenfield" produced a false positive on naive substring matching) |
| **WireGuard** | 3 | Min qual #2 + preferred (named twice) | 🔴 Double-weighted in JD |
| **TLS** | 3 | Min qual #2 + preferred | 🔴 Absent entirely |
| **DTLS** | 3 | Min qual #2 + preferred (named twice) | 🔴 Absent entirely |
| **QUIC** | 3 | Min qual #2 + preferred (named twice) | 🔴 Absent entirely |
| **SSL** | 2 | Min qual #2 | 🔴 Absent entirely |
| **FIPS** | 3 | Role expectation + preferred | 🔴 Federal certification |
| **FedRAMP** | 3 | Role expectation + preferred | 🔴 Federal certification |
| **Common Criteria** | 2 | Role expectation | 🔴 Federal certification |
| **SOC2** | 2 | Role expectation | 🔴 Compliance framework |
| VLANs | 2 | Min qual #2 | 🟡 |
| DHCP | 2 | Min qual #2 | 🟡 |
| L2VPN | 2 | Preferred qual | 🟡 |
| VRRP / HA protocols | 2 | Preferred qual | 🟡 |
| Tunneling protocols (generic) | 2 | Preferred qual | 🟡 |
| Multitenant architecture | 2 | Role description | 🟡 Zscaler's stated architectural context |
| Predictive threat detection | 2 | Preferred qual #1 | 🟡 Has field-issue detection, not threat detection |
| Cloud security / SSE / SASE | 2 | Company context | 🟡 |

---

## 4. Lens B — Recruiter / Hiring-Manager Score (60 / 100)

Human scoring rewards demonstrated depth, transferable capability, and evidence quality — and penalizes hedged claims and domain distance in ways a keyword parser cannot see.

| # | Dimension | Weight | Earned | Assessment |
|---|---|---:|---:|---|
| 1 | Linux kernel & datapath engineering depth | 22 | **14** | Genuine, verifiable kernel-level pedigree: full TCP/IP + IPv6 stack port including RFC 2461 Neighbor Discovery (Conexant), Linux kernel modules and real-time middleware (Intel), MoCA PHY/MAC driver fault debugging, L3 routing throughput via Cavium Octeon hardware offload (HCL). **The reservation is recency and mode.** The deepest hands-on kernel networking sits in 2005–2014. The recent DPDK vs. SmartNIC/DPU work is explicitly annotated "(evaluated)" and "(architecture assessment)" — an honest disclosure that a hiring manager will read as comparative analysis rather than production datapath implementation. |
| 2 | Required protocol & routing stack | 18 | **4** | This is the JD's densest and most specific requirement, and the resume answers roughly a fifth of it. NAT, DNS, IPv6/ND and L3 forwarding are real. BGP/OSPF/PIM, stateful firewall, IPsec/GRE/WireGuard, and the entire TLS/DTLS/QUIC transport-security family have no representation. For a Zero Trust Exchange datapath role, TLS/DTLS/QUIC and tunneling are not peripheral — they are the traffic the product inspects. |
| 3 | Go + Python proficiency | 10 | **5** | Python is unambiguous and production-grade. Go is absent. Twenty years of C/C++ systems work makes Go a short ramp in reality, but the JD names it as a minimum qualification, and a Principal hire is expected to be productive in the team's languages on arrival, not after a ramp. |
| 4 | AI/ML applied within the functional domain | 12 | **10** | The strongest differentiator on this resume, and unusually well-matched to Zscaler's "AI-forward enterprise" positioning. Real GPU engineering (CUDA tuning, DGX A100 8×A100/640GB, cost-per-hour-of-audio optimization), real pipelines (Whisper ASR + LLM over 2,000+ hours of noisy narrowband telephony), real production AI architecture (LangGraph multi-agent with output governance, traceability, human review queue, readiness gate). Loses 2 points only because the preferred qual asks specifically for AI applied to *kernel-level networking optimization and predictive threat detection*; the applied domain here is field-issue detection and catalog automation. Adjacent, not identical. |
| 5 | Scale, complexity & quantified impact | 12 | **9** | Consistently quantified: 4M+ device fleet, 3M+ Fios Video and 1M+ OTT devices, 6.6× fulfillment scaling (300 → 2,000 orders/day), ~300K incremental orders, 24 parallel I/O streams under contention, ~15s update-time reduction, 2,000+ hours of audio. Almost every bullet carries a number — well above the norm for the level. Deduction reflects that the scale is *device-fleet and consumer-platform* scale, not multi-tenant cloud-service scale (Zscaler's frame is 15M users, 185 countries, world's largest security data lake). |
| 6 | Principal-level seniority signals | 12 | **11** | Excellent and directly mapped to the JD's role expectations. Authored production design and architecture specifications that ODM and internal teams built against (JD: "creating design and functional specification documents"). Led 25+ cross-functional HW/FW/SW teams. Established architecture review practice and developed engineers through it (JD: "coach and mentor junior team members"). Works directly with a product manager and owns roadmap/build-vs-buy/TCO. Granted US patent 10,606,605 B2 plus a filed provisional — meaningful at a company that markets 100+ patents. |
| 7 | Security-domain relevance to Zero Trust Exchange | 8 | **4** | Zero-trust appears twice and is architecturally substantiated (edge-native virtual mobile computing platform with zero-trust security at the MEC tier). Supporting security breadth is real: secure boot and chain of trust, ARM TEE, firmware hardening, SAST/DAST, penetration testing, Black Duck SCA, and an enterprise Windows endpoint security platform for 500–1,000 endpoints. But this is *device and firmware* security. There is no inline traffic inspection, no proxy/gateway, no SSE/SASE, no cloud security service experience — the substance of the product this role builds. |
| 8 | Federal certification & compliance experience | 3 | **1** | Genuine, deep certification *program ownership* — FCC Part 15 (B/C/E), UL 62368-1, Wi-Fi Alliance, Bluetooth SIG, RoHS, Energy Star, CPSC, run from design review through lab submission and grant. The process discipline transfers well to FIPS/FedRAMP/Common Criteria/SOC2 audit cycles. But the JD names federal *security* certifications specifically, and none appear. Credit for transferable process, not for domain. |
| 9 | Logistics & availability | 3 | **2** | Irving, TX with explicit "open to San Jose, CA — hybrid," and prior San Jose tenure at Verizon (2014–2017) makes the relocation credible rather than aspirational. Still a relocation for a hybrid-mandated role. |
| | **Total** | **100** | **60** | |

---

## 5. Role-Expectation Traceability

| JD Role Expectation | Coverage | Supporting Evidence |
|---|---|---|
| Design, develop, optimize the system incl. **networking and security features** for high-performance applications | 🟡 Partial | High-throughput storage datapath (24 parallel I/O streams, fragmentation mitigation, write coalescence); L3 forwarding offload; latency-budget tuning. Security features are firmware/device-side, not network-inline. |
| Create **design and functional specification documents**; unit testing and automation | 🟢 Strong | "Authored the production design and architecture specifications … that ODM and internal teams built against." QA automation and AI-assisted development standards established at SwifTrade. Unit testing not named explicitly. |
| Apply strong software design principles and **deep troubleshooting** to deliver scalable, resilient improvements to **Zero Trust Security Services** | 🟡 Partial | Troubleshooting is a standout strength (systemic root-cause across a 4M+ fleet: MoCA link instability, 802.11 interference, A/V dropouts, DVR faults, update freezes; DGX/ProLiant failure diagnosis via BMC/iLO and IPMI). Zero Trust *Security Services* specifically — no direct experience. |
| Work with Engineering Architects, PMs, Customers, Solution Architects; **review PRDs** | 🟢 Strong | Cross-functional leadership across 25+ teams; leads a PM; architecture review boards; vendor/ODM management. "PRD" itself does not appear. |
| **Coach and mentor** junior team members; ensure highest quality deliverables | 🟢 Strong | "developed engineers through formal architecture review"; established architecture review practice and AI-assisted development standards. |
| Ensure federal certifications — **FIPS, FedRAMP, Common Criteria, SOC2** | 🔴 Gap | Extensive certification program ownership, but exclusively regulatory/product-safety (FCC, UL, Wi-Fi Alliance, Bluetooth SIG, Energy Star, RoHS, CPSC). Zero federal security certification exposure. |

### Success-Profile Alignment (JD "Who You Are")

| Trait | Signal | Evidence |
|---|---|---|
| Thrives in ambiguity | 🟢 Strong | Greenfield AI-native platform, zero to production in five months; independent R&D initiative advanced to prototype, whitepaper and provisional patent. |
| Acts like an owner | 🟢 Strong | "Platform architecture owner"; owned certification programs end to end; authored the business case quantifying call-deflection opportunity — strategy through hands-on execution, which is precisely the "dynamic range" the JD asks for. |
| Problem-solver | 🟢 Strong | Systemic field-failure root-cause driven back into platform architecture rather than point fixes. |
| High-trust collaborator | 🟢 Strong | 25+ cross-functional teams; formal architecture review as a feedback mechanism. |
| Learner | 🟢 Strong | Pivoted from embedded systems into applied GPU/LLM engineering; four recent certifications (GenAI Ready 2024, UPenn 2025, Harvard 2021 ×2). |

---

## 6. Screening Flags

| Flag | Severity | Detail |
|---|---|---|
| Go absent from a minimum qualification | 🔴 High | Most likely single cause of automated rejection or recruiter-screen fallout. |
| 12 of 18 named protocols/routing technologies absent | 🔴 High | Minimum qualification #2 is the JD's most specific requirement and is largely unanswered. |
| No transport-security experience (SSL/TLS/DTLS/QUIC) | 🔴 High | Central to a Zero Trust Exchange datapath role; named in both minimum and preferred qualifications. |
| No FIPS/FedRAMP/Common Criteria/SOC2 | 🟠 Medium | An explicit role responsibility, not merely preferred. |
| Recent kernel-datapath work is hedged as "(evaluated)" / "(architecture assessment)" | 🟠 Medium | Honest and to the candidate's credit, but it caps how much recent hands-on kernel credit a reviewer will assign. |
| Domain distance: consumer video/CPE and edge platforms vs. multi-tenant cloud security service | 🟠 Medium | Transferable systems fundamentals; different product physics and operating scale. |
| Current role tenure of ~7 months (Feb 2026 → present) | 🟡 Low | A candidate leaving a platform-owner role inside a year will draw one screening question. Prior tenures are long (Verizon 11 years, Intel 4), so the overall pattern is stable. |
| Geography: Irving, TX for a San Jose hybrid requisition | 🟡 Low | Mitigated by an explicit relocation statement and prior San Jose tenure. |
| Degree string is "Master of Computer Applications," not "Computer Science" | 🟡 Low | Equivalent in substance; may not match a literal degree-taxonomy filter. |
| Mixed date formats across roles | 🟡 Low | "2014 – 2017" vs. "February 2026 – Present" — minor parser inconsistency risk. |

---

## 7. Where the Resume Outperforms the Requisition

Recorded for balance — these are areas where the candidate exceeds what the JD asks for, and they are the reason the blended score lands in Tier 2 rather than lower:

- **AI/ML depth vastly exceeds the "foundational understanding" bar.** The JD asks for foundational familiarity and lists AI-framework integration as *preferred*. This candidate has shipped GPU-accelerated production pipelines, tuned CUDA workloads against cost-per-unit targets, operated DGX A100 hardware, and built a governed multi-agent LLM architecture. For an organization describing itself as an "AI-forward enterprise" seeking "innovators who actively use AI to amplify their impact," this is a differentiating asset rather than a checkbox.
- **Specification authorship and architecture review** map one-to-one onto two separate role expectations, with concrete artifacts (specs that ODMs built against) rather than assertions.
- **Quantification density.** Nearly every bullet carries a measured outcome, which materially raises human-reviewer confidence in the claims.
- **Granted patent and filed provisional** carry real weight at a company that foregrounds its 100+ patents.
- **End-to-end certification program ownership** — while the certifications are the wrong family, the demonstrated ability to run a compliance program from design review to grant is the scarce, transferable half of the FIPS/FedRAMP requirement.

---

## 8. Methodology & Verification

- **Source documents:** the supplied 2-page PDF resume and the full JD text, both parsed in full. Resume text extracted with `pdftotext` in both layout-preserving and linear reading-order modes; the two extractions were compared to confirm the document linearizes correctly for an ATS.
- **Structural inspection:** `pdfinfo`, `pdffonts`, and `pdfimages` were used to confirm the PDF is tagged, contains no images or embedded graphics, uses embedded subset TrueType fonts, and has no forms or JavaScript — all favorable to machine parsing.
- **Keyword extraction:** 53 weighted terms were drawn from the JD's role expectations, minimum qualifications, preferred qualifications, and company/product framing. Weights of 2–5 reflect prominence, repetition across JD sections, and minimum-vs-preferred placement.
- **Matching:** case-insensitive, with word-boundary anchoring on all acronyms and short tokens. This anchoring is what excluded a naive false positive — a substring search for "gre" matches inside "greenfield," which would have wrongly credited GRE tunneling. Every acronym reported as absent (GRE, NAT, TLS, VLAN, IPsec, FIPS, Go) was re-verified individually with a bounded regex.
- **Score construction:** Lens A weights are fixed before inspection and applied mechanically. Lens B weights reflect how a Principal-level requisition is typically evaluated, with the heaviest weight on the two dimensions the JD itself emphasizes most (kernel datapath depth, and the named protocol stack).
- **Known limitations:** real ATS platforms differ in ranking algorithms, synonym dictionaries, and knockout configuration; a system with a strong synonym graph would credit "TCP/IP stack implementation" toward transport-protocol familiarity, while a strict boolean knockout on "Go" would reject at intake regardless of every other score. Treat 68 as the center of a plausible 60–75 range depending on platform configuration.

---

*Scores reflect the resume as submitted against this specific requisition. They measure document-to-requisition alignment, not the candidate's capability.*
