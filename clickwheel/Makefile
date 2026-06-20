# Build the iPod click-wheel driver. Requires pigpio (sudo apt install pigpio).
# Must be built and run on the Raspberry Pi (uses the Broadcom GPIO peripheral).

CC      ?= gcc
CFLAGS  ?= -Wall -O2 -pthread
LDLIBS  := -lpigpio -lrt
PREFIX  ?= /usr/local

click: click.c
	$(CC) $(CFLAGS) -o click click.c $(LDLIBS)

# Run with: sudo ./click   (add -v for verbose packet logging)
run: click
	sudo ./click

install: click
	install -m 0755 click $(PREFIX)/bin/click

clean:
	rm -f click

.PHONY: run install clean
