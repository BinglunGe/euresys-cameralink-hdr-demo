# -*- coding: utf-8 -*-
"""run.bat 启动器验证 (无 pytest 依赖; 需相机环境).

    python tests/test_launcher.py     # 独立运行
    pytest tests/test_launcher.py     # 若装了 pytest

校验 run.bat 的启动器契约: 行尾/编码、git 属性、命令分发与 PYTHONPATH 隔离。
"""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(ROOT, 'run.bat')
GA = os.path.join(ROOT, '.gitattributes')
JUNK = ('AT command has been deprecated', 'is not recognized as an internal')


def _run_bat(args):
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    r = subprocess.run(['cmd.exe', '/c', BAT] + args, cwd=ROOT, env=env,
                       capture_output=True, input=b'\r\n', timeout=60)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


def test_bat_line_endings_and_encoding():
    raw = open(BAT, 'rb').read()
    assert raw.count(b'\r\n') > 0, 'run.bat 必须含 CRLF'
    assert raw.count(b'\n') == raw.count(b'\r\n'), 'run.bat 不能有裸 LF'
    assert raw[:3] != b'\xef\xbb\xbf', 'run.bat 不能有 BOM'
    assert all(b < 128 for b in raw), 'run.bat 必须是 ASCII (中文会让 cmd 解析错乱)'


def test_gitattributes_pins_bat_to_crlf():
    assert re.search(r'\*\.bat\s+text\s+eol=crlf', open(GA, encoding='utf-8').read())
    out = subprocess.run(['git', 'check-attr', 'eol', '--', 'run.bat'],
                         cwd=ROOT, capture_output=True, text=True).stdout
    assert 'eol: crlf' in out, out


def test_gui_alias_maps_to_existing_script():
    src = open(BAT, encoding='ascii').read()
    assert '"gui"' in src and 'vc71_gui.py' in src
    assert os.path.isfile(os.path.join(ROOT, 'src', 'vc71_gui.py'))


def test_launcher_dispatches_cleanly():
    cases = [('control --temp', ['control', '--temp']),
             ('control --cmd gag', ['control', '--cmd', 'gag']),
             ('direct script', ['vc71_control.py', '--temp']),
             ('snap', ['snap', '--shutter', '1000'])]
    for label, args in cases:
        rc, so = _run_bat(args)
        assert '[run.bat] python vc71_' in so, '%s 未分发到脚本: %s' % (label, so[:150])
        assert not any(k in so for k in JUNK), '%s 出现 cmd 杂讯: %s' % (label, so[:150])
        assert 'Traceback' not in so, '%s 脚本异常:\n%s' % (label, so[-400:])
        assert 'ModuleNotFoundError' not in so, '%s 环境被污染' % label


if __name__ == '__main__':
    fns = [v for k, v in sorted(vars().items()) if k.startswith('test_') and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn()
            print('PASS  %s' % fn.__name__)
        except AssertionError as e:
            fails += 1
            print('FAIL  %s: %s' % (fn.__name__, e))
    print('\n%d/%d passed' % (len(fns) - fails, len(fns)))
    raise SystemExit(1 if fails else 0)
