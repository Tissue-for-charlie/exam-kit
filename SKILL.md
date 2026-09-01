---
name: finals-prepper
description: 期末备考 Skill。当用户上传/提供课程资料（PPT、Word、PDF、图片、手机拍的板书照片），想生成复习提纲、复习题、知识图谱，或者说"期末复习""期末考""备考""帮我整理复习提纲""给我出复习题""划重点""做复习资料""这门课怎么复习"等时使用。把老师给的课件和复习资料转成三份可打印、可自测的 HTML：复习提纲（重要度标签 + 折叠自测）、复习题（交互答题 + 一键批改 + 掌握度报告）、知识图谱（交互式依赖关系图）。题目优先复用资料里已有的原题（例题/课后题/真题），资料不足时再按知识点生成。**不要 undertrigger**——用户说要复习某门课、整理资料或出题而你不调本 Skill，就是把课件原文甩给用户，帮不到备考。
---

# 期末备考 Skill（finals-prepper）

把老师给的课件和复习资料变成备考利器。输入是散乱的 PPT / Word / PDF / 图片，输出三份单文件 HTML：

| 产物 | 用途 | 形态 |
|---|---|---|
| **复习提纲** | 考前背诵 | 按章分块，知识点打四色重要度标签，每章末尾折叠自测 |
| **复习题** | 自测检验 | 客观题为主 + 大题，交互答题、一键批改、逐题解析、按知识点掌握度报告 |
| **知识图谱** | 建立体系 | 章节→知识点树 + 依赖虚线 + 枢纽概念星标，可拖拽缩放 |

## 核心原则

1. **题目优先用资料原题**。PPT 里的例题、Word 里的课后题、PDF 里的历年真题，都是最贴合老师考法的题。提取时单独把资料里的题抽出来，命题时优先复用；只有原题覆盖不到的知识点或题量不够时，才由 AI 生成补齐。所有题都要标 `source`：`original`（原题，附出处）或 `generated`（AI 生成）。
2. **脚本干机械活，AI 干智力活**。脚本只做扫描分组、文字提取、HTML 渲染、缓存；通读理解、提炼骨架、命题、写解析由 AI 完成。
3. **图片交给 AI 直接读**。手机拍的板书、截图等图片不做 OCR，直接把图片路径喂给多模态模型理解，内容并入提纲和题。
4. **提纲是"背的"，不是"读的"**。每条知识点控制在 1-2 句话，用「是什么 → 为什么重要 → 怎么用/怎么考」的结构，不做长篇叙事。

## 命令路由

检查用户意图：
- 用户给了**资料目录或具体文件** + 复习意图 → 走默认流程（下）。
- 用户只想**出题/复习某一章**（没说从零整理）→ 也走默认流程，但产物只强调复习题那一份。
- 用户问"**只想要提纲**"或"**只想要题**"或"**只想要图谱**" → 走默认流程后只交付对应份，其余跳过。

## 默认流程

### Phase 0 · 扫描 + 章节分组（脚本）

```bash
python <skill目录>/scripts/scan.py <资料目录>
```

产出 `<资料目录>/.final_prep/manifest.json`：

```json
{
  "course": "课程名（取目录名，或稍后由 AI 校正）",
  "root": "资料目录绝对路径",
  "chapters": [
    {
      "id": "ch1",
      "label": "章节名（先用文件名/目录名推断）",
      "files": ["该章源文件绝对路径列表"]
    }
  ]
}
```

章节分组规则（写死在 scan.py 里）：优先按子目录分组（每个子目录=一章）；无子目录时用文件名正则（`第\d+章`、`Chapter\s*\d+`、`ch\d+`、`\d+_` 前缀）分组；都匹配不上则全部归为单章 `ch1`，label 留空由 AI 补。

### Phase 1 · 提取文字（脚本）

```bash
python <skill目录>/scripts/extract.py <资料目录>
```

读 manifest，对每个文件按类型提取：
- `.pptx` → 每页文字 + 表格 + 备注，**同时把内嵌图片导出到 `.final_prep/media/`**（python-pptx）
- `.docx` → 段落 + 表格（python-docx）
- `.pdf` → 每页文字（pypdf）
- 独立图片（`.png/.jpg/.jpeg/.gif/.bmp/.webp`）和 PPT 内嵌图片 → **不做 OCR**，把绝对路径记入 bundle 的 `images` 列表，供 AI 直接读

产出 `.final_prep/chapters/<章id>.json`（text bundle）：

```json
{
  "chapter_id": "ch1",
  "label": "章节名",
  "text": "合并后的正文文字（含表格，用 | 分隔单元格）",
  "images": ["图片绝对路径"]
}
```

### Phase 2 · AI 通读 → 知识骨架 + 原题清单（AI）

读每章 bundle 的 `text`，图片用 Read 工具逐张看。然后写两个 JSON。

**（1）知识骨架 `.final_prep/knowledge_skeleton.json`**：

```json
{
  "course": "课程全名",
  "chapters": [
    {
      "id": "ch1",
      "label": "章节名",
      "summary": "本章一句话主旨",
      "kcs": [
        {
          "id": "ch1.kc1",
          "label": "知识点名（精炼，可背）",
          "importance": "must | key | freq | info",
          "content": "1-2 句话：是什么 → 为什么重要 → 怎么考；**关键术语用 **术语** 标记**，渲染时加粗 + 主题蓝高亮（每条 content 至少标 1-3 个核心术语）",
          "deps": ["依赖的知识点 id，可为空数组"],
          "is_hub": false
        }
      ],
      "selftests": [
        { "q": "章节自测题（1-2 个，客观题，短）", "a": "参考答案" }
      ]
    }
  ]
}
```

- `importance` 四档：`must`（必考，红）、`key`（重点，橙）、`freq`（高频，蓝）、`info`（了解，灰）。占比大致 must/key 合计 ≤40%，别全打重点。
- `deps` 只填**真实前置依赖**（要先懂 A 才能懂 B），用于画图谱连线；没有就空数组。
- `is_hub`：能串起多个知识点的枢纽概念标 true（图谱里加星标）。

**（2）原题清单 `.final_prep/source_questions.json`**：

通读时把资料里出现的**现成题目**单独抽出来（例题、课堂练习、课后习题、往年真题、作业题）。结构：

```json
{
  "questions": [
    {
      "chapter_id": "ch1",
      "type": "choice | multi | tf | fill | short | calc | essay",
      "question": "题干原文",
      "options": ["仅选择/多选有，字符串数组"],
      "answer": "资料里给了答案就填（格式同 Phase 3），没给就 null",
      "source_ref": "来源文件名/页码，如「第3章课件.pptx 第12页」"
    }
  ]
}
```

只收**题目本身完整、可独立作答**的题；只给了题目没给答案的也收（AI 后面补答案），但题干残缺的不要硬凑。

### Phase 3 · 命题（AI）

写 `.final_prep/questions.json`。规则：

1. **优先原题**：从 `source_questions.json` 按章节取题，标 `source: "original"`、`source_ref` 照抄。原题答案缺失的，AI 补答案并保证正确。
2. **缺额生成**：统计每章题目，不足"每个知识点 ≥1 题、整章 ≥8 题"的，按知识点生成补齐，标 `source: "generated"`。
3. **题型配比**：客观题为主（choice/multi/tf/fill ≈ 70-80%），大题按学科判断——文科出 short/essay，理工科出 calc，概念混合课可少量 short。
4. choice 正确答案 A/B/C/D **均匀分布**（各字母次数差 ≤1），干扰项对应真实误解。
5. 每题带 `explanation`（解析）和 `pitfall`（易错提醒）。
6. 每题标 `difficulty`（易/中/难）：`easy`=直接记忆/概念题，`medium`=需理解辨析，`hard`=综合/易错。难度要拉开，别全 easy。

```json
{
  "chapters": [
    {
      "id": "ch1",
      "questions": [
        {
          "id": "ch1.q1",
          "type": "choice",
          "source": "original | generated",
          "source_ref": "原题出处或空",
          "kc_id": "ch1.kc1",
          "difficulty": "easy | medium | hard",
          "points": 2,
          "question": "题干",
          "options": ["A", "B", "C", "D"],
          "answer": 0,
          "explanation": "解析",
          "pitfall": "易错点"
        }
      ]
    }
  ]
}
```

`answer` 字段按题型：
- `choice`：int 索引（0-based）
- `multi`：int 数组，如 `[0, 2]`
- `tf`：bool，`true`=命题正确，`false`=命题错误
- `fill`：字符串数组，按空顺序，如 `["TCP", "三次握手"]`
- `short` / `calc` / `essay`：字符串，参考答案/要点

写完用 `python -c "import json; json.load(open(...))"` 自检 JSON 合法。

### Phase 4 · 渲染（脚本）

```bash
python <skill目录>/scripts/render_outline.py <资料目录>
python <skill目录>/scripts/render_quiz.py <资料目录>
python <skill目录>/scripts/render_graph.py <资料目录>
```

在 `<资料目录>/` 下产出三份 HTML：

| 脚本 | 产物 | 内容 |
|---|---|---|
| render_outline.py | `<课程名>-复习提纲.html` | 衬线教材风：宋体标题 + 黑体正文，章节标题深蓝渐变实色块 + 大号水印编号，目录卡片化；知识点 H3 带序号圆点 + 四色图标标签（🔥必考/⭐重点/📈高频/👀了解）；**content 里的 **术语** 渲染为深蓝加粗高亮**；**importance=must 的知识点整体用浅红强调框框起**；章末折叠自测（selftests） |
| render_quiz.py | `<课程名>-复习题.html` | 刷题 App 风：深色 header（右上角 ▲/▼ 可折叠顶部栏）+ 统计条/进度条 + 题型 tab + 刷题模式（全部题目/仅错题/仅未答/随机顺序）；单题视图逐题判对错、高亮答案、显示解析与易错点（单选/判断点选项即自动判分）；做错的题自动进「错题集」可重刷；主观题一键看参考答案；「掌握度报告」按知识点聚合得分率标薄弱、以弹窗形式展示；页面隐藏滚动条但保留滚动；Ctrl+P 打印时全部题目+答案+解析展开 |
| render_graph.py | `<课程名>-知识图谱.html` | 左章右知识点布局，`deps` 画依赖虚线，`is_hub` 加星标，可拖拽/缩放/悬停 tooltip |

三份 HTML 均单文件、无外部 CDN 依赖（离线可开），可 Ctrl+P 打印为 PDF。

### Phase 5 · 预览交付

用 present_files 把三份 HTML 一起呈现，第一份放复习提纲。

## 依赖安装

首次使用先装依赖（用当前环境的 Python）：

```bash
pip install python-pptx python-docx pypdf
```

若某个库装不上或某类型文件提取失败，**不阻断流程**——跳过该文件的脚本提取，改用 Read 工具直接读该文件内容补进 bundle 的 `text`。

## 产物管理

- 三份 HTML 输出到**资料目录**下，文件名固定（课程名-复习提纲.html 等）。
- 中间产物（manifest、bundle、骨架、题目 JSON）都在 `.final_prep/`，二次运行命中缓存时直接复用，秒出。
- 不污染资料目录根目录，测试临时文件用完即删。

## 常见问题处理

- **PPT 里图片多、文字少**（老师把内容都做在图里）：脚本提取的文字很少时，`extract.py` 已把 PPT 内嵌图片导出到 `.final_prep/media/` 并记入 bundle 的 `images`——直接用 Read 逐张读这些图片，把图里的知识点读出来补进骨架。独立图片格式的课件同理。
- **章节分组不准**（文件名没有明显章节号）：AI 通读 bundle 后按内容重新划分章节，覆盖 manifest 里的 label，必要时合并/拆分。
- **资料里原题几乎为 0**：说明"资料里没找到现成题目，以下按知识点生成"，仍保证每个知识点有题。
- **PDF 是扫描件**（无文字层）：pypdf 提不出文字，改用 Read 直接读 PDF（多模态），内容并入 bundle。

## 不要做

- 不要照抄参考技能 exampass 的整页 PPT 渲染对照栏、多 Agent 编排——本 Skill 已砍掉这些，保持轻量。
- 不要对图片做 OCR——图片一律交给多模态模型直接读。
- 不要把提纲写成长篇讲解——每条知识点 1-2 句话，能背即可。
- 不要凭空编造原题出处——`original` 题必须真实存在于资料里，`source_ref` 必须真实。
- 不要在没读资料的情况下生成内容——骨架、题目、解析都必须有资料依据。
