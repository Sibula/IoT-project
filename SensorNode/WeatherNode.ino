#include <Arduino_HTS221.h>  // Temperature & humidity sensor
#include <Arduino_LPS22HB.h> // Pressure sensor
#include <ArduinoBLE.h>
#include "mbed.h" // For FlashIAP (and Watchdog?)

static const uint32_t DEFAULT_INTERVAL_MS = 60000;                    // 1 minute
static const uint32_t MIN_INTERVAL_MS = 5000;                         // 5 seconds
static const uint32_t MAX_INTERVAL_MS = 3600000;                      // 1 hour
static const unsigned long CONFIG_ADVERTISING_DURATION_MS = 10000;    // 10 seconds
static const unsigned long MEASUREMENT_ADVERTISING_DURATION_MS = 300; // 300ms, still robust with low power use
static const uint32_t WATCHDOG_TIMEOUT_SECONDS = 2 * 60 * 60;         // 2 hours

mbed::FlashIAP flash;
uint32_t flashAddress;
uint32_t interval = DEFAULT_INTERVAL_MS;

BLEService configService("9b9a2f33-78e8-434c-b21e-c65dcfb2fbce");
BLEUnsignedIntCharacteristic intervalCharacteristic("9b9a2f33-78e8-434c-b21e-c65dcfb2fbce", BLERead | BLEWrite);

struct Config
{
  uint32_t magic;    // Magic number to validate config integrity
  uint32_t interval; // Measurement interval in milliseconds
};
#define CONFIG_MAGIC 0xDEADBEEF

struct __attribute__((packed)) WeatherData
{
  uint16_t companyId; // Bluetooth SIG assigned Company Identifier, use 0xFFFF
  float temperature;  // °C
  float humidity;     // %RH
  float pressure;     // kPa
};

void configurationWindow()
{
  BLE.setLocalName("WeatherNode-Config");
  configService.addCharacteristic(intervalCharacteristic);
  BLE.addService(configService);
  BLE.setAdvertisedService(configService);
  intervalCharacteristic.writeValue(interval);
  BLE.advertise();

  unsigned long startTime = millis();
  while (millis() - startTime < CONFIG_ADVERTISING_DURATION_MS)
  {
    BLEDevice central = BLE.central();
    if (central)
    {
      while (central.connected())
      {
        if (intervalCharacteristic.written())
        {
          uint32_t newInterval = intervalCharacteristic.value();
          if (newInterval >= MIN_INTERVAL_MS && newInterval <= MAX_INTERVAL_MS && newInterval != interval)
          {
            interval = newInterval;
            Config config = {
              .magic = CONFIG_MAGIC,
              .interval = interval
            };
            flash.erase(flashAddress, flash.get_sector_size(flashAddress));
            flash.program(&config, flashAddress, sizeof(Config));
          }
        }
      }
    }
  }
  BLE.stopAdvertise();
  BLE.end();
  delay(500);
  if (!BLE.begin())
  {
    delay(60000);
    while (1);
  }
  flash.deinit(); // Not needed anymore - deinitialize to save power
}

void setup()
{
  digitalWrite(LED_PWR, LOW); // Disable power LED to save power
  NRF_POWER->DCDCEN = 1;      // Enable DC/DC Converter for better power efficiency

  // Set up a watchdog timer to reset the device if it becomes unresponsive
  NRF_WDT->CONFIG = 0x01;                            // Configure WDT to run when CPU is asleep
  NRF_WDT->CRV = WATCHDOG_TIMEOUT_SECONDS * 32768UL; // Timeout set to 2 hours (32768 ticks per second)
  NRF_WDT->RREN = 0x01;                              // Enable the RR[0] reload register
  NRF_WDT->TASKS_START = 1;                          // Start WDT

  // Initialize BLE and sensors
  if (!BLE.begin() || !HTS.begin() || !BARO.begin())
  {
    // Failed to initialize a module - sleep to conserve power
    while (true)
    {
      delay(60000);
    }
  }

  // Initialize flash storage. Use the last sector, which shouldn't
  // interfere with the bootloader (0x0-0x10000) or firmware (0x10000->)
  flash.init();
  uint32_t flashEnd = flash.get_flash_start() + flash.get_flash_size();
  flashAddress = flashEnd - flash.get_sector_size(flashEnd - 1);

  // Read stored interval from flash
  Config config;
  memcpy(&config, (void *)flashAddress, sizeof(Config));
  if (config.magic == CONFIG_MAGIC && config.interval >= MIN_INTERVAL_MS && config.interval <= MAX_INTERVAL_MS)
  {
    interval = config.interval;
  }

  // Configuration window for setting measurement interval
  // TODO: Rework configuration window to be triggered by repeated reset or 
  // connecting during advertising to further reduce power consumption.
  configurationWindow();

  // Change local name for normal operation after configuration
  BLE.setLocalName("WeatherNode");
}

void loop()
{
  NRF_WDT->RR[0] = WDT_RR_RR_Reload; // Reset watchdog timer

  // Read sensors
  float temperature = HTS.readTemperature();
  float humidity = HTS.readHumidity();
  float pressure = BARO.readPressure();

  // Send data as manufacturer data in BLE advertisements to reduce connection overhead and save power
  WeatherData data = {
      .companyId = 0xFFFF,
      .temperature = temperature,
      .humidity = humidity,
      .pressure = pressure};
  BLE.setManufacturerData((uint8_t *)&data, sizeof(data));
  BLE.advertise();
  delay(MEASUREMENT_ADVERTISING_DURATION_MS);
  BLE.stopAdvertise();

  delay(constrain(interval, MIN_INTERVAL_MS, MAX_INTERVAL_MS));
}
