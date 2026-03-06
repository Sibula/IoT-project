# IoT-project

*This code is for a small course project. It will not be further developed or maintained.*

IoT prototype for collecting environmental measurements using a BLE sensor node and a Bluetooth-capable edge node. We used an Arduino Nano 33 BLE Sense and a Raspberry Pi 3B+.

The Pi scans BLE advertisements and forwards measurements to an MQTT broker (Mosquitto), and also subscribes to the MQTT topic and pushes the data to InfluxDB. We then used IndxDB as a datasource for Grafana. The Python scripts `ble_to_mqtt.py` and `mqtt_to_influx.py` were set up with systemd services so they'll automatically start up and restart from failures.


Parts of the code contributed by [riinaeer](https://github.com/riinaeer) and [Miksuu14](https://github.com/Miksuu14).