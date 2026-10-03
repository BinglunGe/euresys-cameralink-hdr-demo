# -*- coding: utf-8 -*-
"""枚举 Camera Link 串口，用于识别相机"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import sys
from MultiCam.clserial import clseremc as cl

def main():
    try:
        num_ports = cl.GetNumSerialPorts()
    except Exception as e:
        print("GetNumSerialPorts 失败:", e)
        return
    if num_ports == 0:
        print("未检测到任何 Camera Link 串口 (可能相机未上电/未接串口/驱动未加载)")
        return
    print("检测到 %d 个串口:" % num_ports)
    for i in range(num_ports):
        try:
            port_name = cl.GetSerialPortIdentifier(i)
            print("  - Serial Index %d: %s" % (i, port_name))
        except Exception as e:
            print("  - Serial Index %d: <无法获取名称> %s" % (i, e))

if __name__ == '__main__':
    main()
