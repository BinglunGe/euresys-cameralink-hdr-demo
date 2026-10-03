# -*- coding: utf-8 -*-
"""用正确的相机文件 VC-71MC-M4 探测 + 抓图"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import ctypes
import os
import sys
import time
from MultiCam import MC

def probe_cam(camfile):
    MC.OpenDriver()
    channel = MC.Create('CHANNEL')
    try:
        MC.SetParamInt(channel, 'DriverIndex', 0)
        MC.SetParamStr(channel, 'Connector', 'M')
        MC.SetParamStr(channel, 'CamFile', camfile)
        print("=== 相机文件: %s ===" % camfile)
        for p in ['Connector', 'CamFile', 'ColorFormat', 'TapConfiguration', 'TapGeometry']:
            try:
                print("  %s = %s" % (p, MC.GetParamStr(channel, p)))
            except Exception as e:
                print("  %s 查询失败: %s" % (p, e))
        try:
            MC.SetParamStr(channel, 'ChannelState', 'ACTIVE')
            print("  ChannelState = ACTIVE 成功")
        except Exception as e:
            print("  ChannelState ACTIVE 失败:", e)
            return
        try:
            w = MC.GetParamInt(channel, 'ImageSizeX')
            h = MC.GetParamInt(channel, 'ImageSizeY')
            print("  ImageSize = %d x %d" % (w, h))
        except Exception as e:
            print("  ImageSize 查询失败:", e)
        try:
            MC.SetParamStr(channel, 'ChannelState', 'IDLE')
        except Exception:
            pass
    finally:
        MC.Delete(channel)
        MC.CloseDriver()

if __name__ == '__main__':
    for cf in ['VC-71MC-M4_P4SC', 'VC-71MC-M4_P4RG']:
        probe_cam(cf)
        print()
