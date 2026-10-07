# -*- coding: utf-8 -*-
"""GUI 冒烟测试: 事件驱动跑一遍 预览 / ROI / 增益补偿 / HDR / 扫描。

    cd tests
    ../.venv/Scripts/python.exe smoke_gui.py

阶段推进靠"收集够帧数"或"等完成回调", 不用固定秒数
—— 启动期约 8s、全尺寸 HDR 约 50s、扫描 30s+, 固定秒数会把阶段截断(实测阶段1 得 0 帧、
报告里没有扫描结果)。兜底计时器只用于报告失败, 不再静默截断。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from vc71_gui import MainWindow
from vc71_camera import format_shutter

NEED_FRAMES = 8         # 每个预览阶段至少看到的帧数
WATCHDOG_S = 300        # 兜底: 超时报告失败(而非静默截断)

app = QApplication(sys.argv)
win = MainWindow()
win.show()

S = {'phase': None, 'frames': 0, 't0': 0.0, 'reports': {},
     'temps': [], 'errors': [], 'hdr': None, 'scan': None, 'fails': []}


def advance(name):
    S['phase'], S['frames'], S['t0'] = name, 0, time.time()
    print('[阶段] -> %s' % name)


def finish(name):
    dt = time.time() - S['t0'] or 1e-9
    S['reports'][name] = '%d 帧 / %.1fs = %.1f fps' % (S['frames'], dt, S['frames'] / dt)
    print('[阶段] <- %-5s %s' % (name, S['reports'][name]))
    if S['frames'] < NEED_FRAMES:
        S['fails'].append('%s 仅 %d 帧 (<%d)' % (name, S['frames'], NEED_FRAMES))


def on_frame(_arr):
    if S['phase'] not in ('full', 'roi'):
        return
    if S['frames'] == 0:
        S['t0'] = time.time()          # 从第一帧起计时: 线程启动期(~8s)不算进帧率
    S['frames'] += 1
    if S['frames'] < NEED_FRAMES:
        return
    name = S['phase']
    finish(name)
    if name == 'full':
        advance('roi')
        print('       ROI 1/4 + 增益31 + 补偿20')
        win.apply_preset(2496, 1776)
        win.gain_slider.setValue(31)
        win.on_gain()
        win.offset_slider.setValue(20)
        win.on_offset()
    else:
        advance('hdr')
        print('       触发 HDR ...')
        win.cam.start_hdr()


def on_hdr(path):
    S['hdr'] = path
    print('[阶段] <- hdr   %s' % path)
    advance('scan')
    print('       触发扫描 ...')
    win.cam.start_scan()


def on_scan(results, best_us, best_mean):
    S['scan'] = (results, best_us, best_mean)
    print('[阶段] <- scan  %d 档, 最佳 %s (均值 %.1f)' % (
        len(results), format_shutter(best_us), best_mean))
    report()


def report(_timeout=False):
    if S.get('reported'):
        return
    S['reported'] = True
    if _timeout:
        S['fails'].append('兜底超时 %ds' % WATCHDOG_S)
    print('\n=== 冒烟测试结果 ===')
    for k in ('full', 'roi'):
        print('  %-5s      %s' % (k, S['reports'].get(k, '(未完成)')))
    print('  温度      :', S['temps'][:2] or '(无)')
    print('  HDR 对比图:', S['hdr'] or '(未完成)')
    print('  扫描      :', ('%d 档, 最佳 %s (均值 %.1f)' % (
        len(S['scan'][0]), format_shutter(S['scan'][1]), S['scan'][2]))
        if S['scan'] else '(未完成)')
    print('  错误      :', S['errors'] or '无')
    print('  失败项    :', S['fails'] or '无')
    win.close()
    app.exit(1 if S['fails'] else 0)


win.cam.frame_ready.connect(on_frame)
win.cam.temp_ready.connect(lambda t: S['temps'].append(t))
win.cam.error.connect(lambda m: S['errors'].append(m))
win.cam.status.connect(lambda m: print('  [状态]', m))
win.cam.hdr_done.connect(on_hdr)
win.cam.scan_done.connect(on_scan)

QTimer.singleShot(0, lambda: advance('full'))
QTimer.singleShot(WATCHDOG_S * 1000, lambda: report(True))
sys.exit(app.exec())
