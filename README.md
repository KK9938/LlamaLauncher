# Llama 一键启动器

基于 Python + tkinter 的 llama.cpp 图形化启动器，支持一键启动 API 服务或终端对话。

## 功能

- 自动扫描并选择本地 GGUF 模型
- 快速预设：低显存 / 均衡 / 高性能
- 自定义 NGL、上下文长度、线程、端口、Host
- 启动后自动打开浏览器
- 深色 / 浅色双主题
- 圆角无边框窗口，支持标题栏拖动
- 最小化到系统托盘
- 运行日志与配置持久化

## 文件说明

| 文件 | 说明 |
|---|---|
| `LlamaLauncher.exe` | 可单独运行的文件启动器 |
| `llama_launcher.py` | 启动器源代码 |
| `launcher.ico` | 程序图标 |
| `build_exe.bat` | PyInstaller 打包脚本 |
| `llama_letter2.png` | 图标原图 |

## 运行要求

- Windows 10 / 11
- Python 3.10+
- 安装依赖：`pip install pystray pillow`

## 运行方式

```bash
python llama_launcher.py
```

## 打包为 exe

```bash
py -3 -m PyInstaller --onefile --windowed --name "LlamaLauncher" --icon "launcher.ico" --hidden-import pystray --hidden-import PIL --noconfirm llama_launcher.py
```

打包完成后，`dist/LlamaLauncher.exe` 即为可独立运行的启动器。

## 配置

首次运行会自动在程序目录生成 `config.json`，记录：

- `llama_server` / `llama_cli` 路径
- 模型文件夹路径
- 参数与主题偏好

## 使用提示

- 点击“定位 llama.cpp”选择 llama-server.exe / llama-cli.exe 所在目录。
- 点击“选择模型文件夹”可单独指定包含 `.gguf` 模型的目录。
- 模型列表会自动隐藏 `mmproj*` 视觉模型文件。
