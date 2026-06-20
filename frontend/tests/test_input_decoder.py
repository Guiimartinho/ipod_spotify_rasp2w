import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

import config
from input_decoder import (
    WheelDecoder,
    EV_UP,
    EV_DOWN,
    EV_SELECT,
    EV_BACK,
    EV_PLAY,
    EV_NEXT,
    EV_PREV,
)

NO_BUTTON = 255  # value seen when only the wheel moves (no button bit set)


class TestButtonDecode(unittest.TestCase):
    def setUp(self):
        self.d = WheelDecoder()

    def test_each_button_fires_on_press(self):
        cases = [
            (config.CENTER_BUTTON_BIT, EV_SELECT),
            (config.UP_BUTTON_BIT, EV_BACK),
            (config.DOWN_BUTTON_BIT, EV_PLAY),
            (config.RIGHT_BUTTON_BIT, EV_NEXT),
            (config.LEFT_BUTTON_BIT, EV_PREV),
        ]
        for bit, event in cases:
            d = WheelDecoder()
            self.assertIn(event, d.decode(bit, 1, 0))

    def test_button_does_not_repeat_while_held(self):
        self.assertEqual(self.d.decode(config.CENTER_BUTTON_BIT, 1, 0), [EV_SELECT])
        # same button still pressed -> no event
        self.assertEqual(self.d.decode(config.CENTER_BUTTON_BIT, 1, 0), [])

    def test_button_fires_again_after_release(self):
        self.d.decode(config.CENTER_BUTTON_BIT, 1, 0)
        self.d.decode(config.CENTER_BUTTON_BIT, 0, 0)  # release
        self.assertEqual(self.d.decode(config.CENTER_BUTTON_BIT, 1, 0), [EV_SELECT])

    def test_unknown_button_is_ignored(self):
        self.assertEqual(self.d.decode(99, 1, 0), [])


class TestWheelDecode(unittest.TestCase):
    def setUp(self):
        self.d = WheelDecoder()

    def test_first_packet_only_sets_baseline(self):
        self.assertEqual(self.d.decode(NO_BUTTON, NO_BUTTON, 10), [])
        self.assertEqual(self.d.wheel_position, 10)

    def test_scroll_up_and_down(self):
        self.d.decode(NO_BUTTON, NO_BUTTON, 10)  # baseline
        self.assertEqual(self.d.decode(NO_BUTTON, NO_BUTTON, 12), [EV_UP])
        self.assertEqual(self.d.decode(NO_BUTTON, NO_BUTTON, 10), [EV_DOWN])

    def test_odd_positions_ignored(self):
        self.d.decode(NO_BUTTON, NO_BUTTON, 10)
        self.assertEqual(self.d.decode(NO_BUTTON, NO_BUTTON, 11), [])

    def test_wraparound_low_to_high_is_down(self):
        self.d.decode(NO_BUTTON, NO_BUTTON, 0)  # baseline at bottom
        self.assertEqual(self.d.decode(NO_BUTTON, NO_BUTTON, 46), [EV_DOWN])

    def test_wraparound_high_to_low_is_up(self):
        self.d.decode(NO_BUTTON, NO_BUTTON, 44)  # baseline at top
        self.assertEqual(self.d.decode(NO_BUTTON, NO_BUTTON, 0), [EV_UP])

    def test_large_jump_resyncs_without_event(self):
        self.d.decode(NO_BUTTON, NO_BUTTON, 10)
        self.assertEqual(self.d.decode(NO_BUTTON, NO_BUTTON, 20), [])
        self.assertEqual(self.d.wheel_position, -1)

    def test_wheel_touch_release_resets_position(self):
        self.d.decode(NO_BUTTON, NO_BUTTON, 10)
        self.assertEqual(self.d.decode(config.WHEEL_TOUCH_BIT, 0, 10), [])
        self.assertEqual(self.d.wheel_position, -1)


if __name__ == "__main__":
    unittest.main()
