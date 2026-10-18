---
name: lyric-video
description: 用 HyperFrames 生成 1080×1920 竖屏双语歌词视频：深色梦幻背景 + 单个透明玻璃几何体撞边变形 + 底部小动物乐队 + 居中「原文 + 中文」字幕，时间戳来自 Whisper 实测。当用户给出歌曲音频（MP3/WAV）和歌手名字，要求做歌词视频、歌词 MV、带字幕的音乐视频、给一首歌配歌词动画时使用。音频路径与歌手名是唯二必需输入；用户另给官方歌词时优先采用（歌词为可选项，不给就用 Whisper 重建）。
agent_created: true
---

# 歌词视频标准流水线

一套已经验证过的固定风格。用户只需要给**音频文件**和**歌手名字**，其余全部按本标准执行，不要重新设计视觉。
官方歌词是**可选项**：给了走 3A 快路径（文本零猜测），不给就走 3B 重建路径，两条路的时间轴都必须是实测。

## 输入 / 产出

| 输入 | 说明 |
| --- | --- |
| 音频 | **必需**。任意 MP3/WAV/FLAC，时长不限 |
| 歌手名 | **必需**。用于片头、常驻角标、片尾署名 |
| 官方歌词（可选） | 用户手头有官方歌词时优先采用：文本零猜测，时间轴仍全部走实测重解（见 3A）。不给则用 Whisper 重建（3B） |
| 歌名（可选） | 缺省取文件名；`Artist - Title.mp3` 会自动去掉歌手前缀 |
| 主题句（可选） | 片头标题下的一行中文，缺省不显示 |

产出：`<project>/renders/video.mp4` + `renders/contact-sheet.jpg` + `transcript.json` + `NOTES.md`。

## 固定规格（不可擅自更改）

- 竖屏 1080 × 1920，30 fps，总时长 **等于音频实际时长**（不裁剪、不拉伸、不变速）。
- 音频用原始文件，渲染时由框架统一增益（`data-volume="0.9"`）。
- 背景：纯黑到极深蓝紫，两组错位光斑缓慢交叉淡入；**不使用全屏 CSS 滤镜**（会留分块接缝）。
- 主体：**只有一个**透明玻璃体，8 种圆角几何轮廓（球/横椭圆/竖椭圆/圆角矩形/菱形/三角/五边形/六边形），撞屏幕边缘时沿法线压缩 11% → 0.94 s 内变形为另一种轮廓 → 反弹继续漂移。整曲单时间轴，**不在歌词切换时重置**。
- 底部：小动物乐队（猫/熊/企鹅/狐狸）4.5417 s 无缝循环，贴底 1080×526，层级在背景光斑之上、玻璃体之下，`mix-blend-mode: screen`。
- 字幕：整块以画面垂直中心 y≈960 为光学中心；英文/原文在上（Inter，字号按行宽自适应），中文在下（宋体 SimSun，暖棕 `#DDA97D`），同组淡入淡出。
- 署名统一用歌手名，**画面里不出现任何 VERSE / CHORUS / BRIDGE 之类段落标签**。

细节参数、颜色、字号、坑位见 `references/style-spec.md`。

## 流程

设 `HF` = HyperFrames 安装根目录（默认 `G:\hyperframes`），
`PY` = 带 faster-whisper 的 Python（默认 `C:\Users\Admin\.workbuddy-ai\binaries\python\envs\hf\Scripts\python.exe`），
`SK` = 本 skill 目录。

### 1. 建项目

```bash
"$PY" "$SK/scripts/new_project.py" "<音频路径>" "<歌手名>" [--title "歌名"] [--tagline "一行中文"] [--root G:/hyperframes/videos]
```

输出项目绝对路径，务必记下。它会：建唯一目录 → 复制音频 → 转 16 kHz 单声道 WAV → 跑官方
`analyze-beatgrid.py` 生成 `audiomap.json` → 复制乐队雪碧图与 GSAP → 写 `project.json`。

**绝不覆盖已有项目目录**；修改已交付作品必须新建项目。

### 2. 转写

```bash
"$PY" "$SK/scripts/transcribe.py" "<project>" --model medium.en --lang en
```

CPU int8 跑 3–4 分钟的歌约 3–6 分钟。非英语歌把 `--lang` 换成对应语言、`--model` 去掉 `.en`。
产出 `whisper_raw.json`（段 + 词级时间戳）。

**混语言歌（英语+日语、英语+韩语等）不要用 `transcribe.py`**：`--lang` 会锁定一种语言，
另一种语言会被强行听写成第一种语言 —— 结果读起来通顺但全是错的，比解不出来更危险。
改用逐窗自动判语种：

```bash
"$PY" "$SK/scripts/transcribe_mixed.py" "<project>" --model "C:/Users/Admin/.cache/whisper-manual/large-v3-turbo"
```

它按 14 s 窗口 / 10 s 步进解码，每窗自己判语种，只保留窗口核心的词（重叠区丢弃，不会重复），
打印语言地图并写 `whisper_mixed.json`。**先看语言地图**：语种翻转的位置通常就是段落边界。
注意 `.en` 模型（medium.en / small.en）是纯英语模型，物理上无法输出日语，混语言歌必须换多语言模型。

走 3A（有官方歌词）时本步可选：时间轴以提示词重解为准，但混语言歌仍建议先跑一遍 `transcribe_mixed.py`
看语言地图，用于确定每窗该用 `--lang en` 还是 `--lang ja`。

### 3. 写歌词源文件（这一步必须自己做）

先判断走哪条路径，再写 `<project>/lyrics_source.json`。

**3A 用户提供了官方歌词（首选路径）**

- 文本一行不改地采用官方歌词：`en` 槽即官方原文（英文句放英文，日语句放日语，汉字/假名照写），`zh` 逐句翻译。
- **时间轴不走全曲转写**：用官方歌词作 `initial_prompt` 分区重解拿词级时间戳（做法见 3.5），每行写显式 `start`/`end`，`align_lyrics.py` 会走 manual 通道逐行锚定。
- 官方歌词与复解听到的不一致 → 一律按官方采用，把差异列进 NOTES.md 请用户确认。常见三类：标准词形 vs 笔误（不甲斐ない / 不甲埋ない）、发音相近词（束の間の / 明日の間の）、清辅音误听（smiling / falling）。
- 官方歌词里一口气唱完、拆开每行不足 1 秒的两行 → 字幕合并为一行显示（文字未改、仅并排），合并对照表写进 NOTES.md。
- 官方歌词中没有的拟声/即兴段（"Yeah,"、哼唱、口哨）→ 不配字幕，不要自己编。
- 结构照此写：

```json
{
  "audio": "Artist - Title.mp3",
  "models": ["large-v3-turbo — prompted window re-scans, official lyrics as initial_prompt"],
  "lines": [
    {"en": "Oh my god, they're coming again", "zh": "哦天哪，他们又来了", "start": 6.36, "end": 9.10, "lang": "en", "conf": "high"}
  ]
}
```

**3B 没有官方歌词（重建路径）**

读 `whisper_raw.json`（或混语言歌的 `whisper_mixed.json`）写出歌词源：

```json
{
  "audio": "Artist - Title.mp3",
  "models": ["faster-whisper medium.en — full track, word timestamps"],
  "lines": [
    {"en": "Sometimes I lay under the moon", "zh": "有时我躺卧在月光之下"},
    {"en": "And thank God I'm breathing", "zh": "感谢上天让我仍在呼吸"}
  ]
}
```

两条路径共同的要求：

- 行 = 实际演唱的一句，按官方断句；Whisper 合并过长的句子要拆开。
- 英文拼写按官方歌词校对（`'Cause` / `I've` 等保留撇号），**不要照抄 Whisper 的错字**。
- 中文逐句翻译，语气与歌曲一致，**不要漏句、不要合并、不要占位文本**。
- 重复的副歌要逐次写出（不要用「同上」）。
- 如果某句人声被伴奏盖住、自动对齐明显偏移，给它加显式时间（听完音频再填）：
  `{"en": "...", "zh": "...", "start": 13.22, "end": 16.80}`。
- 中文歌/纯音乐：中文歌把 `en` 填原文、`zh` 留空字符串，画面只显示一行；纯音乐不适用本 skill。
- **混语言歌**：`en` 槽位放该句实际语言的原文（英文句放英文，日语句放日语，汉字/假名照写），
  `zh` 放中文翻译。画面本来就是「原文 + 中文」两行，混排不会破坏版式；
  模板的英文行已带 `Yu Gothic UI / Yu Gothic / Meiryo` 兜底，假名和汉字能正常出字。

### 3.5 提示词重解：时间轴精度的核心手段

全曲转写对快歌、混唱、快嘴句普遍不准。用已知歌词作 `initial_prompt` 分区重解是精度上限最高的手段——
**提示词质量直接决定复解精度：官方歌词 > 猜的歌词 > 无提示词**。可写进 `rescan_all.sh` 批量跑完整首：

```bash
"$PY" "$SK/scripts/rescan.py" "<project>" --from 6.0 --to 20.0 \
    --model "C:/Users/Admin/.cache/whisper-manual/large-v3-turbo" \
    --lang en --prompt "<该窗口的官方歌词原文>"
```

要点：

- 全曲切成 20–26 s 窗口、窗间重叠约 0.5 s，逐窗重解；`large-v3-turbo` CPU int8 单窗约 5–10 s。
- 混语言歌每窗 en/ja 双路各解一遍：两路一致的词级时间才采用，只在一路出现的词用另一路复核。
- 抢拍/起点不明的句子加 2 s 窄窗补锁（`--from 37.2 --to 39.2` 只锁一句的起点）；分区窗起点容易被前一句尾音带偏。
- **幻觉处理**：复解偶发把同一整句重复输出 15+ 次 → 该窗作废，换另一语言通道或缩小窗口重解，只取干净的单次时间戳，别把幻觉写进歌词源。
- 每次重解保存 `rescan_<from>-<to>.json` 并打印窗口内每个词的起止。**这是二次解码，不是估算**；数字直接写进 `lyrics_source.json` 的 `start`/`end`。
- 被伴奏盖住、处理成 `ooh`、合并成一大块、重复句被吞掉的段落，同样先用本手段再写覆盖值；换模型（`small.en` / `medium.en`）也有效。

### 4. 对齐 + 生成

```bash
"$PY" "$SK/scripts/align_lyrics.py" "<project>"
"$PY" "$SK/scripts/motion.py" "<project>"
"$PY" "$SK/scripts/gen_storyboard.py" "<project>"
"$PY" "$SK/scripts/build_frame.py" "<project>"
"$PY" "$SK/scripts/make_index.py" "<project>"
```

`align_lyrics.py` 会打印逐行时间表，并做两道硬检查：

- 开头/结尾有句子完全对不上 → 直接报错退出，并列出是哪几句（不会用猜的时间糊过去）。
- 中间有句子对不上、或两句起点相同、或某句被压缩到 0.5 s 以下 → 打印 `REVIEW` 并退出码 2。

出现这两种情况就回到 3.5 步补覆盖值，直到输出 `OK: every line anchored to a real sung timestamp`。
**不要跳过这一步去渲染**。3A 路径的行全部带显式 `start`/`end`（manual 通道），应全部锚定、0 gap-filled；
3B 路径靠词匹配，对不上的行按 3.5 补时间。

`motion.py` 的随机种子由「歌手名+歌名」决定 —— 同一首歌每次重跑路径完全一致，不同歌不同路径。

### 5. 校验

```bash
cd "<project>"
node "$HF/packages/cli/bin/hyperframes.mjs" check .
node "$HF/packages/cli/bin/hyperframes.mjs" snapshot . --at "3,20,60,120" --no-end -o build/shots
```

必须做到：lint / runtime / layout / motion **0 error**，contrast 全部通过 WCAG AA。
然后**实际看截图**：玻璃体是否完整、歌词是否居中、乐队是否在底部、有没有多余的泡泡或段落标签。
`composition_file_too_large` 是单帧文件超过 300 行的风格提示，可接受（单时间轴设计必然如此）。

### 6. 渲染 + 验收

```bash
node "$HF/packages/cli/bin/hyperframes.mjs" render . --skill=music-to-video -q delivery -o renders/video.mp4 --fps 30
"$PY" "$SK/scripts/verify.py" "<project>"
```

`verify.py` 会核对分辨率/帧率/时长偏差（超过一帧即报错）并生成联系表。**必须看联系表**，
确认开头、主歌、副歌、重复段、结尾都有画面，字幕没有空档或错位。

最后写 `NOTES.md`（规格、时间轴来源、复现命令、校验记录），把成片和联系表交付给用户。

## 硬性纪律

- 不得用 BPM/节拍网格推算歌词时间；时间戳只能来自 Whisper 实测（含提示词重解）或人工听音覆盖。
- 用户提供的官方歌词优先于任何模型重建结果；两者冲突时按官方采用，并把差异写进 NOTES.md 请用户确认。
- 不得因为「看起来更好」而改分辨率、帧率、时长、署名或字幕位置。
- 不得在未验证的情况下宣称音画同步；每首歌都要抽帧看。
- 素材缺失、工具不可用、规格冲突 → 明确报告，不用估算数据冒充结果。
- 已交付项目与其源文件视为只读；改版必须新建目录。

## 环境依赖

- HyperFrames：`node <HF>/packages/cli/bin/hyperframes.mjs`（含 `skills/music-to-video/scripts/analyze-beatgrid.py`）。
- Python：`faster-whisper`、`librosa`、`soundfile`、`numpy`、`scipy`、`pillow`。
  缺失时 `python -m venv <env> && <env>/Scripts/pip install faster-whisper librosa soundfile numpy scipy pillow`。
- Whisper 模型：直接传模型名会自动下载；也可指向本地目录（本机常用
  `C:\Users\Admin\.cache\whisper-manual\medium.en`；提示词重解首选
  `C:\Users\Admin\.cache\whisper-manual\large-v3-turbo`，CPU int8 整曲约 48 s、单窗 5–10 s）。
- ffmpeg / ffprobe 需在 PATH。

## 已知坑

- **不要用 `<video>` 做乐队图层**：本机 `hyperframes render` 会在 Windows 上把提取帧目录链接进编译目录后
  读取失败（`ENOENT ... __hyperframes_video_frames/*/frame_00001.jpg`）。用雪碧图。
- 全屏 CSS `filter: hue-rotate()` 会在渲染里留下竖向接缝，改用两层光斑交叉淡入。
- 带 `data-composition-id` 的模板 HTML 不能放项目根目录（会触发 `multiple_root_compositions`），放 `build/`。
- 中文字体必须显式 `@font-face` 声明 `local("SimSun")`，否则 lint 报 `font_family_without_font_face`。
- **复解幻觉**：某几窗会把同一整句重复输出 15+ 次（如「永遠の行方はどこにある?」×15）→ 该窗作废，
  换交叉的 en 通道或缩窗重解，别把幻觉时间戳写进歌词源。
- **官方歌词 vs 复解不一致**：按官方采用并在 NOTES.md 列对照表请用户确认，别自作主张改官方文本。
- **快嘴合并行**：官方歌词里一口气唱完、拆开不足 1 秒的两行，字幕合并为一行显示（文字不改，仅并排），
  合并对照表写进 NOTES.md。
- **headless 字体加载失败**（抽帧时 Yu Gothic UI 报 FAILED）不必紧张：`src: local()` 的字体系统装了浏览器一般能找到，
  下一顺位字体也会兜底，先看截图再决定要不要处理。
