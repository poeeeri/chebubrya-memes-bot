# Security Lab

This project uses three automated security checks:

- SAST: Bandit for Python source analysis.
- DAST: OWASP ZAP Baseline Scan against a local HTTP target.
- SCA: pip-audit for dependency vulnerability analysis.

Reports are saved in `security-reports/`.

## SAST

Bandit is configured in `bandit.yaml`. The configuration enables multiple Python security rules, including hardcoded secrets, unsafe deserialization, shell injection, weak crypto, SQL injection patterns and broad exception handling.

Run:

```powershell
python -m bandit -r src -c bandit.yaml -f txt -o security-reports/bandit-report.txt
python -m bandit -r src -c bandit.yaml -f json -o security-reports/bandit-report.json
```

Example finding fixed:

- `B110 try_except_pass` in `src/memes_bot/vector_store.py`.
- The old code silently ignored every exception during Chroma collection reset.
- The fix logs the exception instead of swallowing it completely.

## DAST

The Telegram bot itself does not expose a traditional HTTP UI, so the lab includes a small dynamic target in `src/security_lab/dast_target.py`. It gives OWASP ZAP an HTTP surface to scan and demonstrates the same hardening ideas that would be used for a production health endpoint.

Start hardened target:

```powershell
$env:PYTHONPATH="src"
python -m security_lab.dast_target --host 127.0.0.1 --port 8080
```

Run OWASP ZAP Baseline Scan from another terminal:

```powershell
docker run --rm `
  --network host `
  -v "${PWD}\security-reports:/zap/wrk/:rw" `
  ghcr.io/zaproxy/zaproxy:stable `
  zap-baseline.py -t http://127.0.0.1:8080 -r zap-report.html -J zap-report.json
```

If Docker Desktop on Windows does not support `--network host`, expose the target on all interfaces and scan `host.docker.internal`:

```powershell
$env:PYTHONPATH="src"
python -m security_lab.dast_target --host 0.0.0.0 --port 8080
```

```powershell
docker run --rm `
  -v "${PWD}\security-reports:/zap/wrk/:rw" `
  ghcr.io/zaproxy/zaproxy:stable `
  zap-baseline.py -t http://host.docker.internal:8080 -r zap-report.html -J zap-report.json
```

To prove that the scanner reacts to weaknesses, run the intentionally weak mode:

```powershell
$env:PYTHONPATH="src"
python -m security_lab.dast_target --host 0.0.0.0 --port 8080 --vulnerable
```

Then scan `http://host.docker.internal:8080/echo?q=<script>alert(1)</script>`. The hardened mode sends security headers such as CSP, `X-Frame-Options`, `X-Content-Type-Options` and `Referrer-Policy`.

## SCA

`pip-audit` checks vulnerabilities in `requirements.txt`.

Run:

```powershell
python -m pip_audit -r requirements.txt --cache-dir .pip-audit-cache -f json -o security-reports/pip-audit-report.json
python -m pip_audit -r requirements.txt
```

If local `requirements.txt` auditing needs network access or is slow, audit the installed virtual environment:

```powershell
python -m pip_audit --local --cache-dir .pip-audit-cache -f json -o security-reports/pip-audit-report.json
python -m pip_audit --local --cache-dir .pip-audit-cache
```

## CI/CD

`.github/workflows/security.yml` runs SAST, SCA and DAST automatically on push and pull request. The workflow uploads reports as artifacts.