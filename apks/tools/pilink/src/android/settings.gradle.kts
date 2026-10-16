// Pi 通知（pilink）—— 安卓客户端
//
// 为什么走阿里云镜像打头：国内网络直连 maven.google.com 常常很慢或超时，
// 镜像放前面是为了快，真源（google()/mavenCentral()）留在后面兜底。
// 海外网络可以把 maven.aliyun.com 两行删掉。
pluginManagement {
    repositories {
        maven("https://maven.aliyun.com/repository/gradle-plugin")
        maven("https://maven.aliyun.com/repository/google")
        maven("https://maven.aliyun.com/repository/public")
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven("https://maven.aliyun.com/repository/google")
        maven("https://maven.aliyun.com/repository/public")
        google()
        mavenCentral()
    }
}

rootProject.name = "pilink"
include(":app")
