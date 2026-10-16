plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "io.pilink"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.pilink"
        minSdk = 26
        targetSdk = 34
        versionCode = 21
        versionName = "0.7.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    // 依赖只要两个：OkHttp（WebSocket + 轮询）+ 协程。
    // 故意不用 androidx.appcompat —— UI 用代码搭，少一个依赖少一处构建风险。
    // 也故意不依赖任何推送服务（FCM 在本机实测被墙，中国的 OEM 通道要注册开发者账号）。
    packaging {
        resources.excludes += setOf("META-INF/*.kotlin_module", "DebugProbesKt.bin")
    }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
