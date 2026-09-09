"""Local tools and Pi-style matching, without network access."""

import json
import tempfile
import unittest
from pathlib import Path
from threading import Event

from joy.tools import _replace, create_tools


class ToolsTest(unittest.TestCase):
    def test_pi_matching(self):
        cases = [
            ('a\r\nb\r\n', 'a\nb', 'c\nd', 'c\r\nd\r\n'),
            ('\ufeffa\r\n', 'a', 'b', '\ufeffb\r\n'),
            ('keep “this”  \nx = “old”  \nend  \n', 'x = "old"', 'x = "new"',
             'keep “this”  \nx = "new"\nend  \n'),
            ('a  \nb  \nc  \n', 'a\nb\n', 'z\n', 'z\nc  \n'),
            ('before\nﬁ = 1  ', 'fi = 1', 'fi = 2', 'before\nfi = 2'),
            ('x = “old”  \n', '“old”', '“new”', 'x = “new”  \n'),
        ]
        for original, old, new, expected in cases:
            with self.subTest(original=original, old=old):
                self.assertEqual(_replace(original, old, new), expected)
        for original, old, new in [('x x', 'x', 'y'), ('“x” "x"', '"x"', 'y'),
                                   ('a', 'missing', 'b'), ('a', '', 'b'),
                                   ('a', 'a', 'a'), ('a', ' ', 'b')]:
            with self.assertRaises(ValueError):
                _replace(original, old, new)

    def test_tools_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cancelled = Event()
            tools = create_tools(root, cancelled)

            def run(name, **arguments):
                return tools.execute({'function': {'name': name, 'arguments': json.dumps(arguments)}})[0]

            run('write', path='src/demo.py', content='print(“hello”)\n')
            self.assertIn('1: print', run('read', path='src/demo.py'))
            result = run('edit', path='src/demo.py', old_text='print("hello")', new_text='print("bye")')
            self.assertIn('+print("bye")', result)
            self.assertEqual((root / 'src/demo.py').read_text(), 'print("bye")\n')
            self.assertIn('bye', run('bash', command='python3 src/demo.py'))
            self.assertIn('exit code 7', run('bash', command='exit 7'))
            self.assertIn('Timed out', run('bash', command='sleep 5', timeout=1))
            for name, args in [('read', {'path': '../outside'}),
                               ('write', {'path': '../outside', 'content': 'no'}),
                               ('edit', {'path': 'src/demo.py', 'old_text': 'absent', 'new_text': 'no'})]:
                with self.assertRaises(ValueError):
                    run(name, **args)
            self.assertEqual((root / 'src/demo.py').read_text(), 'print("bye")\n')
            (root / 'escape').symlink_to(root.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                run('write', path='escape/outside', content='no')
            cancelled.set()
            with self.assertRaises(InterruptedError):
                run('write', path='cancelled', content='no')
            self.assertFalse((root / 'cancelled').exists())
