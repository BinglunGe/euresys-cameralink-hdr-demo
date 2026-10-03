# -*- coding: utf-8 -*-
"""公平帧率测试: 固定快门, 对比不同 ROI 尺寸的帧率。"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import time
import ctypes
import numpy as np
from MultiCam import MC
from MultiCam.clserial import clseremc as cl


def send(ser, cmd, wait=0.3):
    cl.FlushInputBuffer(ser)
    cl.SerialWrite(ser, cmd + '\r\n', 500)
    time.sleep(wait)
    deadline = time.time() + 1.5
    while time.time() < deadline:
        if cl.GetNumBytesAvail(ser) > 0:
            b = cl.SerialRead(ser, cl.GetNumBytesAvail(ser), 200)
            if b.rstrip().endswith('>'):
                break
        else:
            time.sleep(0.02)


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
    f = np.frombuffer(ctypes.string_at(a, sz), dtype='<u2')[:w * h].reshape((h, w)).copy()
    MC.SetParamStr(s, 'SurfaceState', 'FREE')
    return f


def fps(ch, ser, w, h, n=3):
    send(ser, 'siw %d' % w); send(ser, 'sih %d' % h)
    MC.SetParamInt(ch, 'Hactive_Px', w); MC.SetParamInt(ch, 'Vactive_Ln', h)
    grab(ch)   # warm-up
    ts = []
    for _ in range(n):
        t0 = time.time(); f = grab(ch); ts.append(time.time() - t0)
    return sum(ts) / n, f.shape


ser = cl.SerialInit(0); cl.SetBaudRate(ser, cl.CL_BAUDRATE_115200)
MC.OpenDriver(); ch = MC.Create('CHANNEL'); configure(ch)

send(ser, 'set 1000')        # 固定快门 1ms
send(ser, 'sag 0')           # 增益归零
grab(ch)                     # 丢弃

print('快门固定 1ms, 不同 ROI 尺寸的帧率:')
for (w, h) in [(10000, 7096), (4992, 4000), (2496, 2000), (1248, 1024), (624, 512)]:
    dt, shape = fps(ch, ser, w, h)
    print('  %5dx%-4d -> %.3fs/帧 = %.2f fps  (实际 %dx%d)' % (
        w, h, dt, 1 / dt, shape[1], shape[0]))

# 恢复
send(ser, 'siw 10000'); send(ser, 'sih 7096')
MC.SetParamInt(ch, 'Hactive_Px', 10000); MC.SetParamInt(ch, 'Vactive_Ln', 7096)
MC.Delete(ch); MC.CloseDriver(); cl.SerialClose(ser)
