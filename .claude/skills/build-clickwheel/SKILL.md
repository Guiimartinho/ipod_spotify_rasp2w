---
name: build-clickwheel
description: Compile and run the sPot click-wheel C driver (clickwheel/click.c). Use when asked to build, compile, make, or run the click-wheel / clickwheel driver, the C input driver, or the pigpio GPIO program. Covers the gcc invocation, the pigpio/root requirement, and how it talks to the Python app over UDP.
---

# Build the click-wheel driver (`clickwheel/click.c`)

`click.c` is a pigpio-based C daemon that runs on the Raspberry Pi. It reads the original iPod
click-wheel over GPIO (CLOCK=23, DATA=25, haptic motor=26), decodes 32-bit serial packets, and
forwards 3-byte input events to the Python UI over **UDP `127.0.0.1:9090`**
(`[buttonBit, state, wheelPos]`). It only builds and runs meaningfully **on the Pi** — `libpigpio`
needs the Broadcom GPIO peripheral.

## There is no Makefile
The build command lives only as a comment at the top of `click.c`. The canonical invocation:
```sh
cd clickwheel
gcc -Wall -pthread -o click click.c -lpigpio -lrt
```
- `-lpigpio` — the GPIO library (install: `sudo apt install pigpio` or build from source per README).
- `-lrt` — POSIX realtime (clock/timer) functions.
- `-pthread` — pigpio uses threads/alert callbacks.

## Run (on the Pi)
```sh
sudo ./click          # root required: pigpio uses direct peripheral/DMA access
```
`pigpiod`/libpigpio must be available; ensure it is enabled (`sudo systemctl enable pigpiod` if you
use the daemon variant). The program currently runs forever in a busy `while(1){}` loop.

## Verifying it without the iPod hardware
You generally can't run this off-Pi. To prove the UDP contract end-to-end, you can mimic the driver
from any machine — send a 3-byte datagram to the app:
```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(bytes([7, 1, 0]), ("127.0.0.1", 9090))   # center button press
```
Button bit codes (shared by convention with `spotifypod.py`): center=7, right/next=8, left/prev=9,
down/play=10, up/back=11, wheel-touch=29.

## Known issues to be aware of when editing (see .docs/AUDIT.md §click.c)
- Busy-wait `while(1){}` pins a CPU core — prefer `pause()` + signal-driven `gpioTerminate`.
- pigpio and `sendto` return codes are unchecked.
- ISR-shared globals aren't `volatile`; `main` has a non-standard signature.
- GPIO pins and button codes are duplicated in the Python side — keep both in sync.

## Recommended improvement
Add a `clickwheel/Makefile` so the build is one command and the deploy docs can reference it:
```make
click: click.c
	gcc -Wall -pthread -o click click.c -lpigpio -lrt
install: click
	# copy/enable as appropriate for the target
.PHONY: install
```
