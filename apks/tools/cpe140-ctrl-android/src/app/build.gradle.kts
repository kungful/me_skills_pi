plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.picpe.cpe140"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.picpe.cpe140"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        create("rel") {
            storeFile = rootProject.file("cpe140.jks")
            storePassword = "cpe140123"
            keyAlias = "cpe140"
            keyPassword = "cpe140123"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("rel")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

dependencies {
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
}
