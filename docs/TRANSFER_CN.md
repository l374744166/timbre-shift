# Timbre Shift 换电脑运行说明

## 最简单流程

1. 把 `timbre-shift-portable-*.zip` 拷到另一台 Mac。
2. 解压后进入 `timbre-shift` 文件夹。
3. 第一次运行双击 `setup_mac.command`，它会安装 ffmpeg、Python 环境和项目依赖。
4. 以后运行双击 `start.command`，页面会自动打开到 `http://127.0.0.1:8765/`。

## 另一台电脑需要什么

- macOS，最好是 Apple Silicon 芯片。
- Homebrew。
- 网络可以访问 Python 包和模型下载地址。
- 足够硬盘空间。项目包会带 Seed-VC 和模型，解压后仍然建议预留 8GB 以上。

## 两个 command 文件是干什么的

- `setup_mac.command`：第一次配置环境用，只需要跑一次。
- `start.command`：平时启动页面用，每次想打开项目就双击它。

## 如果 start.command 提示环境缺失

先重新运行 `setup_mac.command`。如果还是失败，把终端里最后几行错误复制出来再排查。

## 生成速度提醒

`M2整首快速` 会先检测有效人声，只转换有人声的片段，通常比原始整首高质量模式快很多。实际速度取决于歌曲里唱声占比、电脑芯片、模型是否已下载完成。
