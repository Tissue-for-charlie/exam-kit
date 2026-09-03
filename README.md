# exam-kit

> 把散落的期末课件，变成能背、能刷、能看懂依赖关系的三份离线复习工具。

`exam-kit` 面向需要整理课程资料的学生：它把 PPT、Word、PDF 和图片交给 Agent 阅读，再输出三份可以保存、打印、离线打开的 HTML。

| 产物 | 你拿它做什么 |
|---|---|
| [复习提纲](showcase/output/outline.html) | 按章背诵，四色重要度标签，章末折叠自测 |
| [复习题](showcase/output/quiz.html) | 逐题作答、自动批改、查看解析、重刷错题 |
| [知识图谱](showcase/output/graph.html) | 查看章节、知识点和前置依赖，拖拽缩放探索 |

> 上面的链接指向构建后生成的公开 derived demo。先运行下面的命令即可得到它们。

## 3 分钟看见结果

```bash
python -m pip install -r requirements.txt
python showcase/build_showcase.py
```

然后用浏览器打开 `showcase/output/` 下的三个 HTML。构建器不联网、不调用模型，也不读取你的课程目录；它只渲染仓库内的公开演示数据。

验证摘要位于 `showcase/verification.json`，只包含产物大小、哈希和数量统计。

## 装完后这样说

将这个仓库作为 Agent Skill 安装后，可以直接说：

```text
请用 exam-kit 处理这门课的 PPT、PDF 和 Word 资料：先扫描并按章节分组，再提取文字；随后生成知识骨架和原题清单；最后输出复习提纲、复习题和知识图谱三份离线 HTML。原题请保留来源，无法从资料确认的内容请明确标注。
```

常见触发方式：

- “帮我整理这门课的期末复习资料。”
- “根据这些课件生成复习提纲和自测题。”
- “把这几份 PDF、PPT 和板书照片按章节整理。”
- “划出必考点，并给每个知识点配题。”
- “做一张这门课的知识依赖图。”

## 它实际怎么工作

```text
课程资料
  → scan.py：扫描并按章节分组
  → extract.py：提取文字，记录图片供多模态 Agent 阅读
  → Agent：整理知识骨架、抽取原题、补齐题目并标注来源
  → render_outline.py / render_quiz.py / render_graph.py
  → 三份单文件 HTML
```

题目优先使用资料里的例题、课后题和真题；资料覆盖不到的部分才生成新题。每题标记 `original` 或 `generated`，原题保留来源说明。

## 公开 demo 与真实课程的边界

`showcase/fixture/course.json` 是独立措辞的 **derived demo**，不是任何真实课程的副本。它不包含真实课件、原图、连续课件原文、教师/学校/学生信息或本地路径。

公开构建只证明“已准备的知识骨架和题库 → 三份离线 HTML”的确定性渲染链路。真实课程的完整流程由 Agent 根据用户提供的资料完成；`showcase/build_showcase.py` 不会读取真实课程目录，也不会自动脱敏后发布资料。

## 处理真实资料

对真实课程资料，Agent 会按以下路径工作：

```bash
python <skill目录>/scripts/scan.py "<资料目录>"
python <skill目录>/scripts/extract.py "<资料目录>"
# Agent 读取 .final_prep 中间结果并生成 knowledge_skeleton.json / questions.json
python <skill目录>/scripts/render_outline.py "<资料目录>"
python <skill目录>/scripts/render_quiz.py "<资料目录>"
python <skill目录>/scripts/render_graph.py "<资料目录>"
```

首次使用安装：

```bash
python -m pip install -r requirements.txt
```

图片不做 OCR：图片和 PPT 内嵌图片会记录路径，交给支持视觉输入的 Agent 阅读。传统二进制 `.ppt` 可能无法由 `python-pptx` 读取，建议先转换为 `.pptx`。扫描 PDF 若没有文字层，需要由 Agent 直接阅读。

## 安全边界

- 不自动上传课程资料，不调用外部 API。
- 不自动删除或覆盖真实资料文件。
- 公开 showcase 不接收任意输入路径，避免误读私人目录。
- `original` 只用于资料中确实存在且可独立作答的题目。
- 公开 fixture 和生成 HTML 会检查常见邮箱、手机号、绝对路径、秘密字段和外部网络依赖。
- 自动检查不是版权授权替代品；真实课件能否公开仍由使用者确认。

## 文件结构

```text
SKILL.md                         # Agent 工作流、JSON 契约和触发说明
scripts/                         # 扫描、提取和三种 HTML renderer
showcase/fixture/course.json     # 独立措辞的公开演示数据
showcase/build_showcase.py       # 确定性构建和静态安全检查
showcase/expected/               # verification.json 结构契约
tests/                           # 构建回归和可选浏览器验收
```

## 验证

```bash
python -m py_compile showcase/build_showcase.py scripts/*.py tests/*.py
python showcase/build_showcase.py
python -m unittest discover -s tests -v
python -m json.tool showcase/fixture/course.json
python tests/browser_showcase.py
```

浏览器验收只使用本机已有的 Playwright/Chromium，不会自动下载浏览器；环境没有浏览器时会明确报告 `unavailable`。

## License

[MIT](LICENSE)
