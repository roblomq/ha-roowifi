# RooWifi — Home Assistant Integration

HACS custom integration for the **RooWifi Wi-Fi module** (Carnlan Engineering, ~2013) to control older iRobot Roomba vacuums (500/600/700 series) via Home Assistant.

## Hardware requirements

- iRobot Roomba 500/600/700 series with mini-DIN 7-pin (PS/2) SCI port
- [RooWifi module](http://www.roowifi.com/) connected to the SCI port
- RooWifi connected to your home network (LED blinks every 3 seconds)

## Installation via HACS

1. In Home Assistant, go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/roblomq/ha-roowifi` as category **Integration**
3. Search for **RooWifi** and click **Download**
4. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add integration**
2. Search for **RooWifi**
3. Enter:
   - **IP address**: e.g. `192.168.1.50` (set a DHCP reservation for a stable IP)
   - **Username**: `admin` (default)
   - **Password**: `roombawifi` (default)

## Entities

### Vacuum
| Entity | Description |
|---|---|
| `vacuum.roomba` | Main entity — start, pause, stop, return to base, spot clean |

### Sensors
| Entity | Unit |
|---|---|
| Battery | % |
| Battery Voltage | V |
| Battery Current | mA (negative = discharging) |
| Battery Temperature | °C |
| Charging State | text |
| Distance | mm (cumulative per session) |
| Angle | ° (cumulative per session) |

### Binary sensors
Bumper left/right, wheel drop left/right, cliff left/front-left/front-right/right, virtual wall, wall sensor, dirt detect.

## Notes

- Polling interval: **15 seconds** (per RooWifi recommendation; max 2 simultaneous connections)
- A sleeping Roomba is automatically woken via opcode 128 before each command
- The OI mode (passive/safe/full) is not available via the JSON API; vacuum state is tracked internally based on issued commands and charging status
- RooWifi supports 802.11b only — make sure your router allows legacy 802.11b clients

## License

MIT
