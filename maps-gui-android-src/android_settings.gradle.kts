pluginManagement {
    val flutterSdkPath =
        run {
            val properties = java.util.Properties()
            file("local.properties").inputStream().use { properties.load(it) }
            val flutterSdkPath = properties.getProperty("flutter.sdk")
            require(flutterSdkPath != null) { "flutter.sdk not set in local.properties" }
            flutterSdkPath
        }

    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "8.11.1" apply false
    id("org.jetbrains.kotlin.android") version "2.2.20" apply false
    // כלי מסלול בליסטי (MPM), Stage 3 (FR-D-237) — מריץ את mpm_api.py המקורי ללא שינוי בתוך
    // ה-APK (החלטה א בשלב 1). גרסה אומתה מול chaquo.com/chaquopy/doc/current/versions.html:
    // 17.2 תומך ב-AGP 7.3-9.5, כולל ה-8.11.1 של הפרויקט הזה.
    id("com.chaquo.python") version "17.2.0" apply false
}

include(":app")
