import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime
import random
import unittest
from core import (Profile, choose_typo, estimate_seconds, expand_template,
                  format_duration, keystroke_delay, parse_variables, prepare_text)

class TestCore(unittest.TestCase):
    def test_variables(self):
        s = expand_template('Hi {{name}} on {{date}}', {'name': 'Mona'}, now=datetime(2026, 10, 16))
        self.assertEqual(s, 'Hi Mona on 2026-10-16')

    def test_no_missing_variable(self):
        with self.assertRaisesRegex(ValueError, 'missing|Missing'):
            expand_template('{{unknown}}')

    def test_parse_variables(self):
        self.assertEqual(parse_variables('# note\nfirst=A=B\nname = Mahmoud'),
                         {'first':'A=B', 'name':'Mahmoud'})
        with self.assertRaises(ValueError): parse_variables('bad-value')

    def test_unicode_and_tabs(self):
        self.assertEqual(prepare_text('أهلا\r\n😀\tHi'), 'أهلا\n😀    Hi')
        self.assertEqual(prepare_text('a\tb', tabs_as_spaces=False), 'a\tb')
        with self.assertRaises(ValueError): prepare_text('\x00')

    def test_profile_bounded(self):
        p = Profile(wpm=500, typo_percent=99).clean()
        self.assertEqual(p.wpm, 220)
        self.assertEqual(p.typo_percent, 6)

    def test_delay_positive(self):
        p = Profile()
        self.assertGreater(keystroke_delay('x', '', p, random.Random(1)), 0)
        self.assertGreater(estimate_seconds('Hello world!\n', p), 0)
        self.assertEqual(format_duration(63), '1m 3s')

    def test_typo_choice(self):
        self.assertIsNone(choose_typo('x', Profile(typo_percent=0), random.Random(0)))
        self.assertIsNone(choose_typo('😀', Profile(typo_percent=6), random.Random(0)))

if __name__ == '__main__':
    unittest.main()