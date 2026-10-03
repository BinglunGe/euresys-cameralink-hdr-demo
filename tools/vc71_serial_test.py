# -*- coding: utf-8 -*-
"""详细测试：每个波特率下发送 gct，显示响应原始字节(hex)"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import sys
import time
from MultiCam.clserial import clseremc as cl

BAUDS = [
    (9600,   cl.CL_BAUDRATE_9600),
    (19200,  cl.CL_BAUDRATE_19200),
    (38400,  cl.CL_BAUDRATE_38400),
    (57600,  cl.CL_BAUDRATE_57600),
    (115200, cl.CL_BAUDRATE_115200),
    (230400, cl.CL_BAUDRATE_230400),
    (460800, cl.CL_BAUDRATE_460800),
    (921600, cl.CL_BAUDRATE_921600),
]

def hexdump(b):
    return ' '.join('%02x' % x for x in b)

def try_baud(port_id, baud_val, baud_const, eol):
    try:
        ref = cl.SerialInit(port_id)
    except Exception as e:
        print("  SerialInit 失败:", e)
        return
    try:
        try:
            cl.SetBaudRate(ref, baud_const)
        except Exception as e:
            print("  [%d] SetBaudRate 不支持: %s" % (baud_val, e))
            return
        cl.FlushInputBuffer(ref)
        for cmd in ['gct', '>gct']:
            for e in eol:
                payload = (cmd + e).encode('latin-1')
                try:
                    cl.SerialWrite(ref, cmd + e, 500)
                except Exception as ex:
                    print("  [%d] write %r 失败: %s" % (baud_val, cmd + e, ex))
                    continue
                time.sleep(0.4)
                n = cl.GetNumBytesAvail(ref)
                if n > 0:
                    resp = cl.SerialRead(ref, n, 500).encode('latin-1')
                    print("  [%d] cmd=%r eol=%r -> %d 字节: %s" % (
                        baud_val, cmd, e, n, hexdump(resp)))
                else:
                    print("  [%d] cmd=%r eol=%r -> 无响应" % (baud_val, cmd, e))
    finally:
        cl.SerialClose(ref)

def main():
    num = cl.GetNumSerialPorts()
    print("串口数:", num)
    port_id = 0
    ref = cl.SerialInit(port_id)
    try:
        supported = cl.GetSupportedBaudRates(ref)
    finally:
        cl.SerialClose(ref)
    print("支持波特率掩码:", supported)
    for baud_val, baud_const in BAUDS:
        if supported & baud_const:
            print("[%d] 硬件支持，测试中..." % baud_val)
            try_baud(port_id, baud_val, baud_const, ['\r', '\n', '\r\n'])
        else:
            print("[%d] 硬件不支持" % baud_val)

if __name__ == '__main__':
    main()
