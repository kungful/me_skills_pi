plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.vocabtype.app"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.vocabtype.app"
        minSdk = 24
        targetSdk = 37
        versionCode = 8
        versionName = "1.6"
    }

    signingConfigs {
        create("rel") {
            storeFile = rootProject.file("vocabtype.jks")
            storePassword = "vocabtype123"
            keyAlias = "vocabtype"
            keyPassword = "vocabtype123"
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
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.constraintlayout)
    implementation(libs.androidx.recyclerview)
    implementation(libs.okhttp)
}
