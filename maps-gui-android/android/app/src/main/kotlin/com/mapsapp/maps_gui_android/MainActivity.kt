// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
package com.mapsapp.maps_gui_android

import android.app.Activity
import android.content.Intent
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

    // ── ערוץ קבצים (כלי בדיקת מעקב המכ"ם, שלב ג', FR-D-283): שמירה/פתיחה של קובץ טקסט דרך חלון הקבצים
    // המובנה של אנדרואיד (Storage Access Framework) — בלי ספריית צד-שלישי ובלי הרשאות אחסון. ייצוא CSV,
    // פרופילי מכ"ם (JSON) וטעינת מסלול מ-CSV. בקשה אחת בכל פעם; התוצאה חוזרת ב-onActivityResult. ──
    private val FILES_CHANNEL = "com.mapsapp.maps_gui_android/files"  // חייב להיות זהה ל-file_bridge.dart
    private val REQ_SAVE = 7101  // קוד בקשה לשמירה
    private val REQ_OPEN = 7102  // קוד בקשה לפתיחה
    private var pendingResult: MethodChannel.Result? = null  // התשובה שממתינה לחלון הקבצים
    private var pendingText: String? = null  // הטקסט שממתין לשמירה

    @Suppress("DEPRECATION")  // onActivityResult — ה-API שזמין ל-FlutterActivity בלי תלות ב-AndroidX Activity Result
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val res = pendingResult ?: return  // לא שלנו
        pendingResult = null  // הבקשה הסתיימה
        val uri = data?.data  // הקובץ שנבחר
        if (resultCode != Activity.RESULT_OK || uri == null) {  // המשתמש ביטל
            pendingText = null
            res.success(null)  // null = בוטל
            return
        }
        try {
            if (requestCode == REQ_SAVE) {  // שמירה
                contentResolver.openOutputStream(uri)?.use { it.write((pendingText ?: "").toByteArray(Charsets.UTF_8)) }  // כתיבה
                pendingText = null
                res.success(true)  // נשמר
            } else if (requestCode == REQ_OPEN) {  // פתיחה
                val text = contentResolver.openInputStream(uri)?.use { it.readBytes().toString(Charsets.UTF_8) }  // קריאה
                res.success(text)  // התוכן
            } else {
                res.success(null)
            }
        } catch (e: Exception) {  // כשל קריאה/כתיבה — חוזר כשגיאה ברורה ל-Dart
            res.error("FILE_IO", e.message ?: "file error", null)
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, FILES_CHANNEL).setMethodCallHandler { call, result ->
            if (pendingResult != null) {  // כבר פתוח חלון קבצים
                result.error("BUSY", "file dialog already open", null)
                return@setMethodCallHandler
            }
            when (call.method) {
                "saveText" -> {  // שמירה: שם מוצע, סוג MIME, והטקסט
                    pendingText = call.argument<String>("text") ?: ""
                    pendingResult = result
                    val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE)
                        type = call.argument<String>("mime") ?: "text/plain"
                        putExtra(Intent.EXTRA_TITLE, call.argument<String>("fileName") ?: "export.txt")
                    }
                    @Suppress("DEPRECATION") startActivityForResult(intent, REQ_SAVE)
                }
                "openText" -> {  // פתיחה: כל קובץ טקסט (CSV/JSON)
                    pendingResult = result
                    val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE)
                        type = "*/*"  // ספקי קבצים מסמנים CSV/JSON בסוגים שונים — מסננים לפי התוכן ב-Dart
                    }
                    @Suppress("DEPRECATION") startActivityForResult(intent, REQ_OPEN)
                }
                else -> result.notImplemented()
            }
        }
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
