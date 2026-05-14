# RooWifi — Home Assistant Integration

HACS custom integration voor de **RooWifi WiFi-module** (Carnlan Engineering, ~2013) om oudere iRobot Roomba's (500/600/700-serie) te bedienen via Home Assistant.

## Hardware vereisten

- iRobot Roomba 500/600/700-serie met mini-DIN 7-pin (PS/2) SCI-poort
- [RooWifi module](http://www.roowifi.com/) verbonden via de SCI-poort
- RooWifi verbonden met je thuisnetwerk (LED knippert elke 3 seconden)

## Installatie via HACS

1. Ga in Home Assistant naar **HACS → Integraties → ⋮ → Aangepaste opslagplaatsen**
2. Voeg `https://github.com/roblomq/ha-roowifi` toe als categorie **Integratie**
3. Zoek naar **RooWifi** en klik op **Downloaden**
4. Herstart Home Assistant

## Configuratie

1. Ga naar **Instellingen → Apparaten & Diensten → Integratie toevoegen**
2. Zoek op **RooWifi**
3. Vul in:
   - **IP-adres**: bijv. `192.168.178.185` (stel DHCP-reservering in voor een vast IP)
   - **Gebruikersnaam**: `admin` (standaard)
   - **Wachtwoord**: `roombawifi` (standaard)

## Entiteiten

### Stofzuiger
| Entiteit | Beschrijving |
|---|---|
| `vacuum.roomba` | Hoofdentiteit — start, pauze, stop, dock, spot clean |

### Sensoren
| Entiteit | Eenheid |
|---|---|
| Battery | % |
| Battery Voltage | V |
| Battery Current | mA (negatief = ontladen) |
| Battery Temperature | °C |
| Charging State | tekst |
| Distance | mm (cumulatief per sessie) |
| Angle | ° (cumulatief per sessie) |

### Binary sensoren
Bumper links/rechts, wieldrop links/rechts, cliff links/front-links/front-rechts/rechts, virtual wall, wall sensor, dirt detect.

## Opmerkingen

- Polling interval: **15 seconden** (conform RooWifi aanbeveling, max 2 gelijktijdige verbindingen)
- Een slapende Roomba wordt automatisch gewekt voor elk commando via opcode 128
- De OI-modus (passive/safe/full) is niet beschikbaar via de JSON API; de vacuümstatus wordt bijgehouden op basis van interne toestand en laadstatus
- RooWifi ondersteunt alleen 802.11b — zorg dat je router legacy 802.11b toestaat

## Licentie

MIT
