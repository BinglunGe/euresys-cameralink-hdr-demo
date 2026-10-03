# VC-71MC-M4 相机工具集

Euresys Grablink 采集卡 + VIEWORKS VC-71MC-M4（71MP Camera Link 黑白相机）的
Python 采集 / 串口控制 / HDR 合成 / 图形界面工具。

## 硬件

| 项目 | 型号 |
|---|---|
| 采集卡 | Euresys Grablink Full |
| 相机 | VIEWORKS VC-71MC-M4 (10000×7096, 12-bit, MEDIUM_4T12, 连接器 M) |
| 驱动 | Euresys MultiCam 6.19 |
| 串口 | Camera Link 串口 (clserial)，115200 baud，CRLF |

## 目录结构

```
python/
├── src/                       # 主程序
│   ├── vc71_camera.py         # 底层库: 配置加载 + 采集(MultiCam) + 串口(clserial) + 工具
│   ├── vc71_gui.py            # 图形界面 (PySide6)
│   ├── vc71_hdr.py            # HDR 合成 (Debevec / 线性加权) + 命令行
│   ├── vc71_snapshot.py       # 抓单帧 -> 16bit PNG + 8bit 预览
│   └── vc71_control.py        # 串口控制命令行
├── tools/                     # 诊断 / 探测 / 基准脚本
│   ├── probe_board.py         #   枚举采集卡
│   ├── probe_serial.py        #   枚举 Camera Link 串口
│   ├── probe_vc71.py          #   探测相机文件/尺寸
│   ├── vc71_api_probe.py      #   验证串口命令 (增益/补偿/ROI)
│   ├── vc71_roi_fps.py        #   ROI 帧率基准
│   └── ...
├── tests/
│   └── smoke_gui.py           # GUI 冒烟测试(自动跑一遍全功能)
├── samples/                   # Euresys 官方示例 (terminal / GrablinkSnapshot)
├── output/                    # 输出图像 (git 忽略)
├── settings.xml               # 全部配置 (路径/参数/命令/预设)
├── requirements.txt
└── .venv/                     # 相机专用虚拟环境 (git 忽略)
```

## 环境搭建

```cmd
cd /d <此目录>
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> **注意**：`MultiCam` 不是 PyPI 包，`requirements.txt` 里的那条需手动从
> `C:\Program Files (x86)\Euresys\MultiCam\Python\` 下的 `.whl` 安装。
> 安装该 wheel 需要系统已装 Euresys MultiCam 驱动（提供 `MultiCam.dll`）。
>
> **Hermes 环境注意**：如果在 Hermes shell 里操作，其 `PYTHONPATH` 会污染子 venv，
> 装包/运行请加前缀 `env -u PYTHONPATH`。

## 用法

所有脚本从 `src/` 目录运行（它们会自动到上级目录找 `settings.xml`）：

### 图形界面

```cmd
cd src
..\.venv\Scripts\python.exe vc71_gui.py
```

功能：实时预览、ROI 预设（提帧率）、快门（滑条+输入+±0.25档）、增益、补偿、
温度、帧率、抓单帧、HDR 合成、曝光扫描（自动最佳快门）。

> 运行前请退出 **MultiCamStudio** 及厂商客户端（它们独占 Camera Link 串口）。

### 命令行

```cmd
cd src
..\.venv\Scripts\python.exe vc71_snapshot.py --shutter 10000   # 抓单帧
..\.venv\Scripts\python.exe vc71_hdr.py                        # HDR 合成
..\.venv\Scripts\python.exe vc71_control.py --temp             # 读温度
..\.venv\Scripts\python.exe vc71_control.py --roi 2496 2000    # 设 ROI
..\.venv\Scripts\python.exe vc71_control.py --interactive      # 交互式串口终端
```

## 配置（settings.xml）

所有硬编码的路径与参数都在 `settings.xml`，改这一个文件即可适配其他相机/环境：

- `<sdk>` — MultiCam 安装路径、wheel 路径、相机文件目录
- `<camera>` — 相机文件、连接器、分辨率、位深、ROI 步进
- `<serial>` — 波特率、EOL
- `<ranges>` — 快门/增益/补偿范围
- `<commands>` — 串口命令模板（`{v}` 为参数占位）
- `<hdr>` / `<scan>` — 曝光序列、合成参数、最佳快门判据
- `<roi_presets>` — ROI 预设按钮

## 已知坑（重要）

1. **快门切换需一帧才生效**：`set` 新快门后，相机下一帧仍是**旧快门**曝光的。
   多曝光采集（HDR/扫描）里每档必须**丢弃首帧**，否则第一档读到上一档的残留。
2. **读 surface 后要释放**：`MC.SetParamStr(surface,'SurfaceState','FREE')`，
   否则下次 `ACTIVE` 可能复用到残留数据。
3. **相机端 ROI 需两步**：串口 `siw/sih` + MultiCam `Hactive_Px/Vactive_Ln` 同步设置。
   **不要把 ROI 值做 16 取整**——全幅高 7096 不是 16 的倍数，取整成 7088 会与
   MultiCam 不匹配导致采集全部超时。
4. **串口独占**：MultiCamStudio / 厂商客户端运行时串口被占用（`Port in use`）。
5. **OpenCV 5.0**：Debevec 输入要 8-bit；Tonemap 输入要 3 通道 float32；不写 `.exr`（用 `.hdr`）。
6. **Reinhard 对极端 HDR 会出 NaN**：显示改用稳健对数压缩（清洗 NaN + 百分位裁剪）。

## 串口命令速查

| 命令 | 作用 |
|---|---|
| `gct` | 读相机温度 (°C) |
| `set <us>` | 设快门（微秒，66 ~ 7000000） |
| `gag` / `sag <0-63>` | 读/设 增益（31=6dB, 63=12dB，线性） |
| `gao` / `sao <0-63>` | 读/设 补偿 |
| `giw` / `gih` | 读扫描宽/高 |
| `siw <n>` / `sih <n>` | 设扫描宽/高（相机端 ROI） |
| `gox` / `goy` | 读扫描偏移（该相机 `sox`/`soy` 不可用，ROI 恒从左上角） |

响应格式：读取 `命令 值`，设置 `命令 值 OK`；末尾的 `>` 是提示符，不是命令的一部分。
