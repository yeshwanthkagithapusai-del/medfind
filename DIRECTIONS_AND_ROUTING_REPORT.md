# MEDIFIND — DIRECTIONS AND ROUTING REPORT

**Report Date:** November 17, 2026  
**Auditor & Architect:** Senior GIS Engineer & Privacy Specialist  
**Document Code:** MF-DOC-ST5-ROUTING  
**System Component:** `pharmacies/services.py` (`build_external_directions_url`) & UI Templates  

---

## 1. Executive Summary

Healthcare consumers navigating to hospitals or retail pharmacies require trustworthy, turn-by-turn road navigation.

MediFind's design implements an ethical, reliable, and privacy-respecting directions strategy:
1. **Zero Route Fabrication Policy**: MediFind does not synthesize simulated routes, fictitious road geometry, or fabricated drive times.
2. **Explicit Straight-Line Distance Disclaimer**: Distances displayed on the platform are explicitly calculated using the Haversine formula and clearly labeled as straight-line estimates ("as-the-crow-flies").
3. **Legitimate External Navigation**: Full routing is delegated to industry-standard external routing providers (Google Maps and OpenStreetMap / FOSSGIS OSRM) via authenticated deep links.
4. **Strict Permission Consent**: Geolocation is never silently captured or transmitted. Users must explicitly click "Use My Current Location" and grant browser permission.

---

## 2. Directions URL Architecture

The `build_external_directions_url()` service function constructs canonical URLs based on the presence or absence of the user's origin coordinates.

```
Parameters:
  - dest_lat, dest_lng (Destination facility coordinates)
  - user_lat, user_lng (Optional user location coordinates)
  - service: 'google' | 'osm'
```

### 2.1 Google Maps Navigation Protocol
- **When User Origin GPS is Present**:
  Uses the official Google Maps Universal Cross-Platform Intent:
  ```
  https://www.google.com/maps/dir/?api=1&origin={user_lat},{user_lng}&destination={dest_lat},{dest_lng}&travelmode=driving
  ```
  *Behavior:* Launches Google Maps mobile app on Android/iOS or web directions in Chrome/Edge with live turn-by-turn driving routing pre-loaded.
- **When User Origin is Absent (Manual Search)**:
  Uses the Google Maps Search Intent:
  ```
  https://www.google.com/maps/search/?api=1&query={dest_lat},{dest_lng}
  ```
  *Behavior:* Pins the exact destination on Google Maps, allowing the user to select their preferred departure point or public transit route.

### 2.2 OpenStreetMap (FOSSGIS OSRM) Protocol
- **When User Origin GPS is Present**:
  Uses the FOSSGIS Open Source Routing Machine (OSRM) engine:
  ```
  https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={user_lat}%2C{user_lng}%3B{dest_lat}%2C{dest_lng}
  ```
  *Behavior:* Generates an open-access road route computed using OpenStreetMap road network topologies.
- **When User Origin is Absent**:
  Uses the OpenStreetMap Marker and Bounding Box URL:
  ```
  https://www.openstreetmap.org/?mlat={dest_lat}&mlon={dest_lng}#map=16/{dest_lat}/{dest_lng}
  ```

---

## 3. Privacy & Location Permission Handling

### 3.1 Strict Opt-In Policy
- MediFind does **not** invoke `navigator.geolocation.getCurrentPosition()` automatically on page load.
- Location capture is triggered **only** when the user explicitly clicks the "Use My Current Location" button.
- User coordinates are stored in client-side hidden inputs during the search session and are **never** persisted to user profiles or database logs without explicit consent.

### 3.2 Error Code Handling Matrix

| Error Code | Browser Condition | MediFind UI Behavior |
| :--- | :--- | :--- |
| `1: PERMISSION_DENIED` | User declined location prompt or browser blocked GPS | Displays an alert banner: *"Location access was denied. You can search manually using City, State, or Pincode below."* No crash or blocking popup. |
| `2: POSITION_UNAVAILABLE`| Device GPS or IP triangulation failure | Displays: *"Location is currently unavailable. Please enter your City or Pincode."* |
| `3: TIMEOUT` | GPS satellite acquisition exceeded 10-second deadline | Displays: *"Location request timed out. Please retry or enter your City or Pincode."* |

---

## 4. Straight-Line vs Actual Road Distance Comparison

To maintain data integrity and patient trust, MediFind enforces clear distinction between spatial calculations:

| Attribute | Straight-Line (Haversine) | Actual Road Routing |
| :--- | :--- | :--- |
| **Calculation Location** | In-database / In-memory within MediFind backend | External Navigation Engines (Google / OSRM) |
| **Formula** | Great-circle arc distance on sphere ($R = 6,371\text{ km}$) | Dijkstra / Contraction Hierarchies on road graph |
| **Traffic / Road Factors**| Road detours, one-ways, terrain, and traffic are excluded | Real-time traffic, tolls, road closures factored |
| **Platform Transparency** | Displayed with explicit subtext: `~X.XX km (straight-line)` | Full turn-by-turn opened via "Directions" action |
| **Latency** | $< 0.1\text{ ms}$ per facility | Handled asynchronously by external map provider |
