# -*- coding: utf-8 -*-
"""验证 Vieworks 相机 模拟处理/视图处理 串口命令。"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import time
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
    # 去掉回显和提示符
    t = raw.replace('\r', ' ').replace('\n', ' ').replace('>', '')
    return ' '.join(t.split())


ser = cl.SerialInit(0)
cl.SetBaudRate(ser, cl.CL_BAUDRATE_115200)

print('=== 读取当前值 (gxx) ===')
for cmd in ['giw', 'gih', 'gox', 'goy', 'gag', 'gao']:
    print('  %-6s -> %r' % (cmd, send(ser, cmd)))

print('\n=== 设置增益/补偿 (sag/sao) ===')
print('  sag 31 -> %r' % send(ser, 'sag 31'))
print('  sao 20 -> %r' % send(ser, 'sao 20'))

print('\n=== 设置 ROI (siw/sih, 16的倍数) ===')
print('  siw 4992 -> %r' % send(ser, 'siw 4992'))
print('  sih 4000 -> %r' % send(ser, 'sih 4000'))
print('  读回 giw -> %r' % send(ser, 'giw'))
print('  读回 gih -> %r' % send(ser, 'gih'))

print('\n=== 恢复全幅 ===')
print('  siw 10000 -> %r' % send(ser, 'siw 10000'))
print('  sih 7096 -> %r' % send(ser, 'sih 7096'))
print('  读回 giw -> %r' % send(ser, 'giw'))
print('  读回 gih -> %r' % send(ser, 'gih'))

cl.SerialClose(ser)
