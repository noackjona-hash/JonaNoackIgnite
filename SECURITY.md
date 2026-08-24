# Security Policy

## 1. Governance and Scope

This document defines the security policies and coordinated disclosure process for the **IGNITE Medical Imaging Suite**. Adherence to these guidelines is mandatory for all contributors, maintainers, and security researchers.

---

## 2. Supported Versions

Security updates and patches are provided exclusively for the actively supported versions listed below:

| Version | Supported | Severity Threshold for Backports | End of Life (EOL) Date |
| :--- | :--- | :--- | :--- |
| **3.2.x** | Yes | Low / Medium / High / Critical | Active Support (Jugend forscht 2026) |
| **3.1.x** | Yes | High / Critical Only | 2026-12-31 |
| **< 3.1** | No | None | EOL |

---

## 3. Reporting a Vulnerability

**Please do not publicly report security vulnerabilities in public issue trackers, pull requests, social media, or public forums.**

### 3.1 Submission Channel
Security vulnerabilities should be reported privately through:
* **Primary:** GitHub Private Vulnerability Reporting via the [*Security -> Advisories*](https://github.com/noackjona-hash/JonaNoackIgnite/security/advisories) tab of this repository.
* **Alternative:** Direct confidential inquiry to the project maintainer on GitHub.

### 3.2 Required Information
To assist in rapid triage and verification, please include:
1. **Type of Issue:** (e.g., Memory safety, In-memory data leak, Authentication bypass, Path traversal).
2. **Affected Component:** Module, function, or API endpoint.
3. **Step-by-Step Proof of Concept (PoC):** Minimal reproducible test case.
4. **Impact Analysis:** Potential impact on confidentiality, integrity, or availability.
5. **Proposed Mitigation:** If available, recommended patches or workarounds.

Automated vulnerability scanner dumps without a verified PoC will be declined.

---

## 4. Response SLAs and Vulnerability Management Lifecycle

We adhere to the following target response windows:

| Phase | Description | Target Window |
| :--- | :--- | :--- |
| **First Response** | Acknowledgment of receipt and triage assignment. | **24 hours** |
| **Triage & Validation** | PoC verification and severity assessment. | **72 hours** |
| **Status Updates** | Progress reports sent to the reporter. | Every **5 business days** |
| **Patch Release** | Release of verified security fix. | **7 to 90 days** |

### 4.1 Remediation Timelines by Severity

* **Critical (CVSS 9.0 - 10.0):** Patch released within **7 days**.
* **High (CVSS 7.0 - 8.9):** Patch released within **14 days**.
* **Medium (CVSS 4.0 - 6.9):** Patch released within **45 days**.
* **Low (CVSS 0.1 - 3.9):** Patch included in the next regular release cycle (maximum **90 days**).

---

## 5. Coordinated Disclosure Policy

To protect users and clinical evaluation environments:
1. **Embargo Period:** The reporter agrees to keep vulnerability details confidential for up to **90 days** following initial notification or until an official patch has been published.
2. **Early Disclosure:** Coordinated public disclosure may occur earlier upon mutual agreement once a fix is released.
3. **Attribution:** Verified security reports will be credited in the release notes upon request.

---

## 6. Safe Harbor and Rules of Engagement

Security research conducted in good faith is supported. We commit not to pursue legal action against security researchers who adhere to the following rules:

### Allowed:
* Testing against local, isolated builds and non-production synthetic test datasets.
* Halting tests immediately upon encountering sensitive or personal data and securely purging any temporary artifacts.

### Strictly Prohibited:
* Performing Denial of Service (DoS/DDoS) attacks or automated high-frequency stress testing against production systems.
* Social engineering, phishing, or physical security attacks.
* Exfiltrating data beyond the minimum necessary to demonstrate a proof of concept.
