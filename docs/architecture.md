# Timbre Shift 代码结构

这份说明按功能划分代码入口，方便后续改功能时快速定位。

## 启动入口

- `src/timbre_shift/cli.py`：命令行入口，负责 `check`、`check-mps`、`web`、`demo` 和音色/歌曲库管理命令。
- `src/timbre_shift/web.py`：本机网页服务入口，负责 HTTP 接口、上传文件、调用生成流程和下载文件。

## 网页层

- `src/timbre_shift/web.py`：后端接口，包括生成歌曲、保存音色、追加音色素材、删除音色、下载结果。
- `src/timbre_shift/web_template.py`：网页 HTML/CSS/JS 模板。改界面按钮、布局、前端交互、引擎选择、模型下拉主要看这里。
- `src/timbre_shift/web_state.py`：生成进度状态，供 `/api/progress` 返回当前步骤和百分比。
- `src/timbre_shift/web_utils.py`：网页层小工具，比如上传文件名、下载文件名清洗。

## 生成流程

- `src/timbre_shift/pipeline.py`：核心编排流程，从输入音频到最终 MP3/WAV。主要步骤是处理音色、处理歌曲、分离人声、压缩有效人声、Seed-VC 换声、还原时间线、人声优化、混音导出、诊断报告。
- `src/timbre_shift/pipeline_config.py`：生成模式和参数配置，包括 `m2max_hq_30`、`m2max_hq_plus`、`m2max_offline_max`，以及默认转换引擎、指定模型 ID、是否启用 Seed-VC 分段。
- `src/timbre_shift/seed_vc.py`：Seed-VC 调用、缓存、设备选择和 CPU 回退逻辑。
- `src/timbre_shift/rvc_mlx.py`：RVC-MLX 实验后端辅助逻辑，包括依赖检测、训练数据集准备、cache key、训练/推理 wrapper。
- `src/timbre_shift/demucs.py`：Demucs 人声/伴奏分离和分离缓存。

## 转换引擎

- `src/timbre_shift/engines/base.py`：转换引擎接口和统一结果对象。
- `src/timbre_shift/engines/registry.py`：引擎注册表，当前注册 `seedvc` 和 `rvc_mlx`。
- `src/timbre_shift/engines/seedvc_engine.py`：Seed-VC 引擎包装，不需要训练。
- `src/timbre_shift/engines/rvc_mlx_engine.py`：RVC-MLX 实验引擎包装，需要训练模型，未安装时只报告缺依赖。

## 音频处理

- `src/timbre_shift/audio.py`：ffmpeg/音频基础工具，包括标准化、混音、导出 MP3、切片拼接、人声优化。
- `src/timbre_shift/vocal_segments.py`：检测有效人声片段，压缩静音区域，换声后还原到原歌曲时间线。
- `src/timbre_shift/diagnostics.py`：生成后音频质量检测，包括爆音、静音比例、频段异常等提示。

## 本地素材库

- `src/timbre_shift/library.py`：SQLite 本地库，管理已保存音色、音色素材、歌曲记录、歌曲分离结果、RVC-MLX 模型记录。

## 通用工具

- `src/timbre_shift/commands.py`：外部命令执行封装，比如 ffmpeg、Demucs、Seed-VC 子进程调用。

## 当前默认策略

- 默认使用 MPS：网页生成时传入 `device="mps"`。
- 默认转换引擎是 `seedvc`，RVC-MLX 作为实验后端保留。
- Seed-VC 使用音色参考音频，不需要选择训练模型；RVC-MLX 可以选择具体 ready 模型，不选时自动使用最新 ready 模型。
- 默认不启用 Seed-VC 分段：`pipeline_config.py` 中 `TIMBRE_SHIFT_SEEDVC_CHUNK_SECONDS` 默认是 `0`。
- 如果以后要临时测试分段，可以启动前设置环境变量，例如 `TIMBRE_SHIFT_SEEDVC_CHUNK_SECONDS=30 TIMBRE_SHIFT_SEEDVC_CHUNK_WORKERS=2`。
