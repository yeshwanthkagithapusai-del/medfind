# Production Deployment Guide
**MediFind – Phase 10: Step-by-Step Deployment Instructions**

---

## 1. Overview

This guide provides end-to-end instructions for deploying MediFind to production. It covers:
- **Part A**: Deployment to Render (Recommended PaaS).
- **Part B**: Local Production Simulation on Windows (PowerShell).
- **Part C**: Post-Deployment Operational Verification.

---

## 2. Part A: Deploying to Render (Recommended)

### Step 1: Push Code to GitHub / Git Remote
Ensure all project files, including [`render.yaml`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/render.yaml), [`build.sh`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/build.sh), and [`Procfile`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/Procfile), are committed and pushed to your GitHub repository.

```bash
git add .
git commit -m "Prepare MediFind for production deployment"
git push origin main
```

---

### Step 2: Deploy via Render Blueprint (1-Click Setup)

1. Log into your account at [https://dashboard.render.com](https://dashboard.render.com).
2. Click **New +** in the top navigation bar and select **Blueprint**.
3. Connect your GitHub repository (`medifind_project`).
4. Render will detect the [`render.yaml`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/render.yaml) file in the root directory and propose creating two resources:
   - **`medifind`** (Web Service running Python 3.11 with Gunicorn)
   - **`medifind-postgres`** (Managed PostgreSQL Database)
5. Click **Apply**.
6. Render will automatically:
   - Provision the PostgreSQL database and inject the `DATABASE_URL` environment variable.
   - Run [`build.sh`](file:///c:/Users/yeshw/OneDrive/Desktop/medfind_project/build.sh) to install dependencies, compile static files with WhiteNoise, and apply migrations.
   - Start Gunicorn using the start command: `gunicorn config.wsgi:application`.
   - Issue a free Let's Encrypt SSL/TLS certificate for your `https://medifind.onrender.com` domain.

---

### Step 3: Create Initial Production Admin Account

Once the deployment shows **Live**, open the **Shell** tab in the Render web dashboard and create your administrator superuser:

```bash
python manage.py createsuperuser
```

Enter your production admin username, email, and a secure password.

---

## 3. Part B: Local Production Simulation on Windows (PowerShell)

Before deploying to the cloud, you can simulate production settings locally on Windows.

### Step 1: Open Windows PowerShell

Navigate to the project root directory:

```powershell
cd c:\Users\yeshw\OneDrive\Desktop\medfind_project
```

### Step 2: Set Production Environment Variables

Run the following commands in PowerShell to simulate production mode:

```powershell
# Disable Debug Mode
$env:DEBUG="False"

# Generate and set a secure 50+ character SECRET_KEY
$env:SECRET_KEY="c9f8v2m8xk2qwze1r4t7y0u3i6o9p2a5s8d1f4g7h0j3k6l9z8x7c6v5b4n3m9k"

# Set allowed hosts and trusted origins for local testing
$env:ALLOWED_HOSTS="localhost,127.0.0.1"
$env:CSRF_TRUSTED_ORIGINS="http://localhost:8000,http://127.0.0.1:8000"

# Disable SSL redirect for local HTTP testing
$env:SECURE_SSL_REDIRECT="False"
```

### Step 3: Compile Static Assets with WhiteNoise

```powershell
python manage.py collectstatic --noinput
```

Output:
```
136 static files copied to 'c:\Users\yeshw\OneDrive\Desktop\medfind_project\staticfiles'.
```

### Step 4: Run Django Deployment Check

```powershell
python manage.py check --deploy
```

Expected output:
```
System check identified no issues (0 silenced).
```

### Step 5: Start Local Server in Production Mode

```powershell
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/` in your browser. Verify:
- The site renders correctly with full CSS and images served by WhiteNoise.
- Favicon displays in the browser tab.
- Debug error pages are disabled (test by navigating to a non-existent URL like `/does-not-exist/` to verify the standard 404 response).

---

## 4. Part C: Post-Deployment Operational Verification

After deploying to Render:
1. **Homepage Check**: Open `https://<your-service>.onrender.com/` and confirm the landing page loads over HTTPS with the green lock icon.
2. **Branding Check**: Verify the MediFind icon displays in the browser tab and the navbar renders the logo.
3. **Database Connectivity**: Log in with your admin credentials at `/accounts/login/` or `/admin/` to verify PostgreSQL reads and writes.
4. **Search Verification**: Search for a medicine (e.g. `Paracetamol`) to verify query execution on PostgreSQL.
5. **Static Assets**: Inspect browser DevTools (Network tab) and confirm `styles.css` and `favicon.svg` are served with `Cache-Control: max-age=31536000` (WhiteNoise immutable caching).
