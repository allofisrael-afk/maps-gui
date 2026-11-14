// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
package com.mapsapp.maps_gui_android

import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

// כלי מסלול בליסטי (MPM) — Stage 3 (FR-D-237). MethodChannel יחיד בין Dart (lib/services/
// mpm_bridge.dart) ל-mpm_api.py (שורש-הפרויקט, דרך android_python/, ר' build_apk.ps1).
// שם-הערוץ ושם-הפעולה חייבים להיות זהים למה ש-mpm_bridge.dart קורא להם.
class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.mapsapp.maps_gui_android/mpm"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            if (call.method != "dispatch") {
                result.notImplemented()
                return@setMethodCallHandler
            }
            val action = call.argument<String>("action")
            val paramsJson = call.argument<String>("paramsJson")
            if (action == null || paramsJson == null) {
                result.error("BAD_ARGS", "action/paramsJson חסרים", null)
                return@setMethodCallHandler
            }
            try {
                // Python.start נדרש פעם אחת בחיי-התהליך — isStarted בודק כדי לא להפעיל פעמיים
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(applicationContext))
                }
                val py = Python.getInstance()
                val mpmApi: PyObject = py.getModule("mpm_api")
                // dispatch_json(action, params_json) -> JSON string — ר' mpm_api.py, אותה חתימה
                // בדיוק כמו ה-routes ב-weather_server.py/web/api/ballistics.py, בלי Flask
                val resultJson: String = mpmApi.callAttr("dispatch_json", action, paramsJson).toString()
                result.success(resultJson)
            } catch (e: Exception) {
                // חריגת-Python (PyException) או כל שגיאה אחרת — חוזרת כ-JSON-שגיאה כדי ש-Dart
                // יוכל להציג הודעה ברורה, לא לקרוס. לא "תופס-כלום" (bare catch) — Exception
                // מכוון בכוונה, כי Chaquopy עטף את כל שגיאות-Python כ-RuntimeException/תת-מחלקותיו.
                result.success("{\"ok\": false, \"error\": \"Chaquopy bridge error: " +
                    (e.message ?: "unknown").replace("\"", "'") + "\"}")
            }
        }
    }
}
