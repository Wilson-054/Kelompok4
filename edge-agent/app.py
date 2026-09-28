import json
import os
import random
import socket
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv("MQTT_BROKER", "10.255.136.89")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "edge/bin1/telemetry")
PUBLISH_INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "2"))
DEVICE_ID = os.getenv("DEVICE_ID", socket.gethostname())

BIN_HEIGHT_CM = float(os.getenv("BIN_HEIGHT_CM", "60"))
FULL_THRESHOLD_PCT = float(os.getenv("FULL_THRESHOLD_PCT", "80"))

is_connected = False
fill_state = random.uniform(5, 30)   # % awal simulasi, berbeda tiap Pod
actuator_state = False


def on_connect(client, userdata, flags, reason_code, properties=None):
    global is_connected
    is_connected = (reason_code == 0)
    if is_connected:
        print(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}", flush=True)
    else:
        print(f"MQTT connection failed: {reason_code}", flush=True)


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    global is_connected
    is_connected = False
    print(f"Disconnected from broker (reason={reason_code}) -> failover, tetap jalan lokal", flush=True)


def read_distance_cm():
    """Simulasi sensor: level naik bertahap, reset saat penuh (tong diangkut)."""
    global fill_state
    fill_state += random.uniform(0.5, 3.0)
    if fill_state >= 100:
        print("[EVENT] Sampah diangkut, level direset", flush=True)
        fill_state = random.uniform(2, 10)
    return round(BIN_HEIGHT_CM * (1 - fill_state / 100), 2)


def distance_to_fill_pct(distance_cm):
    pct = (1 - distance_cm / BIN_HEIGHT_CM) * 100
    return round(max(0, min(100, pct)), 1)


def actuate(is_full: bool):
    """Keluarkan perintah aktuator (simulasi).
    Saat hardware boleh dipakai, ganti isinya dengan GPIO.output(BUZZER_PIN, is_full)."""
    global actuator_state
    actuator_state = is_full


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE_ID}-sensor")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...", flush=True)
    client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=5)
    client.loop_start()

    try:
        while True:
            t0 = time.perf_counter_ns()
            distance_cm = read_distance_cm()                       # SENSE
            t1 = time.perf_counter_ns()
            fill_pct = distance_to_fill_pct(distance_cm)
            is_full = fill_pct >= FULL_THRESHOLD_PCT               # THINK
            t2 = time.perf_counter_ns()
            actuate(is_full)                                       # ACT
            t3 = time.perf_counter_ns()

            # logging di luar bagian yang diukur
            print(f"[ACTUATOR-SIM] {'BUZZER ON - PENUH' if actuator_state else 'normal'}", flush=True)

            payload = {
                "device_id": DEVICE_ID,
                "sensor": "HC-SR04",
                "distance_cm": distance_cm,
                "fill_level_pct": fill_pct,
                "is_full": is_full,
                "sense_us": round((t1 - t0) / 1000, 1),
                "think_us": round((t2 - t1) / 1000, 1),
                "act_us": round((t3 - t2) / 1000, 1),
                "decision_latency_ms": round((t3 - t1) / 1e6, 4),  # Think + Act
                "network_status": "online" if is_connected else "offline-failover",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            message = json.dumps(payload)

            if is_connected:
                info = client.publish(MQTT_TOPIC, message, qos=0)
                if info.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"Published -> {MQTT_TOPIC}: {message}", flush=True)
                else:
                    print(f"Publish failed (rc={info.rc}), decision tetap jalan lokal", flush=True)
            else:
                print(f"[LOCAL] {message}", flush=True)

            time.sleep(PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
