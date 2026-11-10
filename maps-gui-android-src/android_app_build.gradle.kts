plugins {
    id("com.android.application")
    id("kotlin-android")
    // כלי מסלול בליסטי (MPM), Stage 3 (FR-D-237) — ר' android_settings.gradle.kts להסבר הגרסה
    id("com.chaquo.python")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.mapsapp.maps_gui_android"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.mapsapp.maps_gui_android"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // Chaquopy (כלי המסלול הבליסטי, FR-D-237) דורש minSdk>=24 — flutter.minSdkVersion
        // עשוי להיות נמוך יותר, אז נלקח הגבוה משני הערכים ולא נקבע ערך קשיח שיתעלם משינוי-גרסת-Flutter עתידי
        minSdk = maxOf(flutter.minSdkVersion, 24)
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        ndk {
            // Chaquopy תומך רק ב-ABIs האלה (64-ביט) ל-Python 3.12+; מצמצם גם את גודל ה-APK
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

// כלי מסלול בליסטי (MPM) — Stage 3 (FR-D-237). מריץ את mpm_api.py/mpm/ המקוריים (stdlib-בלבד,
// ר' MAPS-GUI_SRS.md FR-D-230) ללא שום שינוי — לפי החלטה א בשלב 1 (Chaquopy, לא port ל-Dart).
chaquopy {
    defaultConfig {
        version = "3.14"  // תואם ל-.venv/Scripts/python.exe (3.14.6) של הפרויקט — טווח נתמך: 3.10-3.15
        // מצביע ל-Python המקומי (לא מחפש ב-PATH) — ר' build_apk.ps1 Step 7b ליצירת android_python/
        buildPython(System.getenv("MPM_BUILD_PYTHON") ?: "D:/PY-IS/maps-gui/.venv/Scripts/python.exe")
    }
    sourceSets {
        getByName("main") {
            // android_python/ — תיקיית-גישור מבודדת (junction ל-mpm/+data/, hardlink ל-mpm_api.py),
            // לא עותקים — נוצרת אוטומטית ע"י build_apk.ps1 Step 7b. לא פונים לשורש-הפרויקט ישירות
            // כי זה היה סורק גם את .venv/ (עשרות-אלפי קבצים) — ר' MAPS-GUI_SRS.md §3.27 FR-D-237
            srcDir("../../../android_python")
        }
    }
}

flutter {
    source = "../.."
}
