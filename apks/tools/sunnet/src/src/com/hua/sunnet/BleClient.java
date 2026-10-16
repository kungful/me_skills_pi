package com.hua.sunnet;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * pcbsun BLE 客户端（Android 中央设备侧）。
 *
 * 与固件 src/ble_service.cpp 一一对应：
 *   服务  6f1a0000-6e6f-7270-6261-73756e5f3031
 *   cmd   6f1a0001-…  WRITE / WRITE_NR   内容 = {"cmd":…} JSON
 *   state 6f1a0002-…  READ / NOTIFY      周期 1s 推 state，写完命令也 setValue 响应
 *   cfg   6f1a0003-…  READ / WRITE       {"cmd":"set",…}
 *
 * 请求-响应策略（没有专门的响应特征，所以这么做）：
 *   写 cmd → 记 pending → 谁先到用谁（state 的 notify、或主动 read 回来的值）→ 回给前端。
 */
public class BleClient {

    private static final String TAG = "SunNetBle";
    public static final UUID SVC = UUID.fromString("6f1a0000-6e6f-7270-6261-73756e5f3031");
    public static final UUID CH_CMD = UUID.fromString("6f1a0001-6e6f-7270-6261-73756e5f3031");
    public static final UUID CH_STATE = UUID.fromString("6f1a0002-6e6f-7270-6261-73756e5f3031");
    public static final UUID CH_CFG = UUID.fromString("6f1a0003-6e6f-7270-6261-73756e5f3031");
    private static final UUID CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    public interface Sink {
        void onEvent(String json);          // 连接状态变化，推给前端
        void onLog(String line);
    }

    private final Context ctx;
    private final Handler h = new Handler(Looper.getMainLooper());
    private final Sink sink;

    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private ScanCallback scanCb;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic chCmd, chState, chCfg;

    private boolean connected = false;
    private String deviceName = "";

    private String lastState = null;        // 最近一次 state 通知
    private long lastStateAt = 0;
    private String lastCfg = null;

    private String pendingId = null;        // 等待响应的请求 id（null = 空闲）
    private Runnable pendingTimeout;

    // GATT 操作串行化：BLE 栈同一时刻只允许一个未完成的操作
    private final ArrayDeque<Runnable> q = new ArrayDeque<>();
    private boolean opInFlight = false;

    public BleClient(Context c, Sink s) {
        this.ctx = c;
        this.sink = s;
        BluetoothManager bm = (BluetoothManager) c.getSystemService(Context.BLUETOOTH_SERVICE);
        if (bm != null) adapter = bm.getAdapter();
    }

    // ------------------------------------------------------------------ 权限
    public boolean hasPermission() {
        if (Build.VERSION.SDK_INT >= 31) {
            return granted("android.permission.BLUETOOTH_SCAN")
                && granted("android.permission.BLUETOOTH_CONNECT");
        }
        return granted("android.permission.BLUETOOTH")
            && granted("android.permission.ACCESS_FINE_LOCATION");
    }

    private boolean granted(String p) {
        return ctx.checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED;
    }

    public boolean enabled() { return adapter != null && adapter.isEnabled(); }

    // ------------------------------------------------------------------ 扫描
    public void scan(int ms, final Bridge.ResultCb cb) {
        if (!hasPermission()) { cb.done(false, "缺少蓝牙权限（请在系统弹窗里允许）"); return; }
        if (!enabled()) { cb.done(false, "手机蓝牙未打开"); return; }
        stopScan();
        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) { cb.done(false, "蓝牙扫描器不可用"); return; }

        final Map<String, JSONObject> found = new LinkedHashMap<>();
        scanCb = new ScanCallback() {
            @Override public void onScanResult(int type, ScanResult r) {
                try {
                    BluetoothDevice d = r.getDevice();
                    String name = null;
                    if (d != null) {
                        try { name = d.getName(); } catch (SecurityException ignored) { }
                    }
                    if (name == null || name.isEmpty()) name = r.getScanRecord() != null
                            ? r.getScanRecord().getDeviceName() : null;
                    boolean ours = name != null && name.toLowerCase(Locale.ROOT).contains("pcbsun");
                    JSONObject o = new JSONObject();
                    o.put("id", d != null ? d.getAddress() : "?");
                    o.put("name", name == null ? "(无名)" : name);
                    o.put("rssi", r.getRssi());
                    o.put("ours", ours);
                    found.put(o.optString("id"), o);
                } catch (Exception e) { Log.w(TAG, "scanResult " + e); }
            }
            @Override public void onScanFailed(int err) { Log.w(TAG, "scanFailed " + err); }
        };

        ScanSettings st = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build();
        scanner.startScan(null, st, scanCb);

        h.postDelayed(() -> {
            stopScan();
            JSONArray arr = new JSONArray();
            // 自己的设备排前面
            List<JSONObject> list = new ArrayList<>(found.values());
            list.sort((a, b) -> {
                boolean oa = a.optBoolean("ours"), ob = b.optBoolean("ours");
                if (oa != ob) return oa ? -1 : 1;
                return b.optInt("rssi") - a.optInt("rssi");
            });
            for (JSONObject o : list) arr.put(o);
            cb.done(true, arr.toString());
        }, Math.max(1500, ms));
    }

    private void stopScan() {
        try { if (scanner != null && scanCb != null) scanner.stopScan(scanCb); }
        catch (Exception ignored) { }
        scanCb = null;
    }

    // ------------------------------------------------------------------ 连接
    public void connect(final String address, final Bridge.ResultCb cb) {
        if (!hasPermission()) { cb.done(false, "缺少蓝牙权限"); return; }
        if (!enabled()) { cb.done(false, "手机蓝牙未打开"); return; }
        disconnect();
        try {
            BluetoothDevice d = adapter.getRemoteDevice(address);
            deviceName = "";
            gatt = d.connectGatt(ctx, false, cbGatt, BluetoothDevice.TRANSPORT_LE);
        } catch (Exception e) {
            cb.done(false, "连接失败: " + e.getMessage());
            return;
        }
        h.postDelayed(() -> {
            if (!connected) cb.done(false, "连接超时（设备没上电 / 不在广播）");
        }, 12000);
        // 真连上（服务发现完成）后回调
        this.connectCb = cb;
    }

    private Bridge.ResultCb connectCb;

    private final BluetoothGattCallback cbGatt = new BluetoothGattCallback() {
        @Override public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            if (newState == android.bluetooth.BluetoothProfile.STATE_CONNECTED) {
                Log.i(TAG, "connected, discovering services");
                g.discoverServices();
            } else if (newState == android.bluetooth.BluetoothProfile.STATE_DISCONNECTED) {
                connected = false;
                clearChars();
                opInFlight = false; q.clear();
                fireEvent("disconnected", "连接已断开");
                if (connectCb != null) { connectCb.done(false, "连接断开 (status=" + status + ")"); connectCb = null; }
            }
        }

        @Override public void onServicesDiscovered(BluetoothGatt g, int status) {
            BluetoothGattService svc = g.getService(SVC);
            if (svc == null) {
                if (connectCb != null) { connectCb.done(false, "设备没有 pcbsun 服务（固件没起 BLE？）"); connectCb = null; }
                return;
            }
            chCmd = svc.getCharacteristic(CH_CMD);
            chState = svc.getCharacteristic(CH_STATE);
            chCfg = svc.getCharacteristic(CH_CFG);
            if (chCmd == null || chState == null) {
                if (connectCb != null) { connectCb.done(false, "特征缺失（固件版本不匹配）"); connectCb = null; }
                return;
            }
            connected = true;
            opDone();
            // MTU 185（固件设定）；失败也无所谓
            runOp(() -> { try { g.requestMtu(185); } catch (Exception e) { opDone(); } });
            // 打开 state 的 notify
            runOp(() -> {
                try {
                    g.setCharacteristicNotification(chState, true);
                    BluetoothGattDescriptor dd = chState.getDescriptor(CCCD);
                    if (dd != null) {
                        if (Build.VERSION.SDK_INT >= 33) {
                            g.writeDescriptor(dd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                        } else {
                            dd.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                            g.writeDescriptor(dd);
                        }
                    } else { opDone(); }
                } catch (Exception e) { opDone(); }
            });
            // 读一次 cfg，前端要用
            runOp(() -> {
                try { if (chCfg != null) g.readCharacteristic(chCfg); else opDone(); }
                catch (Exception e) { opDone(); }
            });

            JSONObject info = new JSONObject();
            try {
                info.put("state", "connected");
                info.put("mode", "ble");
                info.put("addr", address());
                info.put("name", deviceName);
            } catch (Exception ignored) { }
            sink.onEvent(info.toString());
            if (connectCb != null) { connectCb.done(true, info.toString()); connectCb = null; }
        }

        @Override public void onMtuChanged(BluetoothGatt g, int mtu, int status) { opDone(); }

        @Override public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor d, int status) { opDone(); }

        @Override public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic c, int status) {
            opDone();
        }

        @Override public void onCharacteristicRead(BluetoothGatt g, BluetoothGattCharacteristic c, int status) {
            opDone();
            String v = valueOf(c);
            if (v == null) return;
            if (c.getUuid().equals(CH_CFG)) { lastCfg = v; return; }
            if (c.getUuid().equals(CH_STATE)) {
                if (isState(v)) { lastState = v; lastStateAt = System.currentTimeMillis(); }
                resolvePending(v);
            }
        }

        @Override public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
            String v = valueOf(c);
            if (v == null || !c.getUuid().equals(CH_STATE)) return;
            if (isState(v)) {
                lastState = v;
                lastStateAt = System.currentTimeMillis();
            }
            resolvePending(v);
        }
    };

    private String address() {
        try { return gatt != null && gatt.getDevice() != null ? gatt.getDevice().getAddress() : ""; }
        catch (SecurityException e) { return ""; }
    }

    @SuppressWarnings("deprecation")
    private String valueOf(BluetoothGattCharacteristic c) {
        try {
            byte[] b = c.getValue();
            return b == null ? null : new String(b, "UTF-8");
        } catch (Exception e) { return null; }
    }

    /** 区分「state 通知」和「命令回包」：state 一定带 pins + motor + ver。 */
    private boolean isState(String s) {
        return s != null && s.contains("\"pins\"") && s.contains("\"motor\"") && s.contains("\"ver\"");
    }

    public void disconnect() {
        connected = false;
        try { if (gatt != null) { gatt.disconnect(); gatt.close(); } } catch (Exception ignored) { }
        gatt = null;
        clearChars();
        opInFlight = false;
        q.clear();
    }

    private void clearChars() { chCmd = chState = chCfg = null; lastState = null; lastCfg = null; }

    public boolean isConnected() { return connected; }
    public void setName(String n) { this.deviceName = n; }

    // ------------------------------------------------------------------ 读写
    /** BLE 上的「HTTP 等价物」：state / cmd / config 三种调用。 */
    public void call(String path, final String body, final Bridge.ResultCb cb) {
        if (!connected || gatt == null) { cb.done(false, "BLE 未连接"); return; }

        if (path.startsWith("/api/state")) {
            long age = System.currentTimeMillis() - lastStateAt;
            if (lastState != null && age < 4000) { cb.done(true, lastState); return; }
            runOp(() -> {
                boolean started = false;
                try { started = gatt.readCharacteristic(chState); }
                catch (Exception e) { started = false; }
                if (!started) { opDone(); cb.done(false, "读取状态失败"); return; }
                h.postDelayed(() -> {
                    if (lastState != null) cb.done(true, lastState);
                    else cb.done(false, "状态读取超时");
                }, 1500);
            });
            return;
        }

        if (path.startsWith("/api/config")) {
            if (lastCfg != null) { cb.done(true, lastCfg); return; }
            runOp(() -> {
                try { if (chCfg == null || !gatt.readCharacteristic(chCfg)) { opDone(); cb.done(false, "配置读取失败"); } }
                catch (Exception e) { opDone(); cb.done(false, "配置读取异常"); }
            });
            return;
        }

        if (path.startsWith("/api/log") || path.startsWith("/api/scan")) {
            cb.done(false, "BLE 通道不支持 " + path + "（用 WiFi 通道，或串口 CLI）");
            return;
        }

        if (path.startsWith("/api/cmd")) {
            writeCmd(body, cb);
            return;
        }
        cb.done(false, "未知路径 " + path);
    }

    private void writeCmd(final String json, final Bridge.ResultCb cb) {
        if (json == null || json.isEmpty()) { cb.done(false, "空命令"); return; }
        if (pendingId != null) { cb.done(false, "上一条命令还没回，稍后再点"); return; }
        final String rid = Long.toHexString(System.nanoTime());
        pendingId = rid;
        pendingCb = cb;
        pendingTimeout = () -> {
            if (rid.equals(pendingId)) {
                pendingId = null;
                cb.done(true, "{\"ok\":true,\"via\":\"ble\",\"note\":\"已发送（未收到回包，以状态为准）\"}");
            }
        };
        h.postDelayed(pendingTimeout, 4000);

        runOp(() -> {
            try {
                if (chCmd == null || gatt == null) { opDone(); finishPending(null, cb); return; }
                boolean ok;
                if (Build.VERSION.SDK_INT >= 33) {
                    ok = gatt.writeCharacteristic(chCmd, json.getBytes("UTF-8"),
                            BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
                            == android.bluetooth.BluetoothStatusCodes.SUCCESS;
                } else {
                    chCmd.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
                    chCmd.setValue(json.getBytes("UTF-8"));
                    ok = gatt.writeCharacteristic(chCmd);
                }
                if (!ok) { opDone(); finishPending(null, cb); }
            } catch (Exception e) {
                opDone();
                finishPending(null, cb);
            }
        });
    }

    /** 收到任何回包（notify / read）就结束等待。 */
    private void resolvePending(String payload) {
        if (pendingId == null) return;
        finishPending(payload, pendingCb);
    }

    private Bridge.ResultCb pendingCb;

    private void finishPending(String payload, Bridge.ResultCb cb0) {
        Bridge.ResultCb cb = cb0 != null ? cb0 : pendingCb;
        pendingId = null;
        pendingCb = null;
        if (pendingTimeout != null) { h.removeCallbacks(pendingTimeout); pendingTimeout = null; }
        if (cb == null) return;
        if (payload == null) cb.done(true, "{\"ok\":true,\"via\":\"ble\"}");
        else cb.done(true, payload);
    }

    // ------------------------------------------------------------------ 串行化
    private void runOp(Runnable r) { q.add(r); pump(); }

    private void pump() {
        if (opInFlight || q.isEmpty()) return;
        opInFlight = true;
        Runnable r = q.poll();
        final Object token = new Object();
        opToken = token;
        h.postDelayed(() -> { if (opToken == token) opDone(); }, 1500);   // 卡死兜底
        try { r.run(); } catch (Exception e) { Log.w(TAG, "op " + e); opDone(); }
    }

    private Object opToken;

    private void opDone() {
        opInFlight = false;
        opToken = null;
        h.postDelayed(this::pump, 40);
    }

    private void fireEvent(String state, String msg) {
        try {
            JSONObject o = new JSONObject();
            o.put("state", state);
            o.put("mode", "ble");
            o.put("name", deviceName);
            o.put("msg", msg);
            sink.onEvent(o.toString());
        } catch (Exception ignored) { }
    }
}
