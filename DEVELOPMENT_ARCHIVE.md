# FrameDeck 开发存档与项目知识库

> 更新日期：2026-11-03
> 本文档记录本仓库的完整改造历史、架构要点、已验证结论与遗留事项，供后续开发者（人或 AI）快速接手。

---

## 〇、开发文档存放规则（必读）

**本文件夹（`New/FrameDeck/`）是唯一的工作与文档存放地。** 所有开发文档一律写在这里，不外写其他位置：

| 文档 | 位置 | 内容 |
|---|---|---|
| `README.md` | 包根目录 | 项目说明（2026-11-03 重写为中文：快速开始 / 新增功能 / 快捷键 / 构建 / 文档索引） |
| `DEVELOPMENT_ARCHIVE.md`（本文件） | 包根目录 | 开发存档总纲：改造历史、架构约束、事故教训、遗留事项 |
| `BUILD.md` | 包根目录 | 构建方法（单 exe / 多目录 / 开发运行） |
| `build.sh` | 包根目录 | **统一构建脚本**（Windows/Linux 通用，`./build.sh onefile\|windows\|linux`，2026-11-03 新增，onefile 全流程实测通过） |
| `doc/l10n/术语表.md` | doc/l10n/ | 232 条术语 + 字面量锁 + 撞词规则（翻译唯一依据） |
| `doc/l10n/汉化改造规范.md` | doc/l10n/ | 汉化施工规范（批次表/门禁/不译清单） |
| `doc/l10n/译文索引-高频四文件.md` | doc/l10n/ | 185 条译文 + 验证边界 + 六项目视清单 |
| `doc/l10n/check_l10n.py` | doc/l10n/ | 静态验收扫描器（`--baseline d3d8497 --strict`） |
| `doc/l10n/extract_pairs.py` 等迁移工具 | doc/l10n/ | UI 改动后增量同步语言文件的工具链 |
| `.workbuddy/memory/`（上一级 New\ 下） | New/.workbuddy/memory/ | AI 工作记忆（非交付内容，打包发布时可不含） |

> 旧工作区 `FrameDeck-main\` 已冻结停用，其中可能残留早期文档副本，一律以本文件夹为准。

**2026-11-03 文档清理记录**：原版 `README_WINDOWS.md` / `README_UBUNTU.md` / 越南语指南（HUONG_DAN*）/ 旧发布说明 / 作者机器专用 `call-*` 脚本 / `doc/PLAN-reviewapp-parity.md` / mkdocs 文档站（`doc/docs/`、`mkdocs.yml`）/ bug 报告模板已全部删除——它们指向已不存在的脚本、旧版本号或作者私有路径，会造成误解。README 截图保留于 `doc/framedeck-color-playlist-overview.png`。

---

## 一、项目是什么

**FrameDeck** 是一款 Python 3 + PySide6 的桌面端 VFX 审片播放器（shot review player），基于开源项目 viewline 扩展，定位类似 RV / DaVinci Resolve 的审片页 / Nuke 的 Viewer 工作流。

- **代码规模**：约 28,000 行 Python
- **核心模块**：
  | 目录 | 职责 |
  |---|---|
  | `widgets/`（约 17,300 行） | 全部 UI。`__init__.py` 3,100 行主窗口、`viewer.py` 2,400 行查看器、`playlist.py`、`comments.py`、`recaps.py`、`cachemanager.py` 等 |
  | `playback/` | 播放引擎：`player.py`（MediaPlayer）、`reader.py`（解码）、`proxy.py`（代理）、`stats.py`（性能统计） |
  | `constants/` | 枚举与常量（`STATUS_LIST`、`LOOP_MODES`、`COMPARE_MODES`、`REVIEW_TYPES` 等） |
  | `utils/` | 工具 + **`i18n.py`（国际化核心，本次新增）** |
  | `resources/i18n/` | **9 个语言文件（本次新增）** |
  | `ocio/` `logger/` `scripts/` | 色彩管理、日志、辅助脚本 |
  | `tests/` | pytest 测试（需 PySide6 环境） |

---

## 二、本次改造总览（2026-11-03 单日完成）

### 2.1 中文汉化（批次 B1–B6）

全项目 **约 470 条界面文案中文化**，术语对标 DaVinci Resolve / Premiere / Nuke 中文版。静态验收四项指标全零（残留英文 / 占位符漂移 / 改动范围 / 测试断言同步），功能逻辑零改动。

| 批次 | 内容 | 提交 |
|---|---|---|
| 基线 | git init + 全树快照（项目外 `FrameDeck-l10n-baseline-2026-11-03.tar.gz`） | `d3d8497` |
| B1 | 枚举与共用小部件（92 条） | `b5ce1da` + `36d040e`(fix) |
| B2 | 主窗口外壳：菜单/工具栏/状态标签（69 条） | `0d802cc` |
| B3 | 弹窗/状态栏消息/导出入口 + 测试断言同步（95 条） | `5f0b6f2` |
| B4 | 面板与评论链路（116 条） | `5b5a3a6` |
| B5+B6 | 查看器 HUD 映射 + 导出 + PDF 字体回退 + 标注收尾 | `bee5700` |

**施工依据文档**（`doc/l10n/`，均可复用）：
- `术语表.md`：232 条术语 + 9 条字面量锁（L-01~L-09）+ 撞词规则 N-01~N-04
- `汉化改造规范.md`：1,300+ 行，含批次表、门禁、不译文件清单
- `译文索引-高频四文件.md`：184 条 + §0.1 验证边界 + §0.1.1 六项目视清单
- `check_l10n.py`：静态验收扫描器（标准库 AST，可挂 pre-commit）

### 2.2 i18n 国际化架构

**设计**：以英文原句为键。代码写 `tr("Import Media...")`，`tr()` 查语言表返回译文；英文版零配置（key 即文案）。

| 文件 | 说明 |
|---|---|
| `utils/i18n.py` | `tr(key)` / `init()` / `current_language()` / `AVAILABLE`（9 语言）/ `SETTINGS_KEY = "i18n/language"`（QSettings 持久化） |
| `resources/i18n/*.json` | zh_CN（466+ 条）、zh_TW（OpenCC s2t 全量转换）、en_US（空）、ja / ko / ru / fr / de / es（各 466 条） |
| 语言切换 | 工具 → 语言。**同进程重建主窗口即时生效**（`_switch_language`），当前素材经临时播放列表文件自动搬运，无需重启 |

**迁移工具链**（`doc/l10n/`，UI 改动后可重跑增量同步）：
`extract_pairs.py`（diff hunk 配对提取英→中）→ `migrate_tr.py`（位置精确替换 + 每文件语法自检回滚）→ `fstring_format.py`（f-string 模板转 `tr("EN {0}").format()`）→ pass3/pass4（整串反查 + 段级映射）。

### 2.3 RV 式逐帧拖动（scrub）

- 导航模式下按住左键在画面上水平拖动，每 `constants.FRAME_DRAG_PIXELS_PER_FRAME = 10` 像素 = 1 帧，累积式映射无跳帧
- 实现链：`viewer.py` 发 `frame_scrub_started` / `frame_scrubbed(int)` 信号 → 主窗口 `_on_frame_scrub_started`（自动暂停且不恢复）+ `_on_frame_scrubbed`（**双路径 seek**：播放列表模式走全局帧 `_seek_playlist_frame`；单素材直开模式走 `player.seek()` 并用 `player.frame_count` clamp 边界）
- 防误触：Ctrl/Shift 修饰、标注模式、伽马/曝光检查、划像手柄、中键平移均优先接管
- 帮助 → 快捷键 对话框含「在画面上按住左键左右拖动：逐帧微调」

### 2.4 打包

- `framedeck-onefile.spec`：单 exe（109 MB），PyInstaller 6.21 + Python 3.13
- 构建方法见 `BUILD.md`；未内置 ACES 1.2 OCIO 配置（数百 MB），缺失时程序以 OCIO Off 模式正常容错
- 交付包：本目录（源码 + `dist/FrameDeck.exe` + `BUILD.md`）

**官方构建脚本兼容性（2026-11-03 实测）**：`build-windows.ps1`（→ `framedeck.spec`）与 `build-ubuntu-appimage.sh`（→ `framedeck-linux.spec`）**均可直接构建本次改造后的项目**——两个 spec 都用 `os.walk("resources")` 整树收集，`resources/i18n/` 九个语言文件自动入包（Windows onedir 实构建验证：全部落位于 `_internal/resources/i18n/`，冒烟通过）；i18n/scrub 零新增第三方依赖，requirements 文件无需改动；新增代码无 3.10 不兼容语法。**注意**：构建前若存在旧的 `.venv-build`（如 Python 3.13 的），需先删除再跑脚本，否则脚本会复用旧 venv 并在 `pip install -r` 阶段因版本 pin（pyqtdarktheme==2.1.0 等）失败。

> **2026-11-03 发布裁剪**：应发布者要求，**两个官方构建脚本已从本包移除**（`build-windows.ps1` / `build-ubuntu-appimage.sh`），3 个 spec 保留。等价的手动构建命令已写入 `BUILD.md` 方式 A；需要一键脚本时从原版仓库或旧工作区取回即可。

---

## 三、架构关键约束（改代码前必读）

这些是本次施工中用真实事故换来的结论：

1. **数据键与显示串严格分离**。`STATUS_LIST` 的 `value`（hld/rev/vwd…）、`REVIEW_TYPES` 的 value、cache_status 六值等是落盘/匹配用的内部键，**永远不译**。`comboboxs.py:477` 按中文 `"已查看"` 匹配默认值——显示串与匹配点必须同批同字改。
2. **cache_status 链路（L-08）**：6 个值分布在 4 个写入点（`playlist.py`）+ 1 个比较点 + 1 个默认值（`widgetItems.py:169/171`）+ 1 条测试断言。验收用 **grep 计数**（「已缓存」必须恰为 2 处——其中一条完成路径平时不走，漏改界面看不出来）。
3. **`player.frame_count` 是 @property，`reader.frame_count` 是方法**。scrub 功能曾因混用两者导致 `int()` TypeError 被 Qt 静默吞掉（症状：拖拽完全无反应，只有 crash log 有记录）。
4. **孪生常量要一起改**：scrub 曾漏改第二处 `FRAME_DRAG_PIXELS_PER_FRAME` 引用，第一处改了、第二处 NameError。
5. **HUD/状态标签是映射不是字面量**：`viewer.py:194` 附近的 HUD 标签 dict（FPS→帧率等）已包 `tr()`；`playback/stats.py` 数据层键保持全 ASCII（实测验证过）。
6. **Radius/粗细 五点锁（L-03）**：`viewer.py:453/772/781/804` + `labels.py:320` 的比较值必须同字，否则「点橡皮擦→标签跳回英文」。
7. **f-string 静态段不能内嵌 tr()**：模板必须转 `tr("EN {0}").format(...)` 形态；中文无复数，`{1}` 这类**语法占位符**（英文 s 后缀）在中文里必须输出空串。
8. **AST 的 col_offset 是 UTF-8 字节偏移**——写代码改写脚本处理含中文的行时必须换算成字符偏移，否则切片错位。
9. **QSS 段（主窗口 779 行起）零触碰**：`setObjectName` 被误译会让整个界面掉回无样式裸控件。
10. **LOGGER 日志、`resolution`/`container_format` 等落盘字段值禁译**（完整清单见规范 §4.1 与 §9）。

---

## 四、开发过程事故记录（教训沉淀）

| # | 事故 | 根因 | 对策 |
|---|---|---|---|
| 1 | 状态下拉默认值静默失效风险 | 显示串 `"Viewed"` 被用作匹配条件 | 建立「匹配点同批改」规则 + N-04 元规则（改词条必须全文回搜中文词） |
| 2 | 同一控件两个中文名 | 遮幅下拉 tooltip「影院遮幅」/状态栏「画幅遮罩」 | D-20 改「遮幅」，全族同根；方法论：**盘问“这个控件一共有几处文案”** |
| 3 | `已导出 3 条笔记s到` | 中文保留了英文复数占位符输出 | 规范新增「语义占位符 vs 语法占位符」 |
| 4 | `On Hold` 译「暂停」与播放控制撞词 | 术语表单词条目各自正确 | 新增 N-01（状态词禁与播放动词共用汉字）+ N-03 三条件判据 |
| 5 | scrub 拖拽无反应（用户实测） | ① 漏改孪生常量 → NameError；② 单素材路径 `playlist_entries` 为空直接 return；③ `reader.frame_count` 方法形态当属性用 → TypeError | 三次修复；最终靠 **用户跑 scrub-debug.log 诊断埋点** 定位到 ③ |
| 6 | 语言文件重刷丢手工键 | `fstring_format.py` 重建而非合并 | 改为 merge 模式 |
| 7 | `git checkout -- .` 抹掉未提交的迁移脚本 v2 | 回滚范围包含脚本自身 | 教训：**先提交工具脚本，再回滚源码** |

**最重要的方法论结论**：**QtTest 离屏事件模拟通过 ≠ 真机可用**。本机无显示器环境时，对交互类功能应直接在交付版里埋开关式诊断日志（本次 `scrub-debug.log` 模式），让用户跑一次即可精确定位卡在哪一层——这个模式值得复用。

---

## 五、验证状态与遗留事项

### 5.1 已验证 ✅
- 全量静态验收 `check_l10n.py --strict`：FAILURES = 0
- 撞词回搜（暂停/打开/撤销/移除/删除/丢帧计数）：全过
- cache_status 计数判据：全过
- scrub 双路径 QtTest 端到端：播放列表模式 + 单素材模式 seek 序列逐帧连续
- 语言实时切换三轮往返（zh↔en↔zh）：菜单、Language 标签全部实时跟随
- 9 语言文件：键集一致、占位符零漂移、运行时 tr() 冒烟通过；zh_TW 经 OpenCC 幂等质检 0 条残留简体
- 源码与 exe 离屏冒烟（进程稳定存活、无 traceback）

### 5.2 未实机验证（本机无显示器，需在有 PySide6 + CJK 字体的机器上目检）
1. 主窗口工具栏三状态标签与按钮是否挤压（重点：`遮幅关闭` 86px 下拉）
2. PDF 导出：中文无方块、**长评论换行后结尾是否被截断**（`pdfreport.py` 的 `row_height > rect.bottom()` 丢弃路径——换字体后度量已变，最高风险项）
3. HUD 中文浮层宽度（Consolas→fallback 行高变化）
4. 状态下拉默认值：打开提交评审对话框，**默认必须是「已查看」**（显示「待开始」= 静默失效）
5. 评论侧栏三按钮行（跳转到帧/标记已解决/删除）300px 内是否放得下
6. CI 环境跑 `test_pdf_report` 需装 `fonts-noto-cjk`，否则文本断言因缺字形假红

### 5.3 已知边界（非缺陷）
- 约百个 f-string 静态片段（状态栏拼接消息的半段等）未包 tr()——**中文/繁体显示完全正常**，仅切英文时这些片段仍是中文，可重跑迁移工具链增量补齐
- `recaps.py` 的 `评审类型：Comment`：`sg_review_type` 是英文枚举值，刻意不加映射（Q7 裁决）
- `Auto`（色彩状态标签）、`Unknown size`/`Load to read metadata`（落盘字段）刻意保留英文
- 六语言（ja/ko/ru/fr/de/es）长句偏直译，可按用户反馈单点修订

---

## 六、日常操作速查

```bash
# 开发运行（需先装 requirements-windows.txt）
python main.py

# 构建单 exe（Python 3.13 venv，详见 BUILD.md）
.venv-build/Scripts/python -m PyInstaller --noconfirm --clean framedeck-onefile.spec

# 静态汉化验收
python doc/l10n/check_l10n.py --baseline d3d8497 --strict

# 语言切换持久化位置
QSettings("FrameDeck", "FrameDeck") 的 "i18n/language" 键

# 拖拽灵敏度调整
constants/__init__.py → FRAME_DRAG_PIXELS_PER_FRAME（默认 10，越小越灵敏）
```

**新增 UI 文案的正确姿势**：代码里写 `tr("English source string")`，然后向 `resources/i18n/*.json` 添加对应键值对（zh_CN 必加，其余按需；缺失键回落 zh_CN，en_US 回落键原文）。
