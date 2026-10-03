# -*- coding: utf-8 -*-
"""跑 tests/ 下全部 test_*.py (无需 pytest).

    python tests/run_tests.py
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'src'))

mods = sorted(f[:-3] for f in os.listdir(HERE)
              if f.startswith('test_') and f.endswith('.py'))
total = fails = 0
for name in mods:
    print('== %s ==' % name)
    mod = importlib.import_module(name)
    for fn in sorted(k for k, v in vars(mod).items() if k.startswith('test_') and callable(v)):
        total += 1
        try:
            getattr(mod, fn)()
            print('  PASS  %s' % fn)
        except Exception as e:
            fails += 1
            print('  FAIL  %s: %s' % (fn, e))
print('\n%d/%d passed across %d modules' % (total - fails, total, len(mods)))
raise SystemExit(1 if fails else 0)
