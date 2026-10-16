import socket, struct, time, sys

MDNS = "224.0.0.251"
PORT = 5353

def enc_name(name):
    out = b""
    for part in name.split("."):
        if part:
            out += bytes([len(part)]) + part.encode()
    return out + b"\x00"

def build_query(qname, qtype=12):  # PTR
    tid = 0
    flags = 0
    msg = struct.pack(">HHHHHH", tid, flags, 1, 0, 0, 0)
    msg += enc_name(qname) + struct.pack(">HH", qtype, 1)  # IN, no cache-flush for questions
    return msg

def read_name(data, off):
    labels = []
    jumped = False
    start = off
    while True:
        if off >= len(data):
            break
        l = data[off]
        if l == 0:
            off += 1
            break
        if l & 0xC0 == 0xC0:
            ptr = struct.unpack(">H", data[off:off+2])[0] & 0x3FFF
            if not jumped:
                start = off + 2
            jumped = True
            off = ptr
            continue
        labels.append(data[off+1:off+1+l].decode("utf-8", "replace"))
        off += 1 + l
    if jumped:
        off = start
    return ".".join(labels), off

def parse(data):
    try:
        _, _, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    except Exception:
        return []
    off = 12
    for _ in range(qd):
        _, off = read_name(data, off)
        off += 4
    out = []
    total = an + ns + ar
    for _ in range(total):
        name, off = read_name(data, off)
        if off + 10 > len(data):
            break
        rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[off:off+10])
        off += 10
        rdata_off = off
        rdata = data[off:off+rdlen]
        off += rdlen
        rec = {"name": name, "type": rtype, "ttl": ttl}
        if rtype == 12:  # PTR
            rec["target"], _ = read_name(data, rdata_off)
        elif rtype == 33:  # SRV
            if rdlen >= 6:
                prio, weight, port = struct.unpack(">HHH", rdata[:6])
                tgt, _ = read_name(data, rdata_off + 6)
                rec["port"] = port
                rec["target"] = tgt
        elif rtype == 1:  # A
            if rdlen == 4:
                rec["ip"] = ".".join(str(b) for b in rdata)
        elif rtype == 16:  # TXT
            rec["txt"] = rdata.decode("utf-8", "replace")
        out.append(rec)
    return out

def query(names, wait=3.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except Exception:
        pass
    s.bind(("", 0))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
    s.settimeout(0.4)
    for n in names:
        msg = build_query(n)
        for _ in range(3):
            try:
                s.sendto(msg, (MDNS, PORT))
            except Exception as e:
                print("send fail", e)
            time.sleep(0.05)
    end = time.time() + wait
    recs = []
    while time.time() < end:
        try:
            data, addr = s.recvfrom(9000)
        except socket.timeout:
            continue
        except Exception:
            break
        for r in parse(data):
            r["from"] = addr[0]
            recs.append(r)
    s.close()
    return recs

if __name__ == "__main__":
    names = [
        "_adb-tls-connect._tcp.local",
        "_adb-tls-pairing._tcp.local",
        "_adb._tcp.local",
    ]
    recs = query(names)
    print("=== PTR ===")
    for r in recs:
        if r["type"] == 12:
            print("  %-45s -> %s  (from %s)" % (r["name"], r.get("target"), r["from"]))
    print("=== SRV ===")
    for r in recs:
        if r["type"] == 33:
            print("  %-45s -> %s:%s" % (r["name"], r.get("target"), r.get("port")))
    print("=== A ===")
    for r in recs:
        if r["type"] == 1:
            print("  %-45s -> %s" % (r["name"], r.get("ip")))
    print("total records:", len(recs))
