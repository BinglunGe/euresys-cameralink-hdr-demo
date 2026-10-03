# -*- coding: utf-8 -*-
"""GUI 冒烟测试: 预览/温度/快门/ROI帧率/增益/补偿/HDR/扫描。"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from vc71_gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.show()

S = {'phases': {}, 'phase': 'full', 'temps': [], 'errors': [],
     'hdr': None, 'scan_done': None, 't0': time.time(), 'phase_t0': time.time()}

win.cam.frame_ready.connect(lambda a: S['phases'].__setitem__(
    S['phase'], S['phases'].get(S['phase'], 0) + 1))
win.cam.temp_ready.connect(lambda t: S['temps'].append(t))
win.cam.hdr_done.connect(lambda p: S.__setitem__('hdr', p))
win.cam.scan_done.connect(lambda r, bu, bm: S.__setitem__('scan_done', (r, bu, bm)))
win.cam.error.connect(lambda m: S['errors'].append(m))
win.cam.status.connect(lambda m: print('  [状态]', m))


def to_roi():
    dur = time.time() - S['phase_t0']
    fps = S['phases'].get('full', 0) / dur
    print('[阶段1] 全幅预览 %.1fs: %d 帧 = %.2f fps' % (dur, S['phases'].get('full', 0), fps))
    S['phase'] = 'roi'; S['phase_t0'] = time.time()
    print('[阶段2] 设 ROI 2496x2000 + 增益31 + 补偿20 ...')
    win.roi_w.setValue(2496); win.roi_h.setValue(2000)
    win.on_roi_apply()
    win.gain_slider.setValue(31); win.on_gain()
    win.offset_slider.setValue(20); win.on_offset()


def to_hdr():
    dur = time.time() - S['phase_t0']
    fps = S['phases'].get('roi', 0) / dur
    print('[阶段2] ROI 预览 %.1fs: %d 帧 = %.2f fps' % (dur, S['phases'].get('roi', 0), fps))
    print('[阶段3] 触发 HDR ...')
    win.cam.start_hdr()


def phase4():
    print('[阶段4] 触发扫描 ...')
    win.cam.start_scan()


def report():
    print('\n=== 冒烟测试结果 ===')
    print('各阶段帧数:', S['phases'])
    print('温度:', S['temps'][:2])
    print('HDR:', S['hdr'])
    if S['scan_done']:
        r, bu, bm = S['scan_done']
        print('扫描(%d档) 最佳快门: %d us (均值 %.1f)' % (len(r), bu, bm))
    print('错误:', S['errors'] if S['errors'] else '无')
    win.close(); app.quit()


QTimer.singleShot(6000, to_roi)
QTimer.singleShot(12000, to_hdr)
win.cam.hdr_done.connect(lambda p: QTimer.singleShot(500, phase4))
win.cam.scan_done.connect(lambda r, bu, bm: QTimer.singleShot(1000, report))
QTimer.singleShot(80000, report)
sys.exit(app.exec())
