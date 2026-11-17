# Production Security Checklist & Hardening Guide
**MediFind – Phase 10: Production Deployment Preparation**

---

## 1. Executive Summary

This checklist validates that all production security controls, cryptographic protections, browser security headers, and cookie isolation policies meet enterprise healthcare software standards before deployment.

---

## 2. Security Controls Verification Matrix

| # | Security Control | Configuration Setting | Target Value (Production) | Status | Verification Command |
|:-:|------------------|-----------------------|---------------------------|:------:|----------------------|
| **1** | **Debug Mode Disabled** | `DEBUG` | `False` | ✅ VERIFIED | `python manage.py check --deploy` |
| **2** | **Cryptographic Key** | `SECRET_KEY` | Environment variable (50+ random chars) | ✅ VERIFIED | No hardcoded key fallback in prod |
| **3** | **Host Header Validation** | `ALLOWED_HOSTS` | Explicit domain list (e.g. `.onrender.com`) | ✅ VERIFIED | Rejects unrecognized Host headers |
| **4** | **CSRF Origin Whitelisting** | `CSRF_TRUSTED_ORIGINS` | Explicit HTTPS URLs | ✅ VERIFIED | Verified in `settings.py` |
| **5** | **SSL/HTTPS Redirection** | `SECURE_SSL_REDIRECT` | `True` | ✅ VERIFIED | Forces HTTPS transport |
| **6** | **HSTS Enforcement** | `SECURE_HSTS_SECONDS` | `31536000` (1 Year) | ✅ VERIFIED | `SECURE_HSTS_PRELOAD = True` |
| **7** | **Session Cookie Security** | `SESSION_COOKIE_SECURE` | `True` | ✅ VERIFIED | Only transmitted over HTTPS |
| **8** | **Session Script Protection**| `SESSION_COOKIE_HTTPONLY` | `True` | ✅ VERIFIED | Blocks XSS cookie theft |
| **9** | **CSRF Cookie Security** | `CSRF_COOKIE_SECURE` | `True` | ✅ VERIFIED | Only transmitted over HTTPS |
| **10** | **Clickjacking Guard** | `X_FRAME_OPTIONS` | `'DENY'` | ✅ VERIFIED | Blocks iframe framing |
| **11** | **MIME-Sniffing Guard** | `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | ✅ VERIFIED | Blocks content sniffing |
| **12** | **Reverse Proxy Header** | `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` | ✅ VERIFIED | Informs Django of TLS termination |
| **13** | **Static Asset Caching** | `STORAGES` | `CompressedManifestStaticFilesStorage` | ✅ VERIFIED | WhiteNoise immutable hashing |
| **14** | **Password Hashing** | `PASSWORD_HASHERS` | PBKDF2 with SHA-256 (Django default) | ✅ VERIFIED | `test_security.py` passes |
| **15** | **Zero Sensitive Exposure** | `.gitignore` | `.env`, `db.sqlite3`, `staticfiles/` | ✅ VERIFIED | Clean repository tree |

---

## 3. Secret Key Generation Command

For Windows PowerShell users:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(55))"
```

Example generated key:
```
5xDi_3NW1-lVUd3_GIVc4IPOn-txbgA_e-qjAuj_u6GWlz5k9W28QDIEDMXlt2FbXkPKi_6t5Q
```

> [!CAUTION]
> Never commit `.env` or paste real production secret keys into version control or chat channels.

---

## 4. Reverse Proxy & Edge Termination Details

Render and most modern cloud PaaS providers terminate SSL at their edge load balancer and forward requests to your Gunicorn application over an internal network using HTTP with the `X-Forwarded-Proto: https` header.

MediFind is pre-configured with:
```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

This prevents redirect loops (`ERR_TOO_MANY_REDIRECTS`) while ensuring Django correctly recognizes secure HTTPS connections.
