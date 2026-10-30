package com.hua.subhunter;

/** 进程内共享的运行态（Activity 与 Service 都要看同一个 LocalServer）。 */
final class Hub {

    static volatile LocalServer SERVER;
    static volatile boolean fetching = false;
    static volatile String lastLog = "";

    private Hub() {
    }

    static boolean serverRunning() {
        LocalServer s = SERVER;
        return s != null && s.isRunning();
    }

    static int serverPort(int fallback) {
        LocalServer s = SERVER;
        return s != null ? s.port() : fallback;
    }

    static void log(String msg) {
        lastLog = msg;
    }
}
