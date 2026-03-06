# Central configuration file for the MQTT things since they are the same across the different scripts. This way we can just import the settings instead of copy-pasting them around.

# --------- MQTT settings ----------
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_USER = "iot"
MQTT_PASS = "IoT-project"
MQTT_TOPIC = "weather/reading"
MQTT_CLIENT_ID = "weather-ble-bridge"
