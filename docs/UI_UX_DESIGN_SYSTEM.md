# MediFind UI/UX Design System Specification

**Document Version:** 1.0  
**Phase:** Professional UI/UX Redesign  
**Date:** November 2026  
**System:** MediFind (Healthcare SaaS Platform)  
**Lead Designer & Architect:** Senior UI/UX Designer & Frontend Architect  

---

## 1. Design System Philosophy

The MediFind design system transforms the application into an enterprise-grade healthcare SaaS platform. The user interface prioritizes clarity, trust, accessibility, and visual calmness:
* **Medical Credibility:** Deep navy blues combined with fresh medical teals communicate authority, clinical precision, and patient safety.
* **Scan-ability & Visual Hierarchy:** High-contrast typography, clear data cards, distinct status pill badges, and structured layouts ensure patients and pharmacists can make rapid, informed decisions under time-sensitive conditions.
* **Modern Minimalism:** Clean white surfaces, subtle 1px border dividers, soft elevation shadows, and rounded container geometry (`border-radius: 12px` and `8px`) create a contemporary SaaS experience without overwhelming animations.

---

## 2. Core Color Palette Tokens

The design system is strictly anchored to the following WCAG 2.1 AA accessible color tokens, declared as global CSS custom properties in `static/css/styles.css`:

```css
:root {
  /* Brand Foundation */
  --med-primary: #102A43;        /* Deep Medical Navy: Navbar, Headings, Primary CTA */
  --med-primary-dark: #091a2c;   /* Darker Navy: Footer, Dark States */
  --med-primary-light: #1e3a5f;  /* Elevated Navy */
  
  /* Brand Secondary & Accent */
  --med-secondary: #0EA5A4;      /* Medical Teal: Secondary CTA, Highlights, Trust Indicators */
  --med-secondary-dark: #0f766e; /* Deep Teal Hover State */
  --med-accent: #38BDF8;         /* Cyan Blue: Map Markers, Active Tabs, Interactive Focus */
  
  /* Semantic Health Status Colors */
  --med-success: #16A34A;        /* In-Stock / Confirmed / Approved */
  --med-success-bg: #DCFCE7;     /* Soft Green Tint for Badges/Pills */
  --med-warning: #F59E0B;        /* Low Stock (< 10) / Pending Verification */
  --med-warning-bg: #FEF3C7;     /* Soft Amber Tint for Badges/Pills */
  --med-danger: #DC2626;         /* Out of Stock / Cancelled / Rejected */
  --med-danger-bg: #FEE2E2;      /* Soft Red Tint for Badges/Pills */
  
  /* Neutral Surfaces & Backgrounds */
  --med-bg: #F8FAFC;             /* Cool Soft Slate Background */
  --med-surface: #FFFFFF;        /* Pure White Card Surface */
  --med-border: #E2E8F0;         /* Subtle Gray Border */
  --med-border-focus: #38BDF8;   /* Input Focus Border */
  
  /* Typography Text Tokens */
  --med-text-primary: #1E293B;   /* Slate 800: High-Contrast Body & Headings */
  --med-text-secondary: #64748B; /* Slate 500: Subtitles, Meta Information, Table Headers */
  --med-text-muted: #94A3B8;     /* Slate 400: Placeholders & Disclaimers */
  
  /* Elevation Shadows & Radius */
  --med-radius-sm: 6px;
  --med-radius-md: 10px;
  --med-radius-lg: 14px;
  --med-radius-pill: 9999px;
  
  --med-shadow-sm: 0 1px 2px rgba(16, 42, 67, 0.05);
  --med-shadow-md: 0 4px 12px rgba(16, 42, 67, 0.08);
  --med-shadow-lg: 0 10px 25px rgba(16, 42, 67, 0.12);
}
```

---

## 3. Typography & Hierarchy

* **Primary Font Family:** `'Plus Jakarta Sans', system-ui, -apple-system, sans-serif`.
* **Weights:**
  - `400 (Regular)`: General paragraph copy, body text, data table cells.
  - `500 (Medium)`: Form labels, navigation links, secondary badges.
  - `600 (SemiBold)`: Card titles, table headers, button labels.
  - `700 (Bold)`: Page headings, hero subtitles, stat figures.
  - `800 (ExtraBold)`: Hero main header, primary brand logo.

---

## 4. Global UI Component Standards

### 4.1 Navigation Bar & Top Banner
* **Compliance Banner:** Top-level soft amber banner (`#fef3c7`) informing users of demonstration mode and non-emergency triage status.
* **Brand Logo:** Distinct pill icon with dual-capsule geometry (`#38bdf8`) beside `MediFind` in bold typography.
* **Role-Aware Navigation:** Dynamic menu rendering based on user role (`CUSTOMER`, `PHARMACY`, `ADMIN`). Unauthenticated visitors see `Patient Sign Up` and `Register Pharmacy` action pills.

### 4.2 Healthcare Stat Tiles (`.stat-tile`)
* Standardized 4-tile grid on dashboards displaying:
  - Numeric metric in primary/success/warning/danger color (`2rem`, `font-weight: 700`).
  - Secondary label (`0.85rem`, `font-weight: 500`, `#64748b`).
  - Modern rounded square icon container (`48px x 48px`, `border-radius: 10px`, matching 10% opacity tint).

### 4.3 Semantic Stock Badges (`.badge-in-stock`, `.badge-low-stock`, `.badge-out-stock`)
* Color-coded rounded pills (`padding: 0.35rem 0.75rem`) featuring a miniature glowing indicator dot (`6px x 6px` circular pseudo-element).
* In Stock: Green (`#16a34a` on `#dcfce7`).
* Low Stock: Amber (`#f59e0b` on `#fef3c7`).
* Out of Stock: Red (`#dc2626` on `#fee2e2`).

### 4.4 Data Tables (`.med-table`)
* Borderless table cells with soft horizontal dividers (`#e2e8f0`).
* Uppercase, tracked table headers (`font-size: 0.75rem`, `letter-spacing: 0.5px`, `color: #64748b`).
* Hover highlight effect on rows (`rgba(16, 42, 67, 0.02)`).

### 4.5 Leaflet Map Component
* Full responsive container (`#map`) bounded with rounded borders (`12px`) and subtle shadow.
* Custom popup styling with medicine name, pharmacy name, formatted address, direct call links, and live stock badges.

---

## 5. Responsive Breakpoints

* **Desktop / Large Screens (`>= 1200px`):** Full 4-column stat grids, split search & map layout (sidebar + interactive map).
* **Laptops / Tablets (`768px - 1199px`):** 2-column dashboard grids, collapsible filter sidebar, touch-friendly form inputs.
* **Mobile Devices (`< 768px`):** Single-column stacked layouts, horizontal scrolling tables with responsive wrappers, full-width action buttons.
