# Piper TTS 接入说明

当前文字朗读功能优先使用本地 Piper 中文模型：

```text
models/piper/zh_CN-huayan-medium.onnx
models/piper/zh_CN-huayan-medium.onnx.json
```

如果模型不存在，会自动退回 macOS 系统 `say` 作为保底 TTS。

## 安装依赖

```bash
.venv/bin/pip install piper-tts
```

## 下载中文模型

```bash
mkdir -p models/piper
curl -L -o models/piper/zh_CN-huayan-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx
curl -L -o models/piper/zh_CN-huayan-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json
```

模型文件较大，已被 `.gitignore` 忽略，不提交到 GitHub。

## 自定义模型

也可以通过环境变量指定模型：

```bash
TIMBRE_SHIFT_PIPER_MODEL=/path/to/model.onnx timbre-shift web
```

## 页面入口

网页左侧进入：

```text
文字朗读
```

流程：

```text
输入文字 → Piper TTS 生成普通朗读干声 → Seed-VC / RVC 换成目标音色 → 输出播放器和下载
```
