# -*- coding: utf-8 -*-
"""VC-71MC-M4 相机控制 GUI (PySide6)

功能: 实时预览 / 相机端ROI(预设,提帧率) / 快门(滑条+输入+加减档,摄影格式显示) /
      增益 / 补偿 / 温度 / 帧率 / 抓单帧 / HDR 合成 / 曝光扫描(最佳快门)。

所有参数读 ../settings.xml。相机操作集中在单个 CameraThread。
"""
import os
import sys
import time
import queue

import numpy as np
import cv2
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel,
                               QVBoxLayout, QHBoxLayout, QSlider, QPushButton,
                               QGroupBox, QDialog, QSpinBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap

from MultiCam import MC
from vc71_camera import (SETTINGS, W, H, configure_channel, grab_frame,
                         CameraSerial, format_shutter, slider_to_us, us_to_slider)
from vc71_hdr import merge, make_compare, filter_bracket

SAT = SETTINGS.sat
DISPLAY_W, DISPLAY_H = SETTINGS.display_w, SETTINGS.display_h
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')


class CameraThread(QThread):
    frame_ready = Signal(object)
    temp_ready = Signal(str)
    shutter_result = Signal(str)
    hdr_done = Signal(str)
    scan_update = Signal(object, int)
    scan_done = Signal(object, int, float)
    status = Signal(str)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.tasks = queue.Queue()
        self.running = False
        self.save_request = False

    def run(self):
        ser = None
        try:
            ser = CameraSerial().open()
        except Exception as e:
            self.error.emit('串口不可用(快门/温度/ROI/增益不可用): %s' % e)
        try:
            MC.OpenDriver()
            channel = MC.Create('CHANNEL')
        except Exception as e:
            self.error.emit('采集卡不可用: %s' % e)
            if ser:
                ser.close()
            return
        try:
            configure_channel(channel)
            if ser:
                ser.set_shutter(10000)          # 设默认短快门
                try:
                    grab_frame(channel, 8000)   # 丢弃继承的旧快门首帧
                except Exception:
                    pass
            self.running = True
            while self.running:
                try:
                    task = self.tasks.get_nowait()
                except queue.Empty:
                    task = None
                if task:
                    self._handle_task(task, ser, channel)
                    continue
                try:
                    frame = grab_frame(channel, timeout_ms=3000)
                except Exception:
                    continue
                if self.save_request:
                    self.save_request = False
                    os.makedirs(OUTDIR, exist_ok=True)
                    ts = time.strftime('%Y%m%d-%H%M%S')
                    path = os.path.join(OUTDIR, 'gui_%s.png' % ts)
                    cv2.imwrite(path, (frame >> 4).astype(np.uint8))
                    self.status.emit('已保存: %s' % path)
                fh, fw = frame.shape
                scale = min(1.0, DISPLAY_W / fw, DISPLAY_H / fh)
                if scale < 1.0:
                    frame = cv2.resize(frame, (int(fw * scale), int(fh * scale)),
                                       interpolation=cv2.INTER_AREA)
                self.frame_ready.emit((frame >> 4).astype(np.uint8))
        finally:
            MC.Delete(channel)
            MC.CloseDriver()
            if ser:
                ser.close()

    def _handle_task(self, task, ser, channel):
        kind = task[0]
        if kind == 'set_shutter':
            if ser:
                self.shutter_result.emit(ser.set_shutter(task[1]))
        elif kind == 'get_temp':
            if ser:
                self.temp_ready.emit(ser.get_temp())
        elif kind == 'set_gain':
            if ser:
                ser.set_gain(task[1])
        elif kind == 'set_offset':
            if ser:
                ser.set_offset(task[1])
        elif kind == 'set_roi':
            self._apply_roi(ser, channel, task[1], task[2])
        elif kind == 'hdr':
            self._do_hdr(ser, channel, task[1])
        elif kind == 'scan':
            self._do_scan(ser, channel, task[1])

    def _apply_roi(self, ser, channel, w, h):
        # 不做 16 取整: 全幅高 7096 非16倍数, 取整会与 MultiCam 不匹配导致超时
        w = max(SETTINGS.roi_step, min(W, int(w)))
        h = max(SETTINGS.roi_step, min(H, int(h)))
        if ser:
            ser.set_roi(w, h)
        MC.SetParamInt(channel, 'Hactive_Px', w)
        MC.SetParamInt(channel, 'Vactive_Ln', h)
        try:
            grab_frame(channel, 8000)           # 尺寸变更后重新同步
        except Exception:
            pass
        est = (W * H) / (w * h) * 2.19
        self.status.emit('ROI = %dx%d (预计 ~%.1f fps)' % (w, h, est))

    def _do_hdr(self, ser, channel, shutters):
        self._apply_roi(ser, channel, W, H)     # HDR 用全幅
        self.status.emit('HDR: 采集 %d 档曝光...' % len(shutters))
        dw, dh = int(W * SETTINGS.hdr_scale), int(H * SETTINGS.hdr_scale)
        imgs12, imgs8, times, means = [], [], [], []
        for i, us in enumerate(shutters):
            if ser:
                ser.set_shutter(us)
            grab_frame(channel, 25000)          # 丢弃首帧(快门切换需一帧生效)
            frame = grab_frame(channel, 25000)
            mean = float(frame.mean())
            means.append(mean)
            f = cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_AREA)
            imgs12.append(f)
            imgs8.append((f >> 4).astype(np.uint8))
            times.append(us / 1e6)
            self.status.emit('HDR %d/%d: %s 均值 %.1f' % (
                i + 1, len(shutters), format_shutter(us), mean))
        imgs12, imgs8, times, dropped = filter_bracket(imgs12, imgs8, times, means)
        if dropped:
            self.status.emit('HDR: 剔除 %d 个极端曝光档' % dropped)
        self.status.emit('HDR: 合成中...')
        hdr, ldr_d, E, ldr_l = merge(imgs12, imgs8, times)
        cmp = make_compare((ldr_d * 255).astype(np.uint8),
                           (ldr_l * 255).astype(np.uint8))
        os.makedirs(OUTDIR, exist_ok=True)
        ts = time.strftime('%Y%m%d-%H%M%S')
        path = os.path.join(OUTDIR, 'hdr_%s.png' % ts)
        cv2.imwrite(path, cmp)
        cv2.imwrite(os.path.join(OUTDIR, 'hdr_%s.hdr' % ts), hdr)
        self.hdr_done.emit(path)

    def _do_scan(self, ser, channel, shutters):
        self._apply_roi(ser, channel, W, H)
        self.status.emit('曝光扫描: %d 档...' % len(shutters))
        results = []
        for us in shutters:
            if ser:
                ser.set_shutter(us)
            grab_frame(channel, 25000)
            frame = grab_frame(channel, 25000)
            mean = float(frame.mean())
            results.append((us, mean))
            fh, fw = frame.shape
            scale = min(1.0, DISPLAY_W / fw, DISPLAY_H / fh)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(fw * scale), int(fh * scale)),
                                   interpolation=cv2.INTER_AREA)
            self.scan_update.emit((frame >> 4).astype(np.uint8), us)
            self.status.emit('扫描 %s: 均值 %.1f' % (format_shutter(us), mean))
        target = SAT * SETTINGS.scan_target
        best_us, best_mean = min(results, key=lambda r: abs(r[1] - target))
        self.scan_done.emit(results, best_us, best_mean)

    # 对外接口
    def set_shutter(self, us):
        self.tasks.put(('set_shutter', us))

    def get_temp(self):
        self.tasks.put(('get_temp', None))

    def set_gain(self, v):
        self.tasks.put(('set_gain', v))

    def set_offset(self, v):
        self.tasks.put(('set_offset', v))

    def set_roi(self, w, h):
        self.tasks.put(('set_roi', w, h))

    def start_hdr(self):
        self.tasks.put(('hdr', SETTINGS.hdr_shutters))

    def start_scan(self):
        self.tasks.put(('scan', SETTINGS.scan_shutters))

    def request_save(self):
        self.save_request = True

    def stop(self):
        self.running = False


class ImageViewer(QDialog):
    def __init__(self, path, title='结果'):
        super().__init__()
        self.setWindowTitle(title)
        label = QLabel()
        label.setPixmap(QPixmap(path))
        label.setScaledContents(True)
        label.setMinimumSize(1000, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('%s 控制' % SETTINGS.model)

        self.image_label = QLabel('正在启动...')
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(DISPLAY_W, DISPLAY_H)
        self.image_label.setStyleSheet('background:#000; color:#fff;')

        # 温度 + 帧率
        self.temp_label = QLabel('温度: --')
        self.fps_label = QLabel('帧率: --')
        stat_row = QHBoxLayout()
        stat_row.addWidget(self.temp_label)
        stat_row.addStretch(1)
        stat_row.addWidget(self.fps_label)

        # 快门
        self.shutter_label = QLabel('快门: --')
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(us_to_slider(10000))
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.shutter_spin = QSpinBox()
        self.shutter_spin.setRange(SETTINGS.shutter_min_us, SETTINGS.shutter_max_us)
        self.shutter_spin.setValue(10000)
        self.shutter_spin.setSuffix(' us')
        self.shutter_spin.editingFinished.connect(self.on_spin_changed)
        self.inc_btn = QPushButton('+ 0.25 档')
        self.dec_btn = QPushButton('- 0.25 档')
        self.inc_btn.clicked.connect(lambda: self.step_ev(0.25))
        self.dec_btn.clicked.connect(lambda: self.step_ev(-0.25))
        step_row = QHBoxLayout()
        step_row.addWidget(self.dec_btn)
        step_row.addWidget(self.inc_btn)

        # 增益 / 补偿
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(0, SETTINGS.gain_max)
        self.gain_slider.sliderReleased.connect(self.on_gain)
        self.gain_label = QLabel('增益: 0 (0.0 dB)')
        self.offset_slider = QSlider(Qt.Horizontal)
        self.offset_slider.setRange(0, SETTINGS.offset_max)
        self.offset_slider.sliderReleased.connect(self.on_offset)
        self.offset_label = QLabel('补偿: 0')

        # ROI 预设 + 自定义
        self.roi_w = QSpinBox()
        self.roi_w.setRange(SETTINGS.roi_step, W)
        self.roi_w.setSingleStep(SETTINGS.roi_step)
        self.roi_w.setValue(W)
        self.roi_h = QSpinBox()
        self.roi_h.setRange(SETTINGS.roi_step, H)
        self.roi_h.setSingleStep(SETTINGS.roi_step)
        self.roi_h.setValue(H)
        preset_row = QHBoxLayout()
        for name, pw, ph in SETTINGS.roi_presets:
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, w=pw, h=ph: self.apply_preset(w, h))
            preset_row.addWidget(b)
        roi_row = QHBoxLayout()
        roi_row.addWidget(QLabel('W'))
        roi_row.addWidget(self.roi_w)
        roi_row.addWidget(QLabel('H'))
        roi_row.addWidget(self.roi_h)
        self.roi_apply = QPushButton('应用')
        self.roi_apply.clicked.connect(lambda: self.cam.set_roi(self.roi_w.value(), self.roi_h.value()))
        roi_row.addWidget(self.roi_apply)

        # 操作按钮
        self.snap_btn = QPushButton('抓单帧(存PNG)')
        self.snap_btn.clicked.connect(self.on_snap)
        self.hdr_btn = QPushButton('HDR 合成')
        self.hdr_btn.clicked.connect(self.on_hdr)
        self.scan_btn = QPushButton('曝光扫描')
        self.scan_btn.clicked.connect(self.on_scan)
        self.status_label = QLabel('')
        self.status_label.setWordWrap(True)

        panel = QGroupBox('控制')
        pl = QVBoxLayout(panel)
        pl.addLayout(stat_row)
        pl.addWidget(self.shutter_label)
        pl.addWidget(QLabel('快门(对数滑条):'))
        pl.addWidget(self.slider)
        pl.addWidget(self.shutter_spin)
        pl.addLayout(step_row)
        pl.addWidget(self.gain_label)
        pl.addWidget(self.gain_slider)
        pl.addWidget(self.offset_label)
        pl.addWidget(self.offset_slider)
        pl.addWidget(QLabel('ROI 预设 / 自定义:'))
        pl.addLayout(preset_row)
        pl.addLayout(roi_row)
        pl.addWidget(self.snap_btn)
        pl.addWidget(self.hdr_btn)
        pl.addWidget(self.scan_btn)
        pl.addWidget(self.status_label)
        pl.addStretch(1)

        central = QWidget()
        root = QHBoxLayout(central)
        root.addWidget(self.image_label, 1)
        root.addWidget(panel, 0)
        self.setCentralWidget(central)
        self.resize(DISPLAY_W + 380, DISPLAY_H + 40)

        # 线程
        self.cam = CameraThread()
        self.cam.frame_ready.connect(self.on_frame)
        self.cam.temp_ready.connect(lambda t: self.temp_label.setText('温度: %s °C' % t))
        self.cam.shutter_result.connect(lambda r: self.status_label.setText('快门响应: %s' % r))
        self.cam.hdr_done.connect(self.on_hdr_done)
        self.cam.scan_update.connect(self.on_scan_update)
        self.cam.scan_done.connect(self.on_scan_done)
        self.cam.status.connect(lambda m: self.status_label.setText(m))
        self.cam.error.connect(lambda m: self.status_label.setText(m))
        self.cam.start()

        self.cam.set_shutter(slider_to_us(self.slider.value()))
        self.temp_timer = QTimer()
        self.temp_timer.timeout.connect(self.cam.get_temp)
        self.temp_timer.start(5000)
        self.cam.get_temp()

        self._frame_count = 0
        self._fps_t0 = time.time()
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)

        self.apply_shutter_ui(10000)
        self._busy = False

    # ---- 槽 ----
    def on_frame(self, arr):
        self._frame_count += 1
        arr = np.ascontiguousarray(arr)
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
        self.image_label.setPixmap(QPixmap.fromImage(qimg))

    def update_fps(self):
        now = time.time()
        dt = now - self._fps_t0
        fps = self._frame_count / dt if dt > 0 else 0.0
        self.fps_label.setText('帧率: %.1f fps' % fps)
        self._frame_count = 0
        self._fps_t0 = now

    def apply_shutter_ui(self, us):
        """更新滑条/输入框/标签(摄影格式), 并下发命令。"""
        us = max(SETTINGS.shutter_min_us, min(SETTINGS.shutter_max_us, int(us)))
        self.slider.blockSignals(True)
        self.slider.setValue(us_to_slider(us))
        self.slider.blockSignals(False)
        self.shutter_spin.blockSignals(True)
        self.shutter_spin.setValue(us)
        self.shutter_spin.blockSignals(False)
        self.shutter_label.setText('快门: %s (%d us)' % (format_shutter(us), us))
        self.cam.set_shutter(us)

    def on_slider_released(self):
        self.apply_shutter_ui(slider_to_us(self.slider.value()))

    def on_spin_changed(self):
        self.apply_shutter_ui(self.shutter_spin.value())

    def step_ev(self, ev):
        self.apply_shutter_ui(int(round(self.shutter_spin.value() * (2 ** ev))))

    def on_gain(self):
        v = self.gain_slider.value()
        self.gain_label.setText('增益: %d (%.1f dB)' % (v, v * 12.0 / SETTINGS.gain_max))
        self.cam.set_gain(v)

    def on_offset(self):
        v = self.offset_slider.value()
        self.offset_label.setText('补偿: %d' % v)
        self.cam.set_offset(v)

    def apply_preset(self, w, h):
        self.roi_w.blockSignals(True)
        self.roi_h.blockSignals(True)
        self.roi_w.setValue(min(w, W))
        self.roi_h.setValue(min(h, H))
        self.roi_w.blockSignals(False)
        self.roi_h.blockSignals(False)
        self.cam.set_roi(w, h)

    def on_snap(self):
        self.cam.request_save()
        self.status_label.setText('正在保存...')

    def on_hdr(self):
        if self._busy:
            return
        self._busy = True
        self.hdr_btn.setEnabled(False)
        self.cam.start_hdr()

    def on_scan(self):
        if self._busy:
            return
        self._busy = True
        self.scan_btn.setEnabled(False)
        self.cam.start_scan()

    def on_hdr_done(self, path):
        self._busy = False
        self.hdr_btn.setEnabled(True)
        self.status_label.setText('HDR 完成: %s' % path)
        viewer = ImageViewer(path, 'HDR 对比 (Debevec | Linear)')
        viewer.show()
        self._viewer = viewer

    def on_scan_update(self, arr, us):
        self.shutter_label.setText('扫描中: %s' % format_shutter(us))
        self.on_frame(arr)

    def on_scan_done(self, results, best_us, best_mean):
        self._busy = False
        self.scan_btn.setEnabled(True)
        self.apply_shutter_ui(best_us)
        lines = '  '.join('%s:%.0f' % (format_shutter(u), m) for u, m in results)
        self.status_label.setText('最佳快门 %s (均值 %.1f/%d) | %s' % (
            format_shutter(best_us), best_mean, int(SAT), lines))

    def closeEvent(self, event):
        self.cam.stop()
        self.cam.wait(5000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
