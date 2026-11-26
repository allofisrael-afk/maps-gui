# Third-Party Notices

This project (Copyright (c) 2024-2026 Israel Alalouf. All rights reserved. See LICENSE) uses the third-party
components listed below. Each component remains under its own license. License texts follow at the end of this file;
the Android app additionally shows every bundled license in-app (About > View licenses).

Generated from primary sources (package metadata, LICENSE files, the Flutter NOTICES bundle and vendor pages) during the
license audit of 2026-11-14. See docs/DEPENDENCIES.md for the audit table, usage and obligations.

> Distribution status: the Android APK is distributed. The Desktop application is currently **not distributed**
> (decision D1 in docs/DEPENDENCIES.md, because PyQt5 is GPL-3.0). The Web version is retired.

## 1. Android application (shipped inside the APK)

### 1.1 Flutter SDK and engine

Flutter framework and engine, Copyright 2014 The Flutter Authors, BSD-3-Clause, https://flutter.dev. The engine bundles
further components (Skia, ICU, HarfBuzz, FreeType, BoringSSL, zlib, libpng, libjpeg-turbo, libwebp, SQLite, Dart VM and
others) under permissive licenses (BSD, MIT, Apache-2.0, ICU, zlib, libpng); the complete texts ship in the APK
(flutter_assets/NOTICES) and are displayed on the in-app licenses page.

### 1.2 Dart packages (runtime dependencies)

| Package | Version | License | Copyright | Source |
|---|---|---|---|---|
| async | 2.13.1 | BSD-3-Clause | Copyright 2015, the Dart project authors. | https://pub.dev/packages/async |
| characters | 1.4.1 | BSD-3-Clause | Copyright 2019, the Dart project authors. | https://pub.dev/packages/characters |
| clock | 1.1.2 | Apache-2.0 | copyright license to reproduce, prepare Derivative Works of, | https://pub.dev/packages/clock |
| collection | 1.19.1 | BSD-3-Clause | Copyright 2015, the Dart project authors. | https://pub.dev/packages/collection |
| crypto | 3.0.8 | BSD-3-Clause | Copyright 2015, the Dart project authors. | https://pub.dev/packages/crypto |
| dart_earcut | 1.2.0 | MIT | Copyright (c) 2025 Luka Stillingfleet (JaffaKetchup) | https://pub.dev/packages/dart_earcut |
| ffi | 2.2.0 | BSD-3-Clause | Copyright 2019, the Dart project authors. | https://pub.dev/packages/ffi |
| file | 7.0.1 | BSD-3-Clause | Copyright 2017, the Dart project authors. All rights reserved. | https://pub.dev/packages/file |
| fixnum | 1.1.1 | BSD-3-Clause | Copyright 2014, the Dart project authors. | https://pub.dev/packages/fixnum |
| flutter_map | 7.0.2 | BSD-3-Clause | Copyright (c) 2018-2024, the 'flutter_map' authors and maintainers | https://pub.dev/packages/flutter_map |
| geolocator | 13.0.4 | MIT | Copyright (c) 2018 Baseflow | https://pub.dev/packages/geolocator |
| geolocator_android | 4.6.2 | MIT | Copyright (c) 2018 Baseflow | https://pub.dev/packages/geolocator_android |
| geolocator_apple | 2.4.3 | MIT | Copyright (c) 2018 Baseflow | https://pub.dev/packages/geolocator_apple |
| geolocator_platform_interface | 4.4.1 | MIT | Copyright (c) 2018 Baseflow | https://pub.dev/packages/geolocator_platform_interface |
| geolocator_web | 4.1.4 | MIT | Copyright (c) 2018 Baseflow | https://pub.dev/packages/geolocator_web |
| geolocator_windows | 0.2.5 | MIT | Copyright (c) 2018 Baseflow | https://pub.dev/packages/geolocator_windows |
| http | 1.6.0 | BSD-3-Clause | Copyright 2014, the Dart project authors. | https://pub.dev/packages/http |
| http_parser | 4.1.2 | BSD-3-Clause | Copyright 2014, the Dart project authors. | https://pub.dev/packages/http_parser |
| intl | 0.20.3 | BSD-3-Clause | Copyright 2013, the Dart project authors. | https://pub.dev/packages/intl |
| latlong2 | 0.9.1 | Apache-2.0 | Copyright 2015 Michael Mitterer (office@mikemitterer.at), | https://pub.dev/packages/latlong2 |
| lists | 1.0.1 | BSD-3-Clause | Copyright (c) 2014, Andrew Mezoni | https://pub.dev/packages/lists |
| logger | 2.8.0 | MIT | Copyright (c) 2019 Simon Leier | https://pub.dev/packages/logger |
| material_color_utilities | 0.13.0 | Apache-2.0 | copyright license to reproduce, prepare Derivative Works of, | https://pub.dev/packages/material_color_utilities |
| material_symbols_icons | 4.2960.0 | Apache-2.0 | copyright license to reproduce, prepare Derivative Works of, | https://pub.dev/packages/material_symbols_icons |
| meta | 1.17.0 | BSD-3-Clause | Copyright 2016, the Dart project authors. | https://pub.dev/packages/meta |
| mgrs_dart | 2.0.0 | MIT | Copyright (c) 2020 Gergely Padányi-Gulyás | https://pub.dev/packages/mgrs_dart |
| nested | 1.0.0 | MIT | Copyright (c) 2019 Remi Rousselet | https://pub.dev/packages/nested |
| path | 1.9.1 | BSD-3-Clause | Copyright 2014, the Dart project authors. | https://pub.dev/packages/path |
| path_provider_linux | 2.2.2 | BSD-3-Clause | Copyright 2013 The Flutter Authors | https://pub.dev/packages/path_provider_linux |
| path_provider_platform_interface | 2.1.3 | BSD-3-Clause | Copyright 2013 The Flutter Authors | https://pub.dev/packages/path_provider_platform_interface |
| path_provider_windows | 2.3.0 | BSD-3-Clause | Copyright 2013 The Flutter Authors. All rights reserved. | https://pub.dev/packages/path_provider_windows |
| platform | 3.1.6 | BSD-3-Clause | Copyright 2017, the Dart project authors. All rights reserved. | https://pub.dev/packages/platform |
| plugin_platform_interface | 2.1.8 | BSD-3-Clause | Copyright 2013 The Flutter Authors. All rights reserved. | https://pub.dev/packages/plugin_platform_interface |
| polylabel | 1.0.1 | BSD-3-Clause | Copyright 2021 André Sousa | https://pub.dev/packages/polylabel |
| proj4dart | 2.1.0 | MIT | Copyright (c) 2020 maRci002, Gergely Padányi-Gulyás (fegyi001) | https://pub.dev/packages/proj4dart |
| provider | 6.1.5+1 | MIT | Copyright (c) 2019 Remi Rousselet | https://pub.dev/packages/provider |
| shared_preferences | 2.5.6 | BSD-3-Clause | Copyright 2013 The Flutter Authors | https://pub.dev/packages/shared_preferences |
| shared_preferences_android | 2.4.23 | BSD-3-Clause | Copyright 2013 The Flutter Authors | https://pub.dev/packages/shared_preferences_android |
| shared_preferences_foundation | 2.5.7 | BSD-3-Clause | Copyright 2013 The Flutter Authors | https://pub.dev/packages/shared_preferences_foundation |
| shared_preferences_linux | 2.4.1 | BSD-3-Clause | Copyright 2013 The Flutter Authors. All rights reserved. | https://pub.dev/packages/shared_preferences_linux |
| shared_preferences_platform_interface | 2.4.2 | BSD-3-Clause | Copyright 2013 The Flutter Authors | https://pub.dev/packages/shared_preferences_platform_interface |
| shared_preferences_web | 2.4.3 | BSD-3-Clause | Copyright 2013 The Flutter Authors. All rights reserved. | https://pub.dev/packages/shared_preferences_web |
| shared_preferences_windows | 2.4.1 | BSD-3-Clause | Copyright 2013 The Flutter Authors. All rights reserved. | https://pub.dev/packages/shared_preferences_windows |
| source_span | 1.10.2 | BSD-3-Clause | Copyright 2014, the Dart project authors. | https://pub.dev/packages/source_span |
| string_scanner | 1.4.1 | BSD-3-Clause | Copyright 2014, the Dart project authors. | https://pub.dev/packages/string_scanner |
| term_glyph | 1.2.2 | BSD-3-Clause | Copyright 2017, the Dart project authors. | https://pub.dev/packages/term_glyph |
| typed_data | 1.4.0 | BSD-3-Clause | Copyright 2015, the Dart project authors. | https://pub.dev/packages/typed_data |
| unicode | 0.3.1 | BSD-3-Clause | Copyright (c) 2014, Andrew Mezoni | https://pub.dev/packages/unicode |
| uuid | 4.6.0 | MIT | Copyright (c) 2021 Yulian Kuncheff | https://pub.dev/packages/uuid |
| vector_math | 2.2.0 | BSD-3-Clause | Copyright 2015, Google Inc. All rights reserved. | https://pub.dev/packages/vector_math |
| web | 1.1.1 | BSD-3-Clause | Copyright 2023, the Dart project authors. | https://pub.dev/packages/web |
| wkt_parser | 2.0.0 | MIT | Copyright (c) 2020 Gergely Padányi-Gulyás | https://pub.dev/packages/wkt_parser |
| xdg_directories | 1.1.0 | BSD-3-Clause | Copyright 2013 The Flutter Authors. All rights reserved. | https://pub.dev/packages/xdg_directories |

### 1.3 Android libraries and runtime

| Component | Version | License | Copyright / Owner | Source |
|---|---|---|---|---|
| CPython (embedded by Chaquopy) | 3.14 | PSF-2.0 | Copyright (c) 2001 Python Software Foundation | https://www.python.org |
| Chaquopy | 17.2.0 | MIT | Copyright (c) 2017-2025 Chaquo Ltd and contributors | https://chaquo.com/chaquopy/ |
| AndroidX libraries (activity, appcompat, core, fragment, lifecycle, window, datastore, ...) | per Gradle resolution | Apache-2.0 | The Android Open Source Project | https://developer.android.com/jetpack/androidx |
| Kotlin standard library | 2.2.x | Apache-2.0 | JetBrains s.r.o. and Kotlin contributors | https://kotlinlang.org |
| ReLinker (com.getkeepsafe.relinker) | 1.4.5 | Apache-2.0 | KeepSafe Software | https://github.com/KeepSafe/ReLinker |
| Google Play services (location, base, basement, tasks) | 21.2.0 / 18.3.0 / 18.3.0 / 18.1.0 | Android Software Development Kit License (proprietary) | Google LLC | https://developer.android.com/studio/terms |

## 2. Desktop application (Python, not currently distributed)

| Package | Version | License | Copyright | Pulled in by | Source |
|---|---|---|---|---|---|
| requests | 2.33.0 | Apache-2.0 | copyright license to reproduce, prepare Derivative Works of, | direct, flightradarapi | https://github.com/psf/requests |
| PyQt5 | 5.15.11 | GPL-3.0-only | (see package license file) | direct, pyqtwebengine | https://www.riverbankcomputing.com/software/pyqt/ |
| PyQtWebEngine | 5.15.7 | GPL-3.0-only | (see package license file) | direct | https://www.riverbankcomputing.com/software/pyqtwebengine/ |
| python-dotenv | 1.2.2 | BSD-3-Clause | Copyright (c) 2014, Saurabh Kumar (python-dotenv), 2013, Ted Tieken (django-dotenv-rw), 2013, Jacob Kaplan-Moss (django-dotenv) | direct | https://github.com/theskumar/python-dotenv |
| Flask | 3.1.3 | BSD-3-Clause | Copyright 2010 Pallets | direct, flask-cors | https://github.com/pallets/flask/ |
| flask-cors | 6.0.2 | MIT | (see package license file) | direct | https://corydolphin.github.io/flask-cors/ |
| FlightRadarAPI | 1.4.0 | MIT | Copyright (c) 2020 Jean Loui Bernard Silva de Jesus | direct | https://github.com/JeanExtreme002/FlightRadarAPI |
| psutil | 7.2.2 | BSD-3-Clause | Copyright (c) 2009, Jay Loden, Dave Daeschler, Giampaolo Rodola | direct | https://github.com/giampaolo/psutil |
| charset-normalizer | 3.4.4 | MIT | Copyright (c) 2025 TAHRI Ahmed R. | requests | https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md |
| idna | 3.11 | BSD-3-Clause | Copyright (c) 2013-2025, Kim Davies and contributors. | requests | https://github.com/kjd/idna/blob/master/HISTORY.rst |
| urllib3 | 2.5.0 | MIT | Copyright (c) 2008-2020 Andrey Petrov and contributors. | requests | https://github.com/urllib3/urllib3/blob/main/CHANGES.rst |
| certifi | 2025.10.5 | MPL-2.0 | (see package license file) | requests | https://github.com/certifi/python-certifi |
| PyQt5_sip | 12.17.1 | BSD-2-Clause | Copyright (c) 2025 Phil Thompson <phil@riverbankcomputing.com> | pyqt5, pyqtwebengine | https://github.com/Python-SIP/sip |
| PyQt5-Qt5 | 5.15.2 | LGPL-3.0-only | Copyright (C) 2007 Free Software Foundation, Inc. <http://fsf.org/> | pyqt5 | https://www.riverbankcomputing.com/software/pyqt/ |
| PyQtWebEngine-Qt5 | 5.15.2 | LGPL-3.0-only | Copyright (C) 2007 Free Software Foundation, Inc. <http://fsf.org/> | pyqtwebengine | https://www.riverbankcomputing.com/software/pyqt/ |
| blinker | 1.9.0 | MIT | Copyright 2010 Jason Kirtland | flask | https://github.com/pallets-eco/blinker/ |
| click | 8.3.3 | BSD-3-Clause | Copyright 2014 Pallets | flask | https://github.com/pallets/click/ |
| itsdangerous | 2.2.0 | BSD-3-Clause | Copyright 2011 Pallets | flask | https://github.com/pallets/itsdangerous/ |
| Jinja2 | 3.1.6 | BSD-3-Clause | Copyright 2007 Pallets | flask | https://github.com/pallets/jinja/ |
| MarkupSafe | 3.0.3 | BSD-3-Clause | Copyright 2010 Pallets | flask, jinja2, werkzeug | https://github.com/pallets/markupsafe/ |
| Werkzeug | 3.1.8 | BSD-3-Clause | Copyright 2007 Pallets | flask, flask-cors | https://github.com/pallets/werkzeug/ |
| brotli | 1.2.0 | MIT | Copyright (c) 2009, 2010, 2013-2016 by the Brotli Authors. | flightradarapi | https://github.com/google/brotli |
| colorama | 0.4.6 | BSD-3-Clause | Copyright (c) 2010 Jonathan Hartley | click | https://github.com/tartley/colorama |
| curl_cffi | 0.16.1 | MIT | (see package license file) | direct (optional, lazily imported) | https://github.com/lexiforest/curl_cffi |

PyQt5 and PyQtWebEngine are licensed by Riverbank Computing under GPL-3.0 (or a commercial license); the Qt 5 libraries
they bundle (PyQt5-Qt5, PyQtWebEngine-Qt5) are LGPL-3.0, and Qt WebEngine includes Chromium components under their own
licenses. These terms are the reason the Desktop application is not distributed (see docs/DEPENDENCIES.md, D1).

## 3. Web version (retired, code kept in the repository)

| Package | Version | License | Source |
|---|---|---|---|
| beautifulsoup4 | 4.14.3 | MIT | https://www.crummy.com/software/BeautifulSoup/bs4/ |
| soupsieve | 2.8.3 | MIT | https://github.com/facelessuser/soupsieve |
| typing_extensions | 4.15.0 | PSF-2.0 | https://github.com/python/typing_extensions/issues |
| upstash-redis | 1.8.0 | UNVERIFIED (not installed locally) | https://pypi.org/project/upstash-redis/ |

## 4. Browser libraries loaded by the Desktop map (from unpkg.com CDN, not bundled)

| Library | Version | License | Copyright | Source |
|---|---|---|---|---|
| Leaflet | 1.9.4 | BSD-2-Clause | Copyright (c) 2010-2023, Volodymyr Agafonkin; Copyright (c) 2010-2011, CloudMade | https://leafletjs.com |
| Leaflet.heat | 0.2.0 | BSD-2-Clause | Copyright (c) 2014, Vladimir Agafonkin | https://github.com/Leaflet/Leaflet.heat |

## 5. Data, map tiles and online services

| Service | Used by | Terms / license | Required attribution (shown in the UI) |
|---|---|---|---|
| OpenStreetMap tiles | Desktop, Android | OSMF Tile Usage Policy; data ODbL | (c) OpenStreetMap contributors |
| OpenTopoMap tiles | Desktop | CC-BY-SA | Map data: (c) OpenStreetMap contributors, SRTM; Map style: (c) OpenTopoMap (CC-BY-SA) |
| Esri World Imagery | Desktop, Android | Esri Master License Agreement | Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community |
| CARTO dark basemap | Android | CARTO basemap terms | (c) CARTO, (c) OpenStreetMap contributors |
| Open-Meteo (elevation, weather) | Desktop, Android, ballistics | Free API for non-commercial use; data CC BY 4.0 | Weather data by Open-Meteo.com |
| OpenWeather (current weather) | Desktop | ODbL | Weather data (c) OpenWeather |
| Nominatim (geocoding) | Desktop, Android | OSMF Nominatim Usage Policy; data ODbL | (c) OpenStreetMap contributors |
| Google Geocoding API | Retired Web search control only | Google Maps Platform Terms | Google Maps (not displayed: no live UI uses it) |
| FlightRadar24 | Desktop, Android | FlightRadar24 Terms and Conditions (see docs/DEPENDENCIES.md, D2) | n/a |
| The OpenSky Network | Android (fallback) | OpenSky terms of use (UNVERIFIED) | The OpenSky Network |
| Israel Airports Authority NOTAM site (brin.iaa.gov.il) | Desktop, Android | Site terms UNVERIFIED | Israel Airports Authority |
| Israel eAIP, AD 2.17 (airport CTR boundaries) | Desktop, Android (static data) | UNVERIFIED | Israel eAIP |
| Recommendation ITU-R P.838-3 (rain specific-attenuation model; coefficients from Tables 1-4) | Desktop radar-tracking tool (`radar_track.py`) | (c) ITU; free download; used under owner decision D8 (docs/DEPENDENCIES.md) | Rain attenuation model: Recommendation ITU-R P.838-3 (ITU) |

## 6. Fonts

The Android launcher icon text was rendered from Noto Sans Hebrew (Copyright 2022 The Noto Project Authors), licensed
under the SIL Open Font License 1.1. Only the rasterized image is shipped; the font file is not distributed.

## 7. License texts

### Apache License 2.0

```text
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

### MIT License (template; each component's copyright line is listed above)

```text
MIT License

Copyright (c) 2019 Remi Rousselet

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### BSD 3-Clause License (template; each component's copyright line is listed above)

```text
Copyright 2014, the Dart project authors. 

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following
      disclaimer in the documentation and/or other materials provided
      with the distribution.
    * Neither the name of Google LLC nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Python Software Foundation License 2.0

```text
PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
--------------------------------------------

1. This LICENSE AGREEMENT is between the Python Software Foundation
("PSF"), and the Individual or Organization ("Licensee") accessing and
otherwise using this software ("Python") in source or binary form and
its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works,
distribute, and otherwise use Python alone or in any derivative version,
provided, however, that PSF's License Agreement and PSF's notice of copyright,
i.e., "Copyright (c) 2001 Python Software Foundation; All Rights Reserved"
are retained in Python alone or in any derivative version prepared by Licensee.

3. In the event Licensee prepares a derivative work that is based on
or incorporates Python or any part thereof, and wants to make
the derivative work available to others as provided herein, then
Licensee hereby agrees to include in any such work a brief summary of
the changes made to Python.

4. PSF is making Python available to Licensee on an "AS IS"
basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

6. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

7. Nothing in this License Agreement shall be deemed to create any
relationship of agency, partnership, or joint venture between PSF and
Licensee.  This License Agreement does not grant permission to use PSF
trademarks or trade name in a trademark sense to endorse or promote
products or services of Licensee, or any third party.

8. By copying, installing or otherwise using Python, Licensee
agrees to be bound by the terms and conditions of this License
Agreement.
```

### Other licenses referenced above

- BSD 2-Clause: https://opensource.org/license/bsd-2-clause
- Mozilla Public License 2.0 (certifi, unmodified; source: https://github.com/certifi/python-certifi): https://www.mozilla.org/MPL/2.0/
- GNU GPL 3.0 (PyQt5, PyQtWebEngine): https://www.gnu.org/licenses/gpl-3.0.html
- GNU LGPL 3.0 (Qt 5 libraries): https://www.gnu.org/licenses/lgpl-3.0.html
- SIL Open Font License 1.1: https://openfontlicense.org
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/  |  CC BY-SA 3.0: https://creativecommons.org/licenses/by-sa/3.0/
- ODbL 1.0: https://opendatacommons.org/licenses/odbl/1-0/
