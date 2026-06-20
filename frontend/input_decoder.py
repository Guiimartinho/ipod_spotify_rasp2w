"""Pure decoding of click-wheel UDP packets into navigation events.

The click-wheel C driver (``clickwheel/click.c``) sends 3-byte UDP datagrams:
``[button_bit, button_state, wheel_position]``. This module turns a stream of those
packets into high-level events (up / down / select / back / play / next / prev).

It is deliberately free of any Tkinter / Pillow / network dependency so the trickiest
input logic in the project can be unit-tested without a display. ``spotifypod.py``
owns a single ``WheelDecoder`` and maps the returned events to its handlers.

The wheel thresholds below are intentionally identical to the original implementation;
they are calibrated to the real hardware and must not be changed without testing on
the device.
"""
from config import (
    CENTER_BUTTON_BIT,
    RIGHT_BUTTON_BIT,
    LEFT_BUTTON_BIT,
    DOWN_BUTTON_BIT,
    UP_BUTTON_BIT,
    WHEEL_TOUCH_BIT,
)

# Event names returned by WheelDecoder.decode()
EV_UP = "up"
EV_DOWN = "down"
EV_SELECT = "select"
EV_BACK = "back"
EV_PLAY = "play"
EV_NEXT = "next"
EV_PREV = "prev"

_BUTTON_EVENTS = {
    CENTER_BUTTON_BIT: EV_SELECT,
    UP_BUTTON_BIT: EV_BACK,
    DOWN_BUTTON_BIT: EV_PLAY,
    RIGHT_BUTTON_BIT: EV_NEXT,
    LEFT_BUTTON_BIT: EV_PREV,
}


class WheelDecoder:
    """Holds the small amount of state needed to decode the wheel between packets."""

    def __init__(self):
        self.wheel_position = -1
        self.last_button = -1

    def decode(self, button, button_state, position):
        """Return the list of events (possibly empty) produced by one packet.

        At most one wheel event and one button event are produced per packet, in
        that order, mirroring the original processInput() behaviour exactly.
        """
        events = []
        events.extend(self._decode_wheel(button, button_state, position))
        button_event = self._decode_button(button, button_state)
        if button_event is not None:
            events.append(button_event)
        return events

    def _decode_wheel(self, button, button_state, position):
        if button == WHEEL_TOUCH_BIT and button_state == 0:
            # finger lifted off the wheel
            self.wheel_position = -1
            return []
        if self.wheel_position == -1:
            self.wheel_position = position
            return []
        if position % 2 != 0:
            # ignore odd positions; the wheel is too sensitive otherwise
            return []
        if self.wheel_position <= 1 and position > 44:
            self.wheel_position = position
            return [EV_DOWN]
        if self.wheel_position >= 44 and position < 1:
            self.wheel_position = position
            return [EV_UP]
        if abs(self.wheel_position - position) > 6:
            # jump too large to be a real swipe: resync on the next packet
            self.wheel_position = -1
            return []
        if self.wheel_position > position:
            self.wheel_position = position
            return [EV_DOWN]
        if self.wheel_position < position:
            self.wheel_position = position
            return [EV_UP]
        return []

    def _decode_button(self, button, button_state):
        if button_state == 0:
            self.last_button = -1
            return None
        if button == self.last_button:
            # held down / repeated packet: only fire on the initial press
            return None
        event = _BUTTON_EVENTS.get(button)
        if event is not None:
            self.last_button = button
        return event
