# 视觉规格（锁定值）

改这些值之前先想清楚：它们是这套风格的识别特征，不是随手调的。

## 画布与时间

| 项 | 值 |
| --- | --- |
| 画布 | 1080 × 1920 |
| 帧率 | 30 fps |
| 时长 | = 音频实际时长（`project.json.duration`） |
| 安全边距 | 左右 60 px |

## 配色

| 用途 | 值 |
| --- | --- |
| 底色 | `#04050D` |
| 天空渐变 | `#0D1238` → `#070A1E` → `#04050D` |
| 冷光斑 | `rgba(58,88,196,.55)` / `rgba(28,132,158,.50)` |
| 暖光斑 | `rgba(112,66,186,.48)` / `rgba(150,58,128,.42)` |
| 英文正文 | `#F5F2EB` |
| 中文正文 | `#DDA97D`（暖棕） |
| 标题 | `#F7F3EA` |

## 玻璃体

- 半径 214 px，中心活动范围 x ∈ [244, 836]，y ∈ [284, 1636]。
- 轮廓 = 96 个采样点径向插值出的闭合路径，圆角过渡，**任何形态都必须轮廓清晰**，禁止液体/尖刺/碎裂。
- 材质：径向渐变 `glassGrad`（顶部 34% 白高光 → 边缘 30% 白）+ 彩虹描边 `rimGrad`（2.6 px）+ 外发光（20 px, 20%）+ 内膜（13 px, 30%）+ 内侧暗边（30 px, 26%）+ 两处高光 + 底部反光。
- 撞边：沿法线压缩到 0.89（正弦窗口 0.5 s），0.06 s 后开始 0.88 s 的轮廓插值，期间形状连续变形。
- 速度：`50 + 34 × energy` px/s，随段落能量缓慢呼吸，绝不突变。

## 字幕

- 整块 `top: 0; bottom: 0` + `.line { top: 50%; translateY(-50%) }` → 单行/双行都围绕 y=960 扩展，不上下跳。
- 英文：Inter（`local("Segoe UI")`），500 字重，行高 1.26，字号按长度 56/50/45/40。
- 中文：宋体（`local("SimSun"), local("宋体")`），37 px，字距 0.10em，行高 1.52，`margin-top: 26px`。
- 衬底：`radial-gradient(96% 46% at 50% 50%, rgba(4,5,13,.90) → transparent 95%)`，覆盖整行宽度。
- 淡入：`start - 0.22s` 起，0.14–0.24 s 完成，同时上移 16 px 归位。
- 淡出：`end + 0.16s` 收尾，且不得晚于下一句起点 - 0.02 s。
- 显示窗口下限 1.4 s，上限 8.5 s。

## 乐队图层

- 素材：`assets/band_sheet{1,2}.webp`，8 列 × 7 行，单元 720×350，共 109 帧。
- 位置：`left:0; bottom:0; width:1080px; height:526px`，`background-size: 8640px 3682px`。
- 帧选择：`idx = floor(t × 24) % 109`，`col = local % 8`，`row = floor(local / 8)`。
- 切换图片只改 `background-position`，两张图用 opacity 0/1 切换，避免运行时加载。
- 合成：`mix-blend-mode: screen`，素材背景已扣成纯黑，因此背景部分贡献为 0，无接缝。
- 舞台光：`.band-glow` 整幅径向渐变，中心 (50%, 89%)，`rgba(44,118,150,.34)`，
  透明度 `0.52 + 0.16·sin(0.085t) + 0.16·energy`。

## 片头 / 片尾

- 片头 2.2–3.6 s 淡入，11.4–12.8 s 淡出；标题字号 `min(132, 900 / max(4, 0.5·len))`。
- 常驻角标 13.2–14.8 s 淡入，186.4–188.0 s 淡出，透明度 0.55。
- 片尾 188.4–190.6 s 淡入，字号 `min(104, 780 / max(4, 0.5·len))`。
- 结尾 203.4–205.9 s 整体压黑到 96%。

## 校验基线

`hyperframes check .` 应满足：lint 0 error、runtime 0 error、layout 0 issue、motion 0 error、
contrast 全通过（本机基线 14/14）。`composition_file_too_large`（单帧 > 300 行）是风格提示，可忽略。

## 乐队表演风格系统（classic 为锁定基线）

风格参数唯一数据源 = `config/styles.json`（与本文档同级的 skill 配置，改值必须同步本文档）。
`classic` 即上方「乐队图层」全部锁定值：速率 1.0、无编舞偏移、无点缀、舞台光 `rgba(44,118,150,.34)` / 0.52 基准。

### 风格一览（锁定值）

| 参数 | emotional_listening | energetic_performance | funny_interaction | cozy_ensemble |
| --- | --- | --- | --- | --- |
| 播放速率 | 0.625×（12 fps 精确保持） | 1.25×（30 fps 1:1） | 1.0× | 1.0× |
| 摇摆 sway | 1.0° / 9.5 s | 1.6° / 1.67 s（按小节） | 1.1° / 2.2 s | 0.7° / 2.5 s |
| 弹跳 bounce | 3 px / 4 拍 | 9 px / 每拍 | 5 px / 2 拍 | 4 px / 2 拍 |
| 呼吸 breathe | 0.005 / 11 s | 0.008 / 1.67 s | 0.006 / 6.0 s | 0.005 / 8.0 s |
| 拍点冲击 beat_punch | — | 0.013（衰减 7.0） | 0.004（衰减 5.0） | 0.006（衰减 6.0） |
| 点缀速率 accents | 7 次/分（心 0.4 / 音符 0.45 / 闪光 0.15） | 22 次/分（音符 0.5 / ! 0.3 / 闪光 0.2） | 12 次/分（! 0.4 / ? 0.35 / 音符 0.25） | 10 次/分（音符 0.35 / 心 0.35 / 闪光 0.3） |
| 定格 holds | — | — | 开：≤3 次、间隔 ≥18 s、时长 0.24–0.40 s | — |
| 舞台光 glow | 蓝 [70,96,190] 基准 0.42 | 暖粉 [196,88,120] 基准 0.55 | 琥珀 [190,150,70] 基准 0.50 | 暖玫红 [170,120,140] 基准 0.50 |
| 动画强度 motion_intensity | 0.25 | 1.00 | 0.70 | 0.45 |
| 互动概率 interaction_probability | 0.05 | 0.15 | 1.00 | 0.35 |

### auto 推荐判定链

读 `audiomap.json` 推导 `energy_median` / `bpm` / `high_energy_frac` / `surges` / `rolls` 后按序判：

1. `bpm ≥ 105` 且 `energy_median ≥ 0.5` → `energetic_performance`
2. `energy_median ≤ 0.30` 且（`bpm < 90` 或低能量占比 ≥ 45%）→ `emotional_listening`
3. 能量起伏大（p25–p75 跨度）且 `rolls ≥ 3` → `funny_interaction`
4. 其余 → `cozy_ensemble`

### mixed 分段与搞笑桥段

- 按 `phrases`（乐句）切段，段能量 < 0.30 → emotional，> 0.55 → energetic，其余 → cozy；
  短于 5 s 的段合并，`funny_interaction` 豁免合并；同项目同时使用的风格受 `cap_styles` 限制（按雪碧图组数 ≤ 3，当前五风格共用一组，故不互斥）。
- 搞笑 one-off **锚定音乐事件时刻**（hard_stop、roll 尾、SURGE/DROP），在宿主段内 split 出 1.4–2.0 s 的 funny 段，
  不是按拍点网格猜位置；段间 0.45 s 交叉淡变（每风格独立 `.bandstyle` wrapper，手动驱动，无 CSS transition）。

### 确定性

- 种子 = `crc32(artist|title|mode)`，`plan_styles.py` 预生成全部事件/分段写入 `style_plan.json`；
  同一项目重跑两次 `style_plan.json` 逐字节一致。
- 浏览器运行时无随机、无 CSS 动画：编舞是解析函数（sway/bounce/breathe/punch），
  定格用 `loopTime` 积分冻结，点缀是 26 个池化 div 按事件可见性重算。
- 风格切换只重设表演参数，**不改 `lyrics` 时间轴**；帧率对齐规则见上表（0.625× 与 1.25× 对 30 fps 输出均为整数帧保持）。
