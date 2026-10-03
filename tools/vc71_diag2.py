# -*- coding: utf-8 -*-
"""诊断: 读当前状态 + 抓帧计时 + ROI 切换后抓帧。"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import time
import ctypes
import numpy as np
from MultiCam import MC
from MultiCam.clserial import clseremc as cl
from vc71_camera import configure_channel, grab_frame


def send(cmd, wait=0.3):
    cl.FlushInputBuffer(ser)
    cl.SerialWrite(ser, cmd + '\r\n', 500)
    time.sleep(wait)
    raw = ''
    dl = time.time() + 1.5
    while time.time() < dl:
        n = cl.GetNumBytesAvail(ser)
        if n > 0:
            raw += cl.SerialRead(ser, n, 200)
            if raw.rstrip().endswith('>'):
                break
        else:
            time.sleep(0.02)
    t = raw.replace('\r', '').replace('\n', '').replace('>', '')
    return t.strip()


ser = cl.SerialInit(0)
cl.SetBaudRate(ser, cl.CL_BAUDRATE_115200)

print('=== 当前状态 ===')
for c in ['giw', 'gih', 'gag', 'gao']:
    print('  %s -> %r' % (c, send(c)))

MC.OpenDriver()
ch = MC.Create('CHANNEL')
configure_channel(ch)

print('\n设快门 10ms, 抓 3 帧:')
send('set 10000')
for i in range(3):
    t0 = time.time()
    try:
        f = grab_frame(ch, 8000)
        print('  帧%d: %.2fs  %dx%d' % (i, time.time() - t0, f.shape[1], f.shape[0]))
    except Exception as e:
        print('  帧%d: 失败 %s' % (i, str(e)[:60]))

print('\n设 ROI 2496x2000, 抓 3 帧:')
send('siw 2496'); send('sih 2000')
MC.SetParamInt(ch, 'Hactive_Px', 2496)
MC.SetParamInt(ch, 'Vactive_Ln', 2000)
for i in range(3):
    t0 = time.time()
    try:
        f = grab_frame(ch, 8000)
        print('  帧%d: %.2fs  %dx%d' % (i, time.time() - t0, f.shape[1], f.shape[0]))
    except Exception as e:
        print('  帧%d: 失败 %s' % (i, str(e)[:60]))

print('\n恢复全幅')
send('siw 10000'); send('sih 7096')
MC.SetParamInt(ch, 'Hactive_Px', 10000)
MC.SetParamInt(ch, 'Vactive_Ln', 7096)
MC.Delete(ch)
MC.CloseDriver()
cl.SerialClose(ser)
