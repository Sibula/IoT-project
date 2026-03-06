import asyncio
import json
import struct
import time
import mqtt_config
from typing import Optional, Tuple

import paho.mqtt.client as mqtt
from bleak import BleakScanner

# --------- Device filtering ----------
TARGET_MAC = "00:11:22:33:44:55"
TARGET_NAME = "WeatherNode"          # Optional extra check if name is present

# --------- Manufacturer payload parsing ----------
MFG_ID_PAYLOAD = 0xFFFF              # Used only to locate the payload in manufacturer_data
# Payload is 12 bytes (3 floats) OR 16 bytes (4-byte header + 12 bytes floats)

# --------- MQTT settings ----------
MQTT_HOST = mqtt_config.MQTT_HOST
MQTT_PORT = mqtt_config.MQTT_PORT
MQTT_USER = mqtt_config.MQTT_USER
MQTT_PASS = mqtt_config.MQTT_PASS
MQTT_TOPIC = mqtt_config.MQTT_TOPIC
MQTT_CLIENT_ID = mqtt_config.MQTT_CLIENT_ID

# --------- Runtime behavior ----------
DUPLICATE_EPS = 1e-5
STATUS_EVERY_SECONDS = 30
MQTT_RECONNECT_SECONDS = 5


def parse_weather_payload(data: bytes) -> Optional[Tuple[float, float, float]]:
    """Parse 3 little-endian floats (T, H, P) from manufacturer payload."""
    if len(data) == 16:
        data = data[4:]  # Drop optional 4-byte header
    if len(data) != 12:
        return None
    t, h, p = struct.unpack("<fff", data)
    return t, h, p


def floats_close(a: Tuple[float, float, float], b: Tuple[float, float, float], eps: float) -> bool:
    return (abs(a[0] - b[0]) < eps) and (abs(a[1] - b[1]) < eps) and (abs(a[2] - b[2]) < eps)


def build_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=MQTT_CLIENT_ID
    )

    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("[MQTT] Connected")
        else:
            print(f"[MQTT] Connect failed rc={reason_code}")

    def on_disconnect(client, userdata, reason_code, properties):
        print(f"[MQTT] Disconnected rc={reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    return client



def mqtt_connect_loop(client: mqtt.Client) -> None:
    """Connect to broker and start background network loop. Raises on failure."""
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()


async def run_service() -> None:
    mqtt_client = build_mqtt_client()

    # Try to connect MQTT initially, retry until success
    while True:
        try:
            mqtt_connect_loop(mqtt_client)
            break
        except Exception as e:
            print(f"[MQTT] Initial connect failed: {e}. Retrying in {MQTT_RECONNECT_SECONDS}s...")
            await asyncio.sleep(MQTT_RECONNECT_SECONDS)

    last_vals: Optional[Tuple[float, float, float]] = None
    msg_count = 0
    last_status = time.time()

    print("[BLE] Starting continuous scan. Press Ctrl+C to stop.")
    print(f"[BLE] Filtering by MAC: {TARGET_MAC}")
    print(f"[MQTT] Publishing to topic: {MQTT_TOPIC}\n")

    def callback(device, advertisement_data):
        nonlocal last_vals, msg_count, last_status

        # Primary filter: only accept our physical device
        if device.address != TARGET_MAC:
            return

        # Optional name check (only if name exists in the ad)
        name = advertisement_data.local_name or device.name or ""
        if name and name != TARGET_NAME:
            return

        mfg = advertisement_data.manufacturer_data or {}
        if MFG_ID_PAYLOAD not in mfg:
            return

        vals = parse_weather_payload(mfg[MFG_ID_PAYLOAD])
        if not vals:
            return

        # Skip duplicates (float-safe)
        if last_vals is not None and floats_close(vals, last_vals, DUPLICATE_EPS):
            return
        last_vals = vals

        t, h, p = vals
        rssi = getattr(advertisement_data, "rssi", None)

        payload = {
            "ts": time.time(),
            "address": device.address,
            "name": name or None,
            "rssi": rssi,
            "temperature_c": float(t),
            "humidity_percent": float(h),
            "pressure_kpa": float(p),
        }

        # Publish JSON payload
        try:
            mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=0, retain=False)
            msg_count += 1
            print(f"[{msg_count}] RSSI={rssi} T={t:.2f}°C H={h:.2f}% P={p:.2f}kPa -> published")
        except Exception as e:
            # If publish fails due to connection issues, log and continue;
            print(f"[MQTT] Publish failed: {e}")

        # Periodic heartbeat
        now = time.time()
        if now - last_status >= STATUS_EVERY_SECONDS:
            print(f"[STATUS] published={msg_count} last_rssi={rssi}")
            last_status = now

    scanner = BleakScanner(detection_callback=callback)

    await scanner.start()
    try:
        while True:
            await asyncio.sleep(1.0)
    finally:
        await scanner.stop()
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        print("\nStopped by user.")

