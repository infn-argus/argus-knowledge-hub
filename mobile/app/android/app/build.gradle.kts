import java.util.Base64

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

/** A --dart-define value, which Flutter hands Gradle base64-encoded in the dart-defines property. */
fun dartDefine(name: String): String? =
    (project.findProperty("dart-defines") as String?)
        ?.split(',')
        ?.map { String(Base64.getDecoder().decode(it)) }
        ?.firstOrNull { it.startsWith("$name=") }
        ?.substringAfter('=')

android {
    namespace = "it.infn.argus.argus_field"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "it.infn.argus.field"
        // flutter_secure_storage and mobile_scanner need Android 7 or later.
        minSdk = maxOf(flutter.minSdkVersion, 24)
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // The OIDC redirect's scheme follows --dart-define=OIDC_REDIRECT (it.infn.argus.field:/oauthredirect
        // for Keycloak, com.googleusercontent.apps.<id>:/oauthredirect for Google), and the host of
        // universal links and QR labels (ARGUS_LINK_HOST), per build: -PargusLinkHost=argus.example.org
        manifestPlaceholders["appAuthRedirectScheme"] =
            dartDefine("OIDC_REDIRECT")?.substringBefore(':') ?: "it.infn.argus.field"
        manifestPlaceholders["argusLinkHost"] =
            (project.findProperty("argusLinkHost") as String?) ?: "argus.invalid"
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
