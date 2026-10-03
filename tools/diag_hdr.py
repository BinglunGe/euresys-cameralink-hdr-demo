# -*- coding: utf-8 -*-
"""诊断 HDR 合成各步的数值范围, 定位"亮度溢出"。"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import time
import ctypes
import numpy as np
import cv2
from MultiCam import MC
from MultiCam.clserial import clseremc as cl
from vc71_hdr import (merge_debevec, merge_linear, tonemap, log_compress,
                      W, H, CAMFILE, CONNECTOR)

SHUTTERS = [100, 1000, 10000, 100000, 1000000]
SCALE = 0.25


def grab(channel):
    MC.SetParamStr(channel, 'ChannelState', 'ACTIVE')
    while True:
        si = MC.WaitSignal(channel, MC.SIG_ANY, 5000)
        if si.Signal == MC.SIG_END_CHANNEL_ACTIVITY:
            break
        if si.Signal == MC.SIG_SURFACE_PROCESSING:
            MC.SetParamStr(si.SignalInfo, 'SurfaceState', 'FREE')
    s = MC.GetParamInst(channel, 'Cluster:0')
    w = MC.GetParamInt(s, 'SurfaceSizeX'); h = MC.GetParamInt(s, 'SurfaceSizeY')
    a = MC.GetParamPtr(s, 'SurfaceAddr:0'); sz = MC.GetParamInt(s, 'SurfaceSize:0')
    return np.frombuffer(ctypes.string_at(a, sz), dtype='<u2')[:w * h].reshape((h, w))


def setsh(ser, us):
    cl.FlushInputBuffer(ser)
    cl.SerialWrite(ser, 'set %d\r\n' % us, 500)
    time.sleep(0.25)
    while cl.GetNumBytesAvail(ser) > 0:
        cl.SerialRead(ser, cl.GetNumBytesAvail(ser), 200)


ser = cl.SerialInit(0); cl.SetBaudRate(ser, cl.CL_BAUDRATE_115200)
MC.OpenDriver()
ch = MC.Create('CHANNEL')
MC.SetParamInt(ch, 'DriverIndex', 0); MC.SetParamStr(ch, 'Connector', CONNECTOR)
MC.SetParamStr(ch, 'CamFile', CAMFILE); MC.SetParamInt(ch, 'SeqLength_Fr', 1)
MC.SetParamStr(ch, MC.SignalEnable + MC.SIG_END_CHANNEL_ACTIVITY, 'ON')
MC.SetParamStr(ch, MC.SignalEnable + MC.SIG_SURFACE_PROCESSING, 'ON')

dw, dh = int(W * SCALE), int(H * SCALE)
imgs12, imgs8, times = [], [], []
for us in SHUTTERS:
    setsh(ser, us)
    fr = grab(ch)
    f = cv2.resize(fr, (dw, dh), interpolation=cv2.INTER_AREA)
    imgs12.append(f); imgs8.append((f >> 4).astype(np.uint8)); times.append(us / 1e6)
    print('快门 %7d us: 原始均值 %.1f, 降采样后 max %d' % (us, fr.mean(), f.max()))

MC.Delete(ch); MC.CloseDriver(); cl.SerialClose(ser)

print('\n--- 合成检查 ---')
hdr, resp = merge_debevec(imgs8, times)
print('hdr(Debevec): min %.4f max %.4f  nan=%d inf=%d' % (
    hdr.min(), hdr.max(), np.isnan(hdr).sum(), np.isinf(hdr).sum()))

ldr_d = log_compress(hdr)
print('ldr_d(稳健log): min %.4f max %.4f  >1=%d <0=%d nan=%d' % (
    ldr_d.min(), ldr_d.max(), (ldr_d > 1).sum(), (ldr_d < 0).sum(),
    np.isnan(ldr_d).sum()))

E = merge_linear(imgs12, times)
print('E(linear): min %.2f max %.2f  nan=%d inf=%d' % (
    E.min(), E.max(), np.isnan(E).sum(), np.isinf(E).sum()))

ldr_l = log_compress(E)
print('ldr_l(log): min %.4f max %.4f  >1=%d <0=%d nan=%d' % (
    ldr_l.min(), ldr_l.max(), (ldr_l > 1).sum(), (ldr_l < 0).sum(),
    np.isnan(ldr_l).sum()))

d8 = (ldr_d * 255).astype(np.uint8)
l8 = (ldr_l * 255).astype(np.uint8)
print('\nd8(显示): 黑0值像素 %d, 白255值像素 %d, 总 %d' % (
    (d8 == 0).sum(), (d8 == 255).sum(), d8.size))
print('l8(显示): 黑0值像素 %d, 白255值像素 %d' % ((l8 == 0).sum(), (l8 == 255).sum()))
