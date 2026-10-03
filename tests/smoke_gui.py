# -*- coding: utf-8 -*-
"""GUI 冒烟测试: 启动后自动跑一遍 预览 / ROI / 增益补偿 / HDR / 扫描。

    cd tests
    ../.venv/Scripts/python.exe smoke_gui.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from vc71_gui import MainWindow
from vc71_camera import SETTINGS, format_shutter

app = QApplication(sys.argv)
win = MainWindow()
win.show()

S = {'phases': {}, 'phase': 'full', 'temps': [], 'errors': [],
     'hdr': None, 'scan': None, 'pt0': time.time()}

win.cam.frame_ready.connect(lambda a: S['phases'].__setitem__(
    S['phase'], S['phases'].get(S['phase'], 0) + 1))
win.cam.temp_ready.connect(lambda t: S['temps'].append(t))
win.cam.hdr_done.connect(lambda p: S.__setitem__('hdr', p))
win.cam.scan_done.connect(lambda r, bu, bm: S.__setitem__('scan', (r, bu, bm)))
win.cam.error.connect(lambda m: S['errors'].append(m))
win.cam.status.connect(lambda m: print('  [状态]', m))


def to_roi():
    dt = time.time() - S['pt0']
    print('[阶段1] 全幅预览 %.1fs: %d 帧' % (dt, S['phases'].get('full', 0)))
    S['phase'] = 'roi'
    S['pt0'] = time.time()
    print('[阶段2] ROI 1/4 + 增益31 + 补偿20')
    win.apply_preset(2496, 1776)
    win.gain_slider.setValue(31)
    win.on_gain()
    win.offset_slider.setValue(20)
    win.on_offset()
    print('      快门标签:', win.shutter_label.text())


def to_hdr():
    dt = time.time() - S['pt0']
    n = S['phases'].get('roi', 0)
    print('[阶段2] ROI 预览 %.1fs: %d 帧 = %.1f fps' % (dt, n, n / dt if dt else 0))
    print('[阶段3] 触发 HDR ...')
    win.cam.start_hdr()


def to_scan():
    print('[阶段4] 触发扫描 ...')
    win.cam.start_scan()


def report():
    print('\n=== 冒烟测试结果 ===')
    print('各阶段帧数:', S['phases'])
    print('温度:', S['temps'][:2])
    print('HDR 对比图:', S['hdr'])
    if S['scan']:
        r, bu, bm = S['scan']
        print('扫描 %d 档, 最佳快门: %s (%dus, 均值 %.1f)' % (
            len(r), format_shutter(bu), bu, bm))
    print('错误:', S['errors'] if S['errors'] else '无')
    win.close()
    app.quit()


QTimer.singleShot(6000, to_roi)
QTimer.singleShot(12000, to_hdr)
win.cam.hdr_done.connect(lambda p: QTimer.singleShot(500, to_scan))
win.cam.scan_done.connect(lambda r, bu, bm: QTimer.singleShot(1000, report))
QTimer.singleShot(90000, report)
sys.exit(app.exec())
