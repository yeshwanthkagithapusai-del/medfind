# Hosting Platform Comparison & Recommendation
**MediFind – Phase 10: Production Deployment Preparation**

---

## 1. Executive Summary

This report evaluates practical hosting platforms for the MediFind healthcare platform. The evaluation considers deployment simplicity, managed PostgreSQL availability, cost predictability, SSL management, and suitability for an academic / capstone engineering project evaluation.

**Recommendation**: **Render** is recommended as the optimal deployment platform for MediFind.

---

## 2. Platform Comparison Matrix

| Criteria | Render (Recommended) | Railway | Linux VPS (DigitalOcean / AWS / Hetzner) |
|----------|:--------------------:|:-------:|:----------------------------------------:|
| **Target Architecture** | PaaS (Container / Git-native) | PaaS (Nixpacks / Git-native) | IaaS (Unmanaged Linux VM) |
| **Setup Complexity** | Very Low (1-click via `render.yaml`) | Low (CLI / GitHub UI) | High (Manual Nginx, Gunicorn, systemd, SSL, UFW) |
| **Managed PostgreSQL** | Built-in (1-click connection string) | Built-in plugin | Self-hosted (manual install & tuning) |
| **SSL / HTTPS** | Automatic (Let's Encrypt managed) | Automatic | Manual (`certbot` & cron renewal) |
| **Static File Serving** | Native via WhiteNoise | Native via WhiteNoise | Nginx reverse-proxy configuration |
| **Free Tier / Evaluation** | Free tier for Web & PostgreSQL | $5 trial credit (requires credit card) | No free tier ($4–$6/month minimum) |
| **Estimated Monthly Cost** | **$0** (Free Tier) to **$7/mo** (Starter) | ~$5–$10/month (Usage-based) | ~$4–$6/month (Flat rate) |
| **Maintenance Overhead** | Zero OS maintenance | Zero OS maintenance | Ongoing kernel, package & security patching |
| **Suitability for College Demo** | **Excellent (Highest)** | Good | High administrative burden |

---

## 3. Detailed Platform Analysis

### Option A: Render (Recommended)

#### Why Render is the Best Fit:
1. **Infrastructure as Code**: MediFind includes a ready-to-use [`render.yaml`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/render.yaml) blueprint specification that automatically provisions both the Python web application and the managed PostgreSQL database in a single step.
2. **Standardized Build Script**: Uses [`build.sh`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/build.sh) which automatically executes dependency installation, WhiteNoise static file compilation (`collectstatic`), and schema migrations (`migrate`).
3. **Zero-Configuration SSL**: Automatic HTTPS certificates with TLS 1.3 termination, eliminating manual certificate renewal.
4. **Predictable Cost**: The free tier provides sufficient compute (512 MB RAM) and a free PostgreSQL instance, ideal for university evaluation panels. For permanent high-availability hosting, the starter tier is only \$7/month.

#### Limitations to Keep in Mind:
- Free web instances spin down after 15 minutes of inactivity and take ~30–50 seconds to wake on the initial request (cold start).
- Free PostgreSQL instances expire after 30 days unless upgraded to the \$7/month starter tier.

---

### Option B: Railway

#### Pros:
- Fast build times via Nixpacks.
- Excellent real-time log streaming and interactive metrics.
- Seamless GitHub integration.

#### Cons:
- Pricing is usage-based (vCPU + RAM per second), which can lead to unpredictable invoices if traffic surges.
- Requires credit card verification upfront to unlock services, even for academic evaluation.

---

### Option C: Linux VPS (DigitalOcean Droplet / AWS Lightsail / Hetzner)

#### Pros:
- Full root access to the operating system.
- Fixed monthly cost (\$4–\$6/month).
- No cold starts or resource throttling.

#### Cons:
- Requires manual installation and configuration of:
  - Python 3.11 virtual environment
  - PostgreSQL server and database user permissions
  - Nginx reverse-proxy configuration (`/etc/nginx/sites-available/medifind`)
  - Gunicorn systemd service (`/etc/systemd/system/gunicorn.service`)
  - Certbot for Let's Encrypt SSL certificates
  - Firewall (`ufw allow 'Nginx Full'`)
- High maintenance overhead and risk of misconfiguration during project demonstrations.

---

## 4. Final Recommendation & Decision

For a final-year CSE project demonstration and capstone submission, **Render** offers the ideal balance of:
- **Zero infrastructure management**
- **Automated git-push deployments**
- **Native blueprint orchestration via `render.yaml`**
- **Zero-cost evaluation tier**
