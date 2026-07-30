# Security Policy

## 1. Governance & Scope

Dieses Dokument definiert die verbindlichen Sicherheitsrichtlinien und den Prozess zum Umgang mit Sicherheitslücken (Vulnerabilities) in diesem Projekt. Die Einhaltung dieser Richtlinien ist für alle Mitwirkenden, Maintainer und externen Sicherheitsforscher bindend.

---

## 2. Supported Versions

Sicherheitsupdates und Patches werden ausschließlich für die unten als unterstützt gekennzeichneten Versionen bereitgestellt. Ältere oder nicht unterstützte Versionen erhalten **keine** Fixes, Audits oder Backports. Nutzer von nicht unterstützten Versionen werden dringend aufgefordert, umgehend auf eine unterstützte Major-/Minor-Version zu aktualisieren.

| Version | Supported          | Severity Threshold for Backports | End of Life (EOL) Date |
| ------- | ------------------ | -------------------------------- | ---------------------- |
| 5.1.x   | :white_check_mark: | Low / Medium / High / Critical   | Active Support         |
| 5.0.x   | :x:                | None                             | EOL (2025-12-31)       |
| 4.0.x   | :white_check_mark: | High / Critical ONLY             | 2026-12-31             |
| < 4.0   | :x:                | None                             | EOL                    |

---

## 3. Reporting a Vulnerability

**Veröffentlichen Sie Sicherheitslücken NIEMALS in öffentlichen Issue-Trackern, Pull Requests, Social Media oder Diskussionsforen.**

### 3.1 Submission Channel
Sicherheitslücken müssen vertraulich gemeldet werden über:
* **Primary:** GitHub Coordinated Disclosure / Private Vulnerability Reporting (über den Tab *Security* -> *Report a vulnerability* dieses Repositories).
* **Alternative (PGP-verschlüsselt):** Sendet eine E-Mail an `security@your-domain.com`.
  * **PGP Key Fingerprint:** `1234 5678 9ABC DEF0 1234 5678 9ABC DEF0 1234 5678` *(Hier Fingerprint einfügen)*

### 3.2 Required Information
Um eine schnelle Bearbeitung zu gewährleisten, **muss** der Report folgende Informationen enthalten:

1. **Type of Issue:** (z. B. RCE, XSS, SQLi, Auth Bypass, Privilege Escalation).
2. **Affected Component:** Genaue Version, Modul oder API-Endpunkt.
3. **Step-by-Step Proof of Concept (PoC):** Vollständige, nachvollziehbare Anleitung zur Reproduktion.
4. **Impact Analysis:** Welches Schadenspotenzial besteht (Vertraulichkeit, Integrität, Verfügbarkeit)?
5. **Mitigation Suggestion:** Falls vorhanden, Vorschläge zur Behebung.

Unvollständige, automatisierte Scanner-Reports ohne manuell verifizierten PoC werden ungelesen abgelehnt.

---

## 4. Response SLAs & Vulnerability Management Lifecycle

Wir verpflichten uns zu folgenden maximalen Reaktionszeiten (Service Level Agreements):

| Phase | Description | Max SLA |
| :--- | :--- | :--- |
| **First Response** | Bestätigung des Eingangs & Zuordnung eines Bearbeiters. | **24 Stunden** |
| **Triage & Validation** | Überprüfung des PoC, CVSS v3.1 Scoring und Erstbewertung. | **72 Stunden** |
| **Status Updates** | Regelmäßige Fortschrittsberichte an den Reporter. | Alle **5 Werktage** |
| **Patch Release** | Veröffentlichung des Patches ab Validierung (strikter Zeitplan unten). | **7–90 Tage** |

### 4.1 Remediation Timelines (nach CVSS-Score)

* **Critical (CVSS 9.0 - 10.0):** Patch innerhalb von **7 Tagen**
* **High (CVSS 7.0 - 8.9):** Patch innerhalb von **14 Tagen**
* **Medium (CVSS 4.0 - 6.9):** Patch innerhalb von **45 Tagen**
* **Low (CVSS 0.1 - 3.9):** Patch im nächsten regulären Release (max. **90 Tage**)

---

## 5. Coordinated Disclosure & Embargo Policy

Um die Sicherheit unserer Nutzer zu gewährleisten, gilt eine **Koordinierte Offenlegungsfrist (Responsible Disclosure)**:

1. **Embargo Period:** Der Reporter erklärt sich bereit, keinerlei Informationen über die Schwachstelle vor Ablauf einer Frist von **90 Tagen** nach der Erstmeldung oder vor dem offiziellen Release eines Patches an Dritte weiterzugeben.
2. **Early Disclosure:** Nach Veröffentlichung des Patches kann die Schwachstelle nach gegenseitiger Absprache öffentlich gemacht werden.
3. **Credit/Hall of Fame:** Validierte Reports werden (sofern vom Reporter gewünscht) in den Release Notes sowie in unserer `SECURITY_HALL_OF_FAME.md` namentlich erwähnt.

---

## 6. Safe Harbor / Rules of Engagement

Gute Sicherheitsforschung ist willkommen. Wir verpflichten uns, keine rechtlichen Schritte gegen Sicherheitsforscher einzuleiten, solange folgende Punkte strikt eingehalten werden:

### :white_check_mark: Allowed / Required:
* Nutzung von Test-Accounts oder lokalen/isolierten Instanzen.
* Sofortiges Einstellen aller Tests bei Entdeckung sensibler Daten (PII, Credentials, Schlüssel).
* Sicheres Löschen aller im Zuge des Tests erlangten Daten nach Abschluss des Falls.

### :x: Strictly Prohibited:
* **Keine** Denial-of-Service (DoS / DDoS) Angriffe oder Stresstests auf Produktivsysteme.
* **Kein** Social Engineering, Phishing oder physische Angriffe auf Mitarbeiter oder Infrastruktur.
* **Keine** Beschädigung, Löschung oder Modifikation von Produktivdaten.
* **Kein** Ausnutzen von Sicherheitslücken über das für den PoC zwingend notwendige Maß hinaus (kein Exfiltrieren großer Datenmengen, Hinterlegen von Web Shells etc.).

---
