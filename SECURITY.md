# Security Policy

## Overview

Orion Range is an open-source Cyber Range Orchestrator designed for authorized and controlled cybersecurity training environments.

Security, responsible disclosure, and safe usage are fundamental to this project.

---

## Supported Versions

Orion Range is currently in early development.

Security fixes will be applied to the `main` branch first.
Future stable releases will document supported versions explicitly.

---

## Reporting a Security Vulnerability

If you discover a **security vulnerability**, please do **not** open a public GitHub issue.

Security vulnerabilities include (but are not limited to):

- Authentication or authorization bypass
- Privilege escalation
- Exposure of credentials or sensitive configuration
- Remote code execution
- Unsafe provider interactions
- Any issue that could compromise real infrastructure

Instead, report vulnerabilities privately:

📧 Email: contato@kra2sec.com  
Subject: `[Orion Range] Security Vulnerability Report`

Please include:

- A clear description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Suggested mitigation (if known)
- Relevant logs or screenshots

We will acknowledge receipt as soon as possible and coordinate responsible disclosure.

---

## Responsible Disclosure Process

1. Vulnerability is reported privately.
2. Maintainers validate and assess severity.
3. A fix is developed and tested.
4. A patch is released.
5. A public advisory may be published (if appropriate).

We ask researchers to allow reasonable time for remediation before public disclosure.

---

## Reporting Bugs (Non-Security)

General bugs, feature requests, and improvements should be submitted via **GitHub Issues**.

Open collaboration is encouraged for all non-sensitive topics.

---

## Intended Use

Orion Range is intended exclusively for:

- Authorized cybersecurity training
- Academic research
- Defensive capability development
- Controlled simulation environments

It must not be used for unauthorized access or illegal activities.

The maintainers assume no responsibility for misuse.

---

## Security Best Practices for Deployment

When deploying Orion Range:

- Run in isolated infrastructure
- Restrict network exposure
- Protect hypervisor credentials
- Use strong authentication mechanisms
- Monitor logs and activity
- Avoid exposing management interfaces publicly

---

## Disclaimer

Orion Range is provided "AS IS", without warranty of any kind.

Users are responsible for ensuring lawful and authorized use.
