# Timbre Shift Web 功能接口清单

这份清单用于前端页面优化时防止误删、误增或改名接口。页面可以改布局和样式，但以下路由语义保持不变。

## 页面和静态资源

- `GET /`：打开 Timbre Shift 工作台页面。
- `GET /static/*`：加载前端 JS/CSS 静态资源。
- `HEAD /static/*`：静态资源探活。

## 查询接口

- `GET /api/check`：环境检查。
- `GET /api/progress`：当前任务进度。
- `GET /api/history`：生成历史列表。
- `GET /api/latest-result`：恢复最近一次生成结果。
- `GET /api/voice-preference?voice_id=...`：读取音色默认参数。
- `GET /api/voice-samples?voice_id=...`：读取某个音色的素材列表。
- `GET /api/voice-models?voice_id=...&engine_id=...`：读取某个音色的模型列表。

## 下载接口

- `GET/HEAD /download/history/<job_id>/<filename>`：下载历史结果。
- `GET/HEAD /download/variants/<filename>`：下载对比版本。
- `GET/HEAD /download/<filename>`：下载当前输出。

## 写入/任务接口

- `POST /api/generate`：歌曲生成。
- `POST /api/cancel-task`：请求停止当前任务。
- `POST /api/tts-generate`：文字朗读生成。
- `POST /api/voice-preference`：保存音色默认参数。
- `POST /api/history-restore`：恢复历史任务。
- `POST /api/history-delete`：删除历史任务。
- `POST /api/select-variant`：选择对比版本为最终版本。
- `POST /api/variant-feedback`：标记喜欢某个对比版本。
- `POST /api/save-voice`：Seed-VC 保存参考声音。
- `POST /api/create-voice-profile`：RVC 创建空音色库。
- `POST /api/add-voice-sample`：给音色库补充素材，可做分离。
- `POST /api/delete-voice-sample`：删除训练/参考素材。
- `POST /api/delete-voice`：删除音色库。
- `POST /api/delete-song`：删除歌曲库歌曲。
- `POST /api/delete-voice-model`：删除 RVC 模型。
- `POST /api/applio-prepare`：准备 Applio 数据集。
- `POST /api/applio-train`：Applio RVC 训练。

## 前端优化约束

- 不新增后端接口。
- 不删除后端接口。
- 不修改现有接口路径。
- 保留现有主要 DOM id，避免破坏 JS 事件绑定和测试。
- 页面文案、布局、颜色、卡片样式可以优化。
