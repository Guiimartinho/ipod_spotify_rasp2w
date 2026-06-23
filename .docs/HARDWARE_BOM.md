# Hardware Bill of Materials (BOM)

The parts needed to build sPot, consolidated from the project schematic
([`.docs/sPot_schematic.png`](./sPot_schematic.png)), the repo README, the GPIO pins in
`clickwheel/click.c`, and the original author's component list on Hackaday.

> Authoritative sources: the [Hackaday components page](https://hackaday.io/project/177034/components)
> and [project writeup](https://hackaday.io/project/177034-spot-spotify-in-a-4th-gen-ipod-2004).
> This repo targets the **Raspberry Pi Zero 2 W** (the original build used a Pi Zero W; the 40-pin
> header and composite-video pads are identical, so the wiring is unchanged).

## Shopping list

| # | Item | Exact model / part number |
|---|------|---------------------------|
| 1 | Raspberry Pi | **Raspberry Pi Zero 2 W** (original build: Pi Zero W) |
| 2 | Donor iPod | **Apple iPod 4th generation, model A1059** (Click Wheel iPod) — provides the shell + Click Wheel |
| 3 | Display | **Adafruit 2" NTSC/PAL TFT Display** — Adafruit product **#911** (composite video input) |
| 4 | Click Wheel breakout | **0.5 mm, 8-pin FPC breakout board** — Amazon **B07H5GCZFW** |
| 5 | Battery | **Li-ion 3.7 V, 1000 mAh** rechargeable (community builds fit up to 2500 mAh) |
| 6 | Charger | **Adafruit Mini LiPoly/LiIon USB Charger** — Adafruit product **#1905** |
| 7 | 5 V boost | **Adafruit PowerBoost 1000 Basic** — Adafruit product **#2030** |
| 8 | Haptic motor | **10 x 2 mm Vibration Motor Disc** — Amazon **B073YFR5WR** |
| 9 | Transistor | **2N3904** NPN BJT (TO-92) — drives the haptic motor |
| 10 | Resistor | **220 Ω** — transistor base resistor (in the schematic; not in the Hackaday BOM) |
| 11 | Storage | **microSD card, 32 GB+** |
| — | Misc | thin wire, solder; optional 40-pin header for the Pi |

## Audio — no extra part to buy

Audio is **not** played through an internal speaker or DAC. `raspotify` (librespot) renders the
audio and `pi-btaudio` routes it over **Bluetooth**, which is built into the Pi Zero 2 W. You pair a
Bluetooth speaker/headphones; no audio hardware is purchased.

## Wiring (from the schematic + `click.c`)

Click Wheel (original iPod 8-pin flex, via the FPC breakout):

| Click Wheel pin | Connects to |
|-----------------|-------------|
| Pin 1 | +3.3 V |
| Pin 8 | GND |
| Pin 2 (Clock) | **GPIO 23** |
| Pin 6 (Data) | **GPIO 25** |

Haptic motor driver:

```
GPIO 26 ──[ 220 Ω ]── base (2N3904)
                        collector ── motor ── +5 V
                        emitter ───────────── GND
```

Display: composite video input wired to +5 V and the Pi's composite video output.

## Notes

- Items 2 and 4 work together: the FPC breakout connects the donor iPod's 8-pin Click Wheel flex
  cable to the Pi's GPIO.
- A larger battery (e.g. 2500 mAh) and the Pi Zero 2 W fit, but may require trimming components to
  close the iPod shell (per community builds).
- The display model is the original author's choice; some builders substitute a Waveshare
  composite display.
