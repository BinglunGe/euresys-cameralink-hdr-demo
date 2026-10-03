# -*- coding: utf-8 -*-
"""测试相机端 ROI (siw/sih) 是否生效 + 是否提升帧率。"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import time
import ctypes
import numpy as np
from MultiCam import MC
from MultiCam.clserial import clseremc as cl


def send(ser, cmd, wait=0.35):
    cl.FlushInputBuffer(ser)
    cl.SerialWrite(ser, cmd + '\r\n', 500)
    time.sleep(wait)
    raw = ''
    deadline = time.time() + 1.5
    while time.time() < deadline:
        n = cl.GetNumBytesAvail(ser)
        if n > 0:
            raw += cl.SerialRead(ser, n, 200)
            if raw.rstrip().endswith('>'):
                break
        else:
            time.sleep(0.02)
    t = raw.replace('\r', ' ').replace('\n', ' ').replace('>', '')
    return ' '.join(t.split())


def configure(ch):
    MC.SetParamInt(ch, 'DriverIndex', 0)
    MC.SetParamStr(ch, 'Connector', 'M')
    MC.SetParamStr(ch, 'CamFile', 'VC-71MC-M4_P4SC')
    MC.SetParamInt(ch, 'SeqLength_Fr', 1)
    MC.SetParamStr(ch, MC.SignalEnable + MC.SIG_END_CHANNEL_ACTIVITY, 'ON')
    MC.SetParamStr(ch, MC.SignalEnable + MC.SIG_SURFACE_PROCESSING, 'ON')


def grab(ch, timeout=8000):
    MC.SetParamStr(ch, 'ChannelState', 'ACTIVE')
    while True:
        si = MC.WaitSignal(ch, MC.SIG_ANY, timeout)
        if si.Signal == MC.SIG_END_CHANNEL_ACTIVITY:
            break
        if si.Signal == MC.SIG_SURFACE_PROCESSING:
            MC.SetParamStr(si.SignalInfo, 'SurfaceState', 'FREE')
    s = MC.GetParamInst(ch, 'Cluster:0')
    w = MC.GetParamInt(s, 'SurfaceSizeX'); h = MC.GetParamInt(s, 'SurfaceSizeY')
    a = MC.GetParamPtr(s, 'SurfaceAddr:0'); sz = MC.GetParamInt(s, 'SurfaceSize:0')
    return np.frombuffer(ctypes.string_at(a, sz), dtype='<u2')[:w * h].reshape((h, w)).copy()


ser = cl.SerialInit(0); cl.SetBaudRate(ser, cl.CL_BAUDRATE_115200)
MC.OpenDriver()
ch = MC.Create('CHANNEL')
configure(ch)

print('=== MultiCam 尺寸参数探测 ===')
for p in ['ImageSizeX', 'ImageSizeY', 'Hactive_Px', 'Vactive_Ln', 'GrabWindow']:
    try:
        print('  %s = %s' % (p, MC.GetParamStr(ch, p)))
    except Exception as e:
        print('  %s -> %s' % (p, str(e)[:50]))

# 全幅基线
send(ser, 'siw 10000'); send(ser, 'sih 7096')
t0 = time.time(); grab(ch); dt_full = time.time() - t0
print('\n全幅 10000x7096: 单帧耗时 %.2fs (%.2f fps)' % (dt_full, 1/dt_full))

# 设 ROI
print('\n设 ROI 4992x4000 ...')
print('  ', send(ser, 'siw 4992'), '|', send(ser, 'sih 4000'))
try:
    MC.SetParamInt(ch, 'Hactive_Px', 4992)
    MC.SetParamInt(ch, 'Vactive_Ln', 4000)
    print('  已设 MultiCam Hactive_Px/Vactive_Ln')
except Exception as e:
    print('  设 MultiCam 尺寸失败:', str(e)[:80])
try:
    t0 = time.time(); f = grab(ch); dt_roi = time.time() - t0
    print('  ROI 采集: 尺寸 %dx%d, 单帧耗时 %.2fs (%.2f fps)' % (
        f.shape[1], f.shape[0], dt_roi, 1/dt_roi))
    print('  均值 %.1f' % f.mean())
except Exception as e:
    print('  ROI 采集失败:', str(e)[:120])

# 恢复
send(ser, 'siw 10000'); send(ser, 'sih 7096')
try:
    MC.SetParamInt(ch, 'Hactive_Px', 10000); MC.SetParamInt(ch, 'Vactive_Ln', 7096)
except Exception:
    pass
print('\n已恢复全幅')

MC.Delete(ch); MC.CloseDriver(); cl.SerialClose(ser)
