import java.io.FileInputStream
import java.util.Base64
import java.util.Properties

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

/**
 * The upload key that signs release builds (Google Play re-signs them with the app signing key).
 * From the environment in CI (ANDROID_KEYSTORE_PATH, ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS,
 * ANDROID_KEY_PASSWORD), or from android/key.properties (storeFile, storePassword, keyAlias,
 * keyPassword; never committed) on a developer's machine. Without either, a release build is signed
 * with the debug key, so `flutter run --release` still works, but it cannot be published.
 */
val uploadKey: Map<String, String>? = run {
    val env = System.getenv()
    if (!env["ANDROID_KEYSTORE_PATH"].isNullOrBlank()) {
        return@run mapOf(
            "storeFile" to env.getValue("ANDROID_KEYSTORE_PATH"),
            "storePassword" to env["ANDROID_KEYSTORE_PASSWORD"].orEmpty(),
            "keyAlias" to env["ANDROID_KEY_ALIAS"].orEmpty(),
            "keyPassword" to env["ANDROID_KEY_PASSWORD"].orEmpty(),
        )
    }
    val file = rootProject.file("key.properties")
    if (!file.exists()) return@run null
    val p = Properties().apply { FileInputStream(file).use { load(it) } }
    p.stringPropertyNames().associateWith { p.getProperty(it) }
}

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
        // universal links and QR labels follows --dart-define=ARGUS_LINK_HOST (or -PargusLinkHost=…).
        manifestPlaceholders["appAuthRedirectScheme"] =
            dartDefine("OIDC_REDIRECT")?.substringBefore(':') ?: "it.infn.argus.field"
        manifestPlaceholders["argusLinkHost"] =
            dartDefine("ARGUS_LINK_HOST") ?: (project.findProperty("argusLinkHost") as String?) ?: "argus.invalid"
    }

    signingConfigs {
        uploadKey?.let { k ->
            create("upload") {
                storeFile = rootProject.file(k.getValue("storeFile"))
                storePassword = k["storePassword"]
                keyAlias = k["keyAlias"]
                keyPassword = k["keyPassword"]
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.findByName("upload") ?: signingConfigs.getByName("debug")
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
