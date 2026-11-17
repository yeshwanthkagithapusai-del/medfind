# MediFind Branding & Favicon Report
**MediFind – Phase 9: Branding & Visual Identity**

---

## 1. Brand Identity & Design Concept

- **Brand Name**: **MediFind**
- **Core Value Proposition**: Location-based medicine discovery, real-time pharmacy inventory intelligence, and transparent customer-to-pharmacy inquiries.
- **Design Metaphor**: A unified medical technology symbol combining:
  1. **Location Pin (Map Pin)**: Tapered teardrop contour representing geographic proximity, nearby pharmacy discovery, and Leaflet map routing.
  2. **Medical Cross**: The universally recognized symbol of healthcare, clinics, and accredited pharmaceutical dispensaries.
  3. **Medicine Capsule / Pill**: A diagonal two-tone capsule motif embedded within the cross junction, symbolizing pharmacotherapy and prescription availability.

### Color Palette

| Token | Hex Value | Usage |
|-------|-----------|-------|
| **Deep Navy** | `#102A43` / `#0B1D3A` | Primary brand foundation, navigation bar, high-contrast borders |
| **Primary Medical Teal** | `#0EA5A4` | Primary brand accent, verified badges, action buttons |
| **Bright Cyan / Turquoise** | `#00D2D3` / `#38BDF8` | Pin glow highlights, "Find" wordmark emphasis, pill top half |
| **Clinical Pure White** | `#FFFFFF` | Medical cross, typography on dark backgrounds, pill bottom half |
| **Slate Gray** | `#64748B` / `#94A3B8` | Subtitles, taglines, descriptive metadata |

---

## 2. Brand Asset Inventory

All brand assets are saved in the project's standard static directory `static/images/`:

| File Name | Format | Dimensions | Purpose |
|-----------|:------:|:----------:|---------|
| `medifind-icon.svg` | SVG Vector | 512x512 | Standalone high-resolution app icon with rounded squircle base and drop shadow |
| `favicon.svg` | SVG Vector | 64x64 | Ultra-crisp, high-contrast vector favicon for modern desktop/mobile browsers |
| `medifind-logo.svg` | SVG Vector | 340x70 | Horizontal logo with emblem and wordmark for light backgrounds |
| `medifind-logo-white.svg` | SVG Vector | 340x70 | Horizontal logo with emblem and white wordmark for dark navigation bars |
| `favicon-32x32.png` | PNG Raster | 32x32 | Standard desktop browser tab favicon (anti-aliased with Lanczos resampling) |
| `favicon-192x192.png` | PNG Raster | 192x192 | Android Chrome home screen bookmark and PWA manifest icon |
| `apple-touch-icon.png` | PNG Raster | 180x180 | Apple iOS Safari home screen bookmark icon with squircle container |
| `favicon.ico` | Multi-res ICO | 16/32/48 | Legacy desktop browser icon container |

---

## 3. Template Integration

### 3.1 Browser Head Favicon Links (`templates/base.html`)

```html
<!-- MediFind Brand Favicons & App Icons -->
<link rel="icon" type="image/svg+xml" href="{% static 'images/favicon.svg' %}">
<link rel="icon" type="image/png" sizes="32x32" href="{% static 'images/favicon-32x32.png' %}">
<link rel="icon" type="image/png" sizes="192x192" href="{% static 'images/favicon-192x192.png' %}">
<link rel="apple-touch-icon" sizes="180x180" href="{% static 'images/apple-touch-icon.png' %}">
<link rel="shortcut icon" href="{% static 'images/favicon.ico' %}">
```

### 3.2 Navigation Bar Integration (`templates/base.html`)

```html
<a class="navbar-brand navbar-brand-logo d-flex align-items-center gap-2" href="{% url 'home' %}">
  <img src="{% static 'images/medifind-icon.svg' %}" alt="MediFind Icon" width="34" height="34" class="d-inline-block rounded-2 shadow-sm">
  <span class="fw-bold tracking-tight text-white fs-4">Medi<span style="color: #00D2D3;">Find</span></span>
</a>
```

### 3.3 Footer Branding Integration (`templates/base.html`)

```html
<div class="navbar-brand-logo mb-3 text-white d-flex align-items-center gap-2">
  <img src="{% static 'images/medifind-icon.svg' %}" alt="MediFind Logo" width="28" height="28" class="rounded-1">
  <span class="fw-bold tracking-tight text-white fs-5">Medi<span style="color: #00D2D3;">Find</span></span>
</div>
```

---

## 4. Verification

- All HTTP asset endpoints tested and returning HTTP 200:
  - `/static/images/favicon.svg` → 200 OK
  - `/static/images/favicon-32x32.png` → 200 OK
  - `/static/images/favicon-192x192.png` → 200 OK
  - `/static/images/apple-touch-icon.png` → 200 OK
  - `/static/images/medifind-icon.svg` → 200 OK
- Automated test `test_01_favicon_and_branding_in_base_template` in `tests/test_e2e_workflows.py` passed.
