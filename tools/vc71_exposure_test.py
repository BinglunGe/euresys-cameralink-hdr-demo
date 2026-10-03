# -*- coding: utf-8 -*-
"""曝光验证：设置不同快门时间，抓图并对比平均亮度。

流程: 串口设快门 -> MultiCam 抓一帧 -> numpy 算平均亮度 -> 对比。
"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import sys
import time
import numpy as np
from MultiCam import MC
from MultiCam.clserial import clseremc as cl


def set_shutter(us):
    """通过串口设置快门，返回响应。"""
    ref = cl.SerialInit(0)
    try:
        cl.SetBaudRate(ref, cl.CL_BAUDRATE_115200)
        cl.FlushInputBuffer(ref)
        cl.SerialWrite(ref, 'set %d\r\n' % us, 500)
        time.sleep(0.3)
        raw = ''
        deadline = time.time() + 1.5
        while time.time() < deadline:
            n = cl.GetNumBytesAvail(ref)
            if n > 0:
                raw += cl.SerialRead(ref, n, 200)
                if raw.rstrip().endswith('>'):
                    break
            else:
                time.sleep(0.02)
        return raw.replace('\r', '').replace('\n', '').replace('>', '').strip()
    finally:
        cl.SerialClose(ref)


def grab_mean():
    """抓一帧，返回平均亮度(12bit)。"""
    MC.OpenDriver()
    channel = MC.Create('CHANNEL')
    try:
        MC.SetParamInt(channel, 'DriverIndex', 0)
        MC.SetParamStr(channel, 'Connector', 'M')
        MC.SetParamStr(channel, 'CamFile', 'VC-71MC-M4_P4SC')
        MC.SetParamInt(channel, 'SeqLength_Fr', 1)
        MC.SetParamStr(channel, MC.SignalEnable + MC.SIG_SURFACE_PROCESSING, 'ON')
        MC.SetParamStr(channel, MC.SignalEnable + MC.SIG_ACQUISITION_FAILURE, 'ON')
        MC.SetParamStr(channel, MC.SignalEnable + MC.SIG_END_CHANNEL_ACTIVITY, 'ON')
        MC.SetParamStr(channel, 'ChannelState', 'ACTIVE')
        # 等待采集结束
        import ctypes
        while True:
            si = MC.WaitSignal(channel, MC.SIG_ANY, 30000)
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
        buf = ctypes.string_at(addr, size)
        arr = np.frombuffer(buf, dtype='<u2')[:w * h]
        return float(arr.mean())
    finally:
        MC.Delete(channel)
        MC.CloseDriver()


def main():
    tests = [1000, 5000, 10000, 50000]  # 快门(微秒)
    print("快门(us) | 响应 | 平均亮度(12bit)")
    print("-" * 40)
    for us in tests:
        resp = set_shutter(us)
        mean = grab_mean()
        print("%8d | %-4s | %.1f" % (us, resp, mean))
        time.sleep(0.5)


if __name__ == '__main__':
    main()
