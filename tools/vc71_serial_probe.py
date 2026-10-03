# -*- coding: utf-8 -*-
"""通过 Camera Link 串口与 VC-71MC-M4 通信：探测波特率 + 测试命令"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import sys
import time
from MultiCam.clserial import clseremc as cl

# 波特率常量映射（位掩码 -> 数值 -> 常量）
BAUDS = [
    (9600,   cl.CL_BAUDRATE_9600),
    (19200,  cl.CL_BAUDRATE_19200),
    (38400,  cl.CL_BAUDRATE_38400),
    (57600,  cl.CL_BAUDRATE_57600),
    (115200, cl.CL_BAUDRATE_115200),
    (230400, cl.CL_BAUDRATE_230400),
]

def read_response(serial_ref, wait_ms=500):
    """读取串口当前可用字节并返回字符串"""
    time.sleep(wait_ms / 1000.0)
    n = cl.GetNumBytesAvail(serial_ref)
    if n <= 0:
        return ''
    return cl.SerialRead(serial_ref, n, 1000)

def test_baud(port_id, baud_val, baud_const, cmd='gct'):
    """尝试某个波特率，发送 gct 命令看响应"""
    try:
        ref = cl.SerialInit(port_id)
    except Exception as e:
        print("  串口初始化失败:", e)
        return None
    try:
        try:
            cl.SetBaudRate(ref, baud_const)
        except Exception:
            pass  # 不支持则跳过
        cl.FlushInputBuffer(ref)
        # 分别尝试带 > 前缀和不带前缀，EOL 用 CR
        for cmdtext in ['>' + cmd, cmd]:
            try:
                cl.SerialWrite(ref, cmdtext + '\r', 1000)
            except Exception as e:
                print("    [%d] 写 '%s' 失败: %s" % (baud_val, cmdtext, e))
                continue
            resp = read_response(ref, 500)
            print("    [%d] 发送 '%s' -> 响应: %r" % (baud_val, cmdtext, resp))
            if resp.strip():
                return resp
        return None
    finally:
        cl.SerialClose(ref)

def main():
    num = cl.GetNumSerialPorts()
    if num == 0:
        print("无串口")
        return
    for i in range(num):
        print("串口 %d: %s" % (i, cl.GetSerialPortIdentifier(i)))
    port_id = 0
    # 枚举支持波特率
    ref = cl.SerialInit(port_id)
    try:
        supported = cl.GetSupportedBaudRates(ref)
    finally:
        cl.SerialClose(ref)
    print("硬件支持波特率位掩码: %d" % supported)
    for baud_val, baud_const in BAUDS:
        if supported & baud_const:
            print("[%d] 支持" % baud_val)
            test_baud(port_id, baud_val, baud_const)
        else:
            print("[%d] 不支持" % baud_val)

if __name__ == '__main__':
    main()
