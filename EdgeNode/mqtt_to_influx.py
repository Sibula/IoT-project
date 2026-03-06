import json
import time
import mqtt_config
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient

# --------- InfluxDB Settings ---------
INFLUX_HOST = "localhost"
INFLUX_PORT = 8086
INFLUX_DB   = "weather_data"

# --------- Initialize InfluxDB Client ---------
# No username/password needed for local prototype
influx_client = InfluxDBClient(
    host=INFLUX_HOST,
    port=INFLUX_PORT,
    database=INFLUX_DB
)

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"[MQTT] Connected. Subscribing to: {mqtt_config.MQTT_TOPIC}")
        client.subscribe(mqtt_config.MQTT_TOPIC)
    else:
        print(f"[MQTT] Connection failed with code: {reason_code}")

def on_message(client, userdata, msg):
    try:
        # 1. Parse Data
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        
        # Extract values safely (default to 0.0 if missing)
        t = float(data.get("temperature_c", 0.0))
        h = float(data.get("humidity_percent", 0.0))
        p = float(data.get("pressure_kpa", 0.0))
        rssi = int(data.get("rssi", 0))
        mac = data.get("address", "unknown")

        # 2. Format for InfluxDB v1
        json_body = [
            {
                "measurement": "weather_reading",
                "tags": {
                    "location": "balcony",
                    "device_mac": mac
                },
                "fields": {
                    "temperature": t,
                    "humidity": h,
                    "pressure": p,
                    "rssi": rssi
                }
            }
        ]

        # 3. Write Data
        influx_client.write_points(json_body)
        print(f"[Influx] Saved: {t:.2f}°C, {h:.1f}%, {p:.2f} kPa")

    except Exception as e:
        print(f"[Error] Failed to write to InfluxDB: {e}")

# --------- Main Loop ---------
def run():
    # Create MQTT Client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(mqtt_config.MQTT_USER, mqtt_config.MQTT_PASS)
    
    client.on_connect = on_connect
    client.on_message = on_message

    print("Starting MQTT -> InfluxDB Bridge...")

    # Infinite Reconnection Loop
    while True:
        try:
            client.connect(mqtt_config.MQTT_HOST, mqtt_config.MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print(f"Connection lost: {e}. Retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nStopping.")
