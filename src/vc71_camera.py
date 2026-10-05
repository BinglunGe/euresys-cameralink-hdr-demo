# -*- coding: utf-8 -*-
"""VC-71MC-M4 相机底层库

集中提供: 配置加载(settings.xml) + 采集(MultiCam) + 串口(clserial) + 工具函数。
所有硬编码的路径/参数都移到 ../settings.xml，本模块只负责读取与封装。
"""
import os
import math
import time
import ctypes
import xml.etree.ElementTree as ET

import numpy as np
from MultiCam import MC
from MultiCam.clserial import clseremc as cl


# ---------------- 配置加载 ----------------
def _find_settings():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, '..', 'settings.xml'),
              os.path.join(here, 'settings.xml')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('settings.xml 未找到')


def _txt(parent, tag, default=None):
    el = parent.find(tag) if parent is not None else None
    return el.text.strip() if (el is not None and el.text) else default


def _int(parent, tag, default=0):
    try:
        return int(_txt(parent, tag, default))
    except (TypeError, ValueError):
        return int(default)


def _flt(parent, tag, default=0.0):
    try:
        return float(_txt(parent, tag, default))
    except (TypeError, ValueError):
        return float(default)


def _ints(parent, tag):
    v = _txt(parent, tag, '') or ''
    return [int(x) for x in v.split(',') if x.strip()]


def ev_bracket(start_us, stop_us, step_ev):
    """按 EV 步进生成曝光序列: us *= 2**step_ev, 直到超过 stop_us。

    step_ev=2 → 每档 4×; step_ev=1 → 每档 2×。
    """
    seq, us, stop = [], float(start_us), float(stop_us)
    while us <= stop * 1.0001 and len(seq) < 64:
        seq.append(int(round(us)))
        us *= 2.0 ** step_ev
    return seq or [int(start_us)]


class Settings:
    """从 settings.xml 读取全部配置。"""

    def __init__(self, path=None):
        self.path = path or _find_settings()
        root = ET.parse(self.path).getroot()
        sdk, cam = root.find('sdk'), root.find('camera')
        grb = root.find('grabber')
        ser, rng = root.find('serial'), root.find('ranges')
        cmd, hdr = root.find('commands'), root.find('hdr')
        scan, prev = root.find('scan'), root.find('preview')

        # SDK
        self.multicam_install = _txt(sdk, 'multicam_install', '')
        self.multicam_wheel = _txt(sdk, 'multicam_wheel', '')
        self.cameras_dir = _txt(sdk, 'cameras_dir', '')
        # 相机
        self.model = _txt(cam, 'model', 'camera')
        self.camfile = _txt(cam, 'camfile', '')
        self.connector = _txt(cam, 'connector', 'M')
        self.driver_index = _int(cam, 'driver_index', 0)
        self.width = _int(cam, 'width', 10000)
        self.height = _int(cam, 'height', 7096)
        self.bit_depth = _int(cam, 'bit_depth', 12)
        self.roi_step = _int(cam, 'roi_step', 16)
        # 采集卡
        self.acq_timeout_ms = _int(grb, 'acq_timeout_ms', 10000)
        # 串口
        self.baud = _int(ser, 'baud', 115200)
        self.eol = _txt(ser, 'eol', r'\r\n').replace('\\r', '\r').replace('\\n', '\n')
        # 范围
        self.shutter_min_us = _int(rng, 'shutter_min_us', 66)
        self.shutter_max_us = _int(rng, 'shutter_max_us', 7000000)
        self.gain_max = _int(rng, 'gain_max', 63)
        self.offset_max = _int(rng, 'offset_max', 63)
        # 命令模板
        self.cmd_temp = _txt(cmd, 'temp', 'gct')
        self.cmd_shutter = _txt(cmd, 'shutter', 'set {v}')
        self.cmd_gain = _txt(cmd, 'gain', 'sag {v}')
        self.cmd_offset = _txt(cmd, 'offset', 'sao {v}')
        self.cmd_get_gain = _txt(cmd, 'get_gain', 'gag')
        self.cmd_get_offset = _txt(cmd, 'get_offset', 'gao')
        self.cmd_roi_w = _txt(cmd, 'roi_width', 'siw {v}')
        self.cmd_roi_h = _txt(cmd, 'roi_height', 'sih {v}')
        self.cmd_get_w = _txt(cmd, 'get_width', 'giw')
        self.cmd_get_h = _txt(cmd, 'get_height', 'gih')
        # HDR / 扫描
        self.hdr_step_ev = _flt(hdr, 'step_ev', 2.0)
        self.hdr_shutters = _ints(hdr, 'shutters') or ev_bracket(
            _int(hdr, 'start_us', 100), _int(hdr, 'stop_us', 1000000), self.hdr_step_ev)
        self.hdr_scale = _flt(hdr, 'scale', 0.25)
        self.hdr_skip_lo = _flt(hdr, 'skip_mean_below', 2)
        self.hdr_skip_hi = _flt(hdr, 'skip_mean_above', 4090)
        self.scan_shutters = _ints(scan, 'shutters') or [100, 1000, 10000, 100000, 1000000]
        self.scan_target = _flt(scan, 'target_fraction', 0.5)
        # 预览
        self.display_w = _int(prev, 'display_width', 1250)
        self.display_h = _int(prev, 'display_height', 887)
        # ROI 预设
        self.roi_presets = []
        rp = root.find('roi_presets')
        if rp is not None:
            for p in rp.findall('preset'):
                try:
                    w, h = p.text.strip().split(',')
                    self.roi_presets.append((p.get('name'), int(w), int(h)))
                except (ValueError, AttributeError):
                    pass

    @property
    def sat(self):
        return float(2 ** self.bit_depth - 1)


SETTINGS = Settings()
W, H = SETTINGS.width, SETTINGS.height     # 便捷别名
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, 'output')      # 默认输出目录


# ---------------- 采集 (MultiCam) ----------------
def configure_channel(channel, hactive=None, vactive=None):
    s = SETTINGS
    MC.SetParamInt(channel, 'DriverIndex', s.driver_index)
    MC.SetParamStr(channel, 'Connector', s.connector)
    MC.SetParamStr(channel, 'CamFile', s.camfile)
    MC.SetParamInt(channel, 'SeqLength_Fr', 1)
    # 采集超时(ms): 字符串标识符是 'Timeout' (≠ 参数名 AcqTimeout_ms), 须在 ACTIVE 前设置
    MC.SetParamInt(channel, 'Timeout', s.acq_timeout_ms)
    MC.SetParamInt(channel, 'Hactive_Px', hactive or s.width)
    MC.SetParamInt(channel, 'Vactive_Ln', vactive or s.height)
    MC.SetParamStr(channel, MC.SignalEnable + MC.SIG_SURFACE_PROCESSING, 'ON')
    MC.SetParamStr(channel, MC.SignalEnable + MC.SIG_ACQUISITION_FAILURE, 'ON')
    MC.SetParamStr(channel, MC.SignalEnable + MC.SIG_END_CHANNEL_ACTIVITY, 'ON')


def grab_frame(channel, timeout_ms=8000):
    """抓一帧, 返回 uint16 (H,W)。超时抛异常。"""
    MC.SetParamStr(channel, 'ChannelState', 'ACTIVE')
    while True:
        si = MC.WaitSignal(channel, MC.SIG_ANY, timeout_ms)
        if si.Signal == MC.SIG_END_CHANNEL_ACTIVITY:
            break
        if si.Signal == MC.SIG_ACQUISITION_FAILURE:
            raise RuntimeError('采集失败')
        if si.Signal == MC.SIG_SURFACE_PROCESSING:
            MC.SetParamStr(si.SignalInfo, 'SurfaceState', 'FREE')
    surface = MC.GetParamInst(channel, 'Cluster:0')
    w = MC.GetParamInt(surface, 'SurfaceSizeX')
    h = MC.GetParamInt(surface, 'SurfaceSizeY')
    addr = MC.GetParamPtr(surface, 'SurfaceAddr:0')
    size = MC.GetParamInt(surface, 'SurfaceSize:0')
    out = np.frombuffer(ctypes.string_at(addr, size),
                        dtype='<u2')[:w * h].reshape((h, w)).copy()
    MC.SetParamStr(surface, 'SurfaceState', 'FREE')   # 释放 surface
    return out


# ---------------- 串口 (clserial) ----------------
_BAUD_MAP = {'9600': cl.CL_BAUDRATE_9600, '19200': cl.CL_BAUDRATE_19200,
             '38400': cl.CL_BAUDRATE_38400, '57600': cl.CL_BAUDRATE_57600,
             '115200': cl.CL_BAUDRATE_115200, '230400': cl.CL_BAUDRATE_230400,
             '460800': cl.CL_BAUDRATE_460800, '921600': cl.CL_BAUDRATE_921600}


class CameraSerial:
    """Camera Link 串口封装。打开前须确保 MultiCamStudio / 厂商客户端已退出。"""

    def __init__(self, index=0):
        self.index = index
        self.ref = None
        self.eol = SETTINGS.eol

    def open(self):
        self.ref = cl.SerialInit(self.index)
        cl.SetBaudRate(self.ref, _BAUD_MAP[str(SETTINGS.baud)])
        return self

    def send(self, cmd, wait=0.2, timeout_s=1.5):
        """发命令, 返回去掉回显命令与提示符 '>' 后的响应。"""
        cl.FlushInputBuffer(self.ref)
        cl.SerialWrite(self.ref, cmd + self.eol, 500)
        time.sleep(wait)
        raw = ''
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            n = cl.GetNumBytesAvail(self.ref)
            if n > 0:
                raw += cl.SerialRead(self.ref, n, 200)
                if raw.rstrip().endswith('>'):
                    break
            else:
                time.sleep(0.02)
        text = raw.replace('\r', '').replace('\n', '').replace('>', '')
        if text.startswith(cmd):
            text = text[len(cmd):]
        return text.strip()

    def get_temp(self):
        return self.send(SETTINGS.cmd_temp, wait=0.3)

    def set_shutter(self, us):
        return self.send(SETTINGS.cmd_shutter.format(v=int(us)))

    def set_gain(self, v):
        return self.send(SETTINGS.cmd_gain.format(v=int(v)))

    def set_offset(self, v):
        return self.send(SETTINGS.cmd_offset.format(v=int(v)))

    def get_gain(self):
        return self.send(SETTINGS.cmd_get_gain)

    def get_offset(self):
        return self.send(SETTINGS.cmd_get_offset)

    def set_roi(self, w, h):
        return (self.send(SETTINGS.cmd_roi_w.format(v=int(w))),
                self.send(SETTINGS.cmd_roi_h.format(v=int(h))))

    def get_roi(self):
        return self.send(SETTINGS.cmd_get_w), self.send(SETTINGS.cmd_get_h)

    def close(self):
        if self.ref:
            cl.SerialClose(self.ref)
            self.ref = None


# ---------------- 工具 ----------------
_COMMON_DENOMS = [1, 2, 3, 4, 5, 6, 8, 10, 13, 15, 20, 25, 30, 40, 50, 60, 80,
                  100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250,
                  1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000]


def format_shutter(us):
    """快门(微秒) -> 摄影常用格式: 1/1000s, 1/2s, 2s, 10s。"""
    if us >= 1_000_000:
        s = us / 1_000_000.0
        return '%ds' % int(s) if s == int(s) else '%gs' % round(s, 2)
    denom = 1_000_000.0 / us
    if abs(denom - round(denom)) < 1e-6:
        return '1/%ds' % int(round(denom))
    nearest = min(_COMMON_DENOMS, key=lambda c: abs(c - denom))
    return '1/%ds' % nearest


def slider_to_us(v, slider_range=1000):
    lo = math.log10(SETTINGS.shutter_min_us)
    hi = math.log10(SETTINGS.shutter_max_us)
    return int(round(10 ** (lo + (hi - lo) * v / slider_range)))


def us_to_slider(us, slider_range=1000):
    us = max(SETTINGS.shutter_min_us, min(SETTINGS.shutter_max_us, us))
    lo = math.log10(SETTINGS.shutter_min_us)
    hi = math.log10(SETTINGS.shutter_max_us)
    return int(round((math.log10(us) - lo) / (hi - lo) * slider_range))
