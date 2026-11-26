# Dependency and License Record

Project: maps-gui. Copyright (c) 2024-2026 Israel Alalouf. All rights reserved (see LICENSE).
Last full audit: 2026-11-14. Re-run the audit whenever dependencies change materially and before any release,
APK build or public publishing (see CLAUDE.md).

Licenses below were verified from primary sources: package metadata and LICENSE files (Python dist-info, Dart pub
cache), the Flutter NOTICES bundle, Maven POMs, and vendor pages. Items marked UNVERIFIED could not be confirmed.
Full notices: THIRD_PARTY_NOTICES.md.

## Owner decisions (2026-11-14)

| ID | Topic | Decision | Effect |
|---|---|---|---|
| D1 | PyQt5 / PyQtWebEngine are GPL-3.0 | Do not distribute the Desktop app for now | Desktop stays personal use; distributing it later requires PySide6 (LGPL) migration or a Riverbank commercial license |
| D2 | FlightRadar24 ToS (sections 2.3, 10.3) forbids non-official automated access; a FR24 subscription token is hard-coded in the Android app | Keep as is (owner's explicit choice, accepted risk) | Known ToS breach and credential exposure remain; revisit before any wider or public distribution |
| D3 | Open-Meteo free tier is non-commercial only, CC BY 4.0 | Owner confirms non-commercial use; add attribution | Attribution added in Desktop map, weather popup, Android map and weather card |
| D4 | Esri World Imagery (Esri Master License Agreement) | Keep the layer, fix attribution | Official attribution string now shown; whether direct tile access without an ArcGIS account is permitted remains UNVERIFIED |
| D5 | Android launcher icon was the Flutter logo (Google trademark) | Replace with an original icon ("אללוף") | New icon in maps-gui-android-src/android_res, copied by build_apk.ps1 |
| D6 | Copyright year | 2024-2026 | Used in LICENSE, file headers and About screens |
| D7 (2026-11-26) | wa-status uses neonize, an unofficial WhatsApp client (ToS breach, ban risk) | Owner chose neonize and "message to self" after the risks were explained | Dev tool only, not shipped; session data stays local and git-ignored |
| - | Unused files (qwebchannel.js, heatmap.html, mongodb-intro.html, mpm_ballistics.zip) | Keep (owner's choice) | qwebchannel.js (LGPL/GPL, unused) is still distributed with the repository |
| - | Authorship of mpm/, mpm_ballistics.zip, data/projectiles, icons/ | Owner's own work | Treated as All Rights Reserved |
| - | CARTO dark basemap | Fix attribution only | Requests without a CARTO API key may show a watermark |

## Components

Legend - Use: L = linked/imported, B = bundled in a distributable, C = loaded from CDN at runtime, S = web service.
Compatible = compatible with an All Rights Reserved, distributed project.

### Android app (distributed)

| Component | Version | License | Use | Obligations | Compatible | Risk | Status / action |
|---|---|---|---|---|---|---|---|
| Flutter SDK + engine | 3.41.9 | BSD-3-Clause (+ permissive engine deps) | L, B | Ship notices | Yes, with conditions | Low | Notices bundled; About > View licenses added |
| 53 Dart packages (flutter_map, latlong2, http, provider, geolocator, shared_preferences, material_symbols_icons, ...) | per pubspec.lock | BSD-3-Clause / MIT / Apache-2.0 | L, B | Ship notices (Apache: keep NOTICE files if present) | Yes, with conditions | Low | Listed in THIRD_PARTY_NOTICES.md; shown in app |
| CPython (via Chaquopy) | 3.14 | PSF-2.0 | B | Ship license text | Yes, with conditions | Low | Registered in the app's license page |
| Chaquopy | 17.2.0 | MIT | B | Ship notice | Yes, with conditions | Low | Registered in the app's license page |
| AndroidX, Kotlin stdlib, ReLinker | per Gradle | Apache-2.0 | B | Ship license | Yes, with conditions | Low | Registered in the app's license page |
| Google Play services location/base/basement/tasks | 21.2.0 / 18.3.0 / 18.3.0 / 18.1.0 | Android SDK License (proprietary) | B | Follow Google terms | Yes, with conditions | Low | Noted in the app's license page |
| Launcher icon | - | Owner's work (text in Noto Sans Hebrew, OFL 1.1, rasterized) | B | None (font not shipped) | Yes | Low | Replaced Flutter logo (D5) |

### Desktop app (not distributed, D1)

| Component | Version | License | Use | Obligations | Compatible | Risk | Status / action |
|---|---|---|---|---|---|---|---|
| PyQt5, PyQtWebEngine | 5.15.11, 5.15.7 | GPL-3.0 (or Riverbank commercial) | L | Whole app must be GPL when distributed, or buy commercial license | No | High | Not distributed (D1) |
| PyQt5-Qt5, PyQtWebEngine-Qt5 (Qt 5 binaries) | 5.15.2 | LGPL-3.0 | L, B if .venv/exe is shared | License text, allow relinking, source offer | Yes, with conditions | Medium | Only relevant if binaries are distributed |
| PyQt5-sip | 12.17.1 | BSD-2-Clause | L | Notice | Yes, with conditions | Low | - |
| requests | 2.33.0 | Apache-2.0 | L | Notice | Yes, with conditions | Low | - |
| Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click | 3.1.3, 3.1.8, 3.1.6, 3.0.3, 2.2.0, 8.3.3 | BSD-3-Clause | L | Notice | Yes, with conditions | Low | - |
| flask-cors, urllib3, charset-normalizer, blinker, brotli | 6.0.2, 2.5.0, 3.4.4, 1.9.0, 1.2.0 | MIT | L | Notice | Yes, with conditions | Low | - |
| python-dotenv, psutil, idna, colorama | 1.2.2, 7.2.2, 3.11, 0.4.6 | BSD-3-Clause / BSD | L | Notice | Yes, with conditions | Low | - |
| certifi | 2025.10.5 | MPL-2.0 | L | Notice; source of MPL files available upstream (unmodified) | Yes, with conditions | Low | - |
| FlightRadarAPI | 1.4.0 | MIT (package itself says "educational purposes") | L | Notice | Yes, with conditions | Low (code) | Service terms: see FlightRadar24 below |
| curl_cffi | 0.16.1 | MIT; bundled native libraries UNVERIFIED | L (optional) | Notice | Yes, with conditions | Low | Used to impersonate a browser TLS fingerprint against FR24 (D2) |

### Browser libraries (Desktop map, loaded from unpkg CDN)

| Component | Version | License | Use | Obligations | Compatible | Risk | Status / action |
|---|---|---|---|---|---|---|---|
| Leaflet | 1.9.4 | BSD-2-Clause | C | Keep notice; keep "Leaflet" attribution prefix | Yes, with conditions | Low | - |
| Leaflet.heat | 0.2.0 | BSD-2-Clause | C | Keep notice | Yes, with conditions | Low | - |

### Developer tool: wa-status (not distributed with the app)

WhatsApp status notifier in `wa-status/`, used only on the owner's machine. Installed with pip, nothing vendored. Licenses verified 2026-11-26 from PyPI metadata and the GitHub license API.

| Component | Version | License | Use | Obligations | Compatible | Risk | Status / action |
|---|---|---|---|---|---|---|---|
| neonize | 0.12.4 | Apache-2.0 (GitHub krypton-byte/neonize) | L (pip) | Notice if ever redistributed | Yes, with conditions | Low (code) | Service terms: see WhatsApp below (D7) |
| whatsmeow (Go core bundled in neonize's DLL) | per neonize 0.12.4 | MPL-2.0 (GitHub tulir/whatsmeow) | L (inside neonize wheel) | If redistributed: say where the MPL source is (upstream, unmodified) | Yes, with conditions | Low | Not redistributed |
| cryptography, phonenumbers, requests | 50.0.2, 9.0.44, 2.34.2 | Apache-2.0 OR BSD-3-Clause; Apache-2.0; Apache-2.0 | L | Notice | Yes, with conditions | Low | - |
| httpx, protobuf, segno | 0.28.1, 7.36.2, 1.6.6 | BSD-3-Clause | L | Notice | Yes, with conditions | Low | - |
| linkpreview, python-magic-bin, pillow | 0.13.3, 0.4.14, 13.0.0 | MIT; MIT; MIT-CMU | L | Notice | Yes, with conditions | Low | - |
| pycryptodome, tqdm | 4.6.0, 4.70.1 | BSD-2-Clause AND Unlicense AND MIT; MPL-2.0 AND MIT | L | Notice | Yes, with conditions | Low | - |

### Web version (retired)

| Component | Version | License | Risk | Status |
|---|---|---|---|---|
| beautifulsoup4, soupsieve | 4.14.3, 2.8.3 | MIT | Low | Not deployed |
| typing_extensions | 4.15.0 | PSF-2.0 | Low | Not deployed |
| upstash-redis | 1.8.0 | UNVERIFIED | Low | Not deployed |

### Data and services

| Service | Terms (verified source) | Required attribution | Compatible | Risk | Status / action |
|---|---|---|---|---|---|
| OpenStreetMap tiles | OSMF Tile Usage Policy: visible attribution, no hiding behind toggles, identifying User-Agent, no bulk/offline use | (c) OpenStreetMap contributors | Yes, with conditions | Medium | Desktop OK; Android attribution now always visible |
| OpenTopoMap | CC-BY-SA, no mass downloads (opentopomap.org/about) | Map data: (c) OpenStreetMap contributors, SRTM; Map style: (c) OpenTopoMap (CC-BY-SA) | Yes, with conditions | Low | Fixed |
| Esri World Imagery | Esri Master License Agreement (ArcGIS item licenseInfo) | Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community | Unknown | Medium | Attribution fixed (D4); account requirement UNVERIFIED |
| CARTO dark basemap | CARTO basemap terms; key required (github.com/CartoDB/basemap-styles) | (c) CARTO, (c) OpenStreetMap contributors | Yes, with conditions | Medium | Attribution fixed; no key yet |
| Open-Meteo | Free API non-commercial only; CC BY 4.0 (open-meteo.com/en/terms, /en/licence) | Weather data by Open-Meteo.com (with link) | Yes, with conditions | Medium | Attribution added (D3) |
| OpenWeather | ODbL, visible attribution required (openweathermap.org/full-price) | Weather data (c) OpenWeather | Yes, with conditions | Low | Attribution added in the weather popup |
| Nominatim | 1 request/s per app, identifying User-Agent, caching required, ODbL | (c) OpenStreetMap contributors | Yes, with conditions | Medium | Identifying UA present; verify caching |
| Google Geocoding API | Google Maps Platform terms; "Google Maps" attribution; lat/lng cache max 30 days | Google Maps | Unknown | Low | Used only by the retired Web search control; "non-Google map" restriction UNVERIFIED |
| FlightRadar24 | ToS 2.3 / 10.3: human or official-API access only, scraping forbidden | - | No | High | Kept by owner decision D2 (accepted risk) |
| WhatsApp (via neonize, wa-status dev tool) | WhatsApp Terms of Service do not allow unofficial/automated clients; risk of account ban | - | No (ToS) | Medium | Kept by owner decision D7 (accepted risk, self-messages only, dev machine only) |
| The OpenSky Network | Terms page unreachable (HTTP 403) | The OpenSky Network | Unknown | Medium | UNVERIFIED |
| Israel Airports Authority NOTAM site | Site terms not verified; scraped with a browser User-Agent to pass the WAF | Israel Airports Authority | Unknown | Medium | UNVERIFIED |
| Israel eAIP AD 2.17 (CTR boundaries), UAS coordination zones | Source terms not verified | - | Unknown | Medium | UNVERIFIED |

### Repository files that are third-party or generated

| File | Origin / license | Note |
|---|---|---|
| qwebchannel.js | The Qt Company / KDAB, LGPL-3.0 OR GPL-2.0 OR GPL-3.0 OR commercial | Unused (0 references); kept by owner decision |
| heatmap.html | Output of the old folium-based weather_tool.py (loads Leaflet, jQuery, Bootstrap, Font Awesome Free from CDNs) | Unused; kept by owner decision |
| map.html, web/public/index.html | Generated by MAP.py | No headers (generated) |
