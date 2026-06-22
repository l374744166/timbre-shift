# Timbre Shift 后续优化记录

## 本轮已落地

- 音色偏好记忆：结果页可以把当前参数保存为该音色默认参数，下次选择这个音色时自动应用。
- RVC 输入前清理：Applio/RVC 生成前可选择关闭、标准、强力三档源人声清理。
- 混音风格：可选择自然、人声靠前、伴奏融合三档，统一影响最终输出和对比版本。
- 生成历史：每次生成会归档到 `outputs/history/job_.../`，保留 `final.wav`、`final.mp3`、`metrics.json`、`variants/` 和 `source_info.json`。
- 页面历史列表：可查看最近生成记录并下载历史 MP3/WAV。

## 演示建议

- 默认用“自然稳定 + 混音自然 + 源人声清理关闭或标准”展示稳定效果。
- 如果歌词糊，切“歌词更清楚”。
- 如果人声被伴奏压住，切“人声靠前”。
- 如果源人声比较脏，再打开“源人声清理：标准”；强力只用于明显脏的素材。
- 生成对比版本后，先听三版，选最好的一版“设为最终版本”，再保存为该音色默认参数。

## 后续最有必要继续做

1. 音色记忆库 15 秒安全测试

当前 index 仍是实验项。后续应该先截取 15 秒跑 index 探测，成功后才允许整首启用，失败自动关闭。

2. 素材启用/禁用

给每个 voice sample 增加：

- `enabled_for_training`
- `enabled_for_seedvc_ref`
- `quality_note`

这样脏素材可以保留但不参与训练。

3. 素材标签

给素材标注：

- clean_vocal
- separated_vocal
- spoken
- singing
- high_range
- low_range
- fast_phrase
- long_note
- soft_voice
- strong_voice

后续训练质量会更可控。

4. 生成历史删除和打开目录

现在历史可以下载，后续可以加删除、打开目录、设为当前最终版本。

5. 唱法相似度下一阶段

RVC 主要改变音色，不真正改变唱法。若要提升唱法像目标人物，需要做：

- guide vocal
- F0 重塑
- 节奏/咬字迁移
- 风格参考轨

这些不适合继续靠 RVC 参数硬调。
