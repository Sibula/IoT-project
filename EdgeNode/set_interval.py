import asyncio
import struct
import sys
from bleak import BleakScanner, BleakClient

CONFIG_NAME = "WeatherNode-Config"
INTERVAL_CHAR_UUID = "9b9a2f33-78e8-434c-b21e-c65dcfb2fbce"

MIN_INTERVAL_MS = 5000
MAX_INTERVAL_MS = 3600000

SCAN_TIMEOUT_SECONDS = 600  # 10 minutes


async def find_config_device():
    print(f"[BLE] Waiting for '{CONFIG_NAME}' (up to {SCAN_TIMEOUT_SECONDS}s)...")

    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or d.name or "") == CONFIG_NAME,
        timeout=SCAN_TIMEOUT_SECONDS,
    )

    return device


async def main():
    if len(sys.argv) != 2:
        print("Usage: python3 set_interval.py <interval_ms>")
        print("Example: python3 set_interval.py 10000")
        return

    try:
        new_interval_ms = int(sys.argv[1])
    except ValueError:
        print("Interval must be an integer (milliseconds).")
        return

    if not (MIN_INTERVAL_MS <= new_interval_ms <= MAX_INTERVAL_MS):
        print(f"Interval must be between {MIN_INTERVAL_MS} and {MAX_INTERVAL_MS} ms.")
        return

    dev = await find_config_device()

    if not dev:
        print("[BLE] Config device not found within timeout.")
        return

    print(f"[BLE] Found config device: {dev.address}")
    print("[BLE] Connecting...")

    data = struct.pack("<I", new_interval_ms)

    async with BleakClient(dev.address) as client:
        if not client.is_connected:
            print("Failed to connect.")
            return

        print("[BLE] Connected. Writing new interval...")
        await client.write_gatt_char(INTERVAL_CHAR_UUID, data, response=True)

    print(f"\nInterval successfully set to {new_interval_ms} ms")
    print("Verify by checking MQTT publish rate.\n")


if __name__ == "__main__":
    asyncio.run(main())
