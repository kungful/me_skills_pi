package com.hua.subhunter;

import java.net.InetSocketAddress;
import java.net.Socket;

/** 节点存活探测：对 server:port 做 TCP 握手，得到毫秒延迟。 */
final class Health {

    private Health() {
    }

    /** @return 延迟毫秒，-1 表示不通。 */
    static int ping(String host, int port, int timeoutMs) {
        if (Util.isBlank(host) || port <= 0 || port > 65535) return -1;
        long t0 = System.currentTimeMillis();
        Socket s = new Socket();
        try {
            s.setTcpNoDelay(true);
            s.connect(new InetSocketAddress(host, port), Math.max(600, timeoutMs));
            long ms = System.currentTimeMillis() - t0;
            return (int) Math.max(1, ms);
        } catch (Throwable t) {
            return -1;
        } finally {
            try {
                s.close();
            } catch (Throwable ignore) {
            }
        }
    }
}
