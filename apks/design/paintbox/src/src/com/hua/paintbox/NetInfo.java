package com.hua.paintbox;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Collections;
import java.util.List;

/** 找本机局域网 IPv4（MCP 开到局域网时显示用）。 */
public final class NetInfo {

    private NetInfo() {
    }

    public static String lanIpv4() {
        try {
            List<NetworkInterface> nics = Collections.list(NetworkInterface.getNetworkInterfaces());
            String fallback = null;
            for (NetworkInterface nic : nics) {
                if (!nic.isUp() || nic.isLoopback()) continue;
                String name = nic.getName() == null ? "" : nic.getName();
                for (InetAddress a : Collections.list(nic.getInetAddresses())) {
                    if (!(a instanceof Inet4Address) || a.isLoopbackAddress()) continue;
                    String ip = a.getHostAddress();
                    if (ip == null) continue;
                    if (name.startsWith("wlan") || name.startsWith("ap") || ip.startsWith("192.168.")
                            || ip.startsWith("10.") || is172Private(ip)) {
                        if (name.startsWith("wlan") || name.startsWith("ap")) return ip;
                        if (fallback == null) fallback = ip;
                    }
                }
            }
            return fallback;
        } catch (Throwable t) {
            return null;
        }
    }

    private static boolean is172Private(String ip) {
        if (!ip.startsWith("172.")) return false;
        int dot = ip.indexOf('.', 4);
        if (dot < 0) return false;
        try {
            int second = Integer.parseInt(ip.substring(4, dot));
            return second >= 16 && second <= 31;
        } catch (Throwable t) {
            return false;
        }
    }
}
