import json
import statistics
import time
from collections import deque

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
SUB_TOPIC = "edge/bin1/telemetry"
PUB_TOPIC = "fog/bin1/summary"

WINDOW = 10          # window fill level per device
LAT_WINDOW = 300     # jumlah sampel latensi yang disimpan per device
STALE_SEC = 15       # device yang diam selama ini dianggap sudah hilang
LAT_LIMIT_MS = 5.0   # batas latensi keputusan kritis

buffers = {}     # device_id -> list data (fill level)
lat_buf = {}     # device_id -> deque latensi (ms)
last_seen = {}   # device_id -> waktu terakhir kirim


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[FOG] Connected to broker (rc={reason_code})", flush=True)
    client.subscribe(SUB_TOPIC)


def latency_summary(data):
    vals = sorted(v for d in lat_buf.values() for v in d)
    if not vals:
        return None
    n = len(vals)
    return {
        "count": n,
        "mean_ms": round(statistics.mean(vals), 4),
        "p95_ms": round(vals[min(n - 1, int(0.95 * n))], 4),
        "max_ms": round(vals[-1], 4),
        "under_limit_pct": round(100 * sum(1 for v in vals if v < LAT_LIMIT_MS) / n, 2),
        "limit_ms": LAT_LIMIT_MS,
        "last_ms": data.get("decision_latency_ms"),
        "sense_us": data.get("sense_us"),
        "think_us": data.get("think_us"),
        "act_us": data.get("act_us"),
    }


def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    dev = data.get("device_id", "unknown")
    now = time.time()

    buf = buffers.setdefault(dev, [])
    buf.append(data)
    if len(buf) > WINDOW:
        buf.pop(0)
    last_seen[dev] = now

    lat = data.get("decision_latency_ms")
    if lat is not None:
        lat_buf.setdefault(dev, deque(maxlen=LAT_WINDOW)).append(float(lat))

    # buang Pod lama yang sudah mati (misal setelah self-healing)
    for d in [d for d, t in last_seen.items() if now - t > STALE_SEC]:
        buffers.pop(d, None)
        lat_buf.pop(d, None)
        last_seen.pop(d, None)

    all_items = [x for b in buffers.values() for x in b]
    per_device_avg = {
        d: round(statistics.mean(x["fill_level_pct"] for x in b), 1)
        for d, b in buffers.items()
    }

    summary = {
        "device_id": f"{len(buffers)} device(s)",
        "avg_fill_pct": round(statistics.mean(per_device_avg.values()), 1),
        "max_fill_pct": round(max(x["fill_level_pct"] for x in all_items), 1),
        "full_count_in_window": sum(1 for x in all_items if x["is_full"]),
        "window_size": len(all_items),
        "latest_network_status": data.get("network_status"),
        "per_device_avg": per_device_avg,
        "latency": latency_summary(data),
    }

    client.publish(PUB_TOPIC, json.dumps(summary))
    print(f"[FOG-AGGREGATED] {summary}", flush=True)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fog-aggregator")
client.on_connect = on_connect
client.on_message = on_message

print(f"Connecting to {BROKER}:{PORT}...", flush=True)
client.connect(BROKER, PORT, 60)
client.loop_forever()