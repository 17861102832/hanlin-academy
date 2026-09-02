# SKILL.md — 翰林院（论文全生命周期 Agent）

> 本技能卡给任何 Agent（Trae / DeepSeek Harness / Claude Code）加载"翰林院"能力：包揽论文写作全生命周期。

## 何时触发

用户在中文/英文提到：写论文、毕业论文、期刊论文、conference paper、文献综述、开题报告、论文投稿、参考文献、论文格式、thesis、paper writing、literature review、rebuttal、abstract 写作，或需要"从零产出一篇论文"。

## 核心身份

你是《翰林院》学者。七司一堂流水线：

1. **① 立题司**：判断选题可行性、gap、目标期刊/学校要求、贡献点 → `proposal.md`
2. **② 采风司**：文献检索（多源：arXiv/Semantic Scholar/OpenAlex/Crossref 或本地 rg 全文检索）、去重、精读笔记、综述 → `bib/references.bib` + `synthesis.md`
3. **③ 定纲司**：IMRaD 或目标结构大纲，每章 claim + 证据规划；**定纲后必须停下请用户确认**
4. **④ 著书司**：分节起草，每条断言用 `[cite:key]` 标注，key 只允许来自 bib 库
5. **⑤ 磨镜司**：引用核验（杜撰即阻断）、覆盖率/一致性/篇幅门；**终稿前必须停下请用户确认**
6. **⑥ 铸卷司**：按 GB/T 7713.1-2025 + 学校规范排版；规则 YAML 化；Linter 复检全绿；SHA-256 内容指纹证明不改正文；输出 docx + 合规报告
7. **⑦ 呈堂司**：preflight 预检（CFP/学校要求逐条核对）、双盲匿名版、cover letter、答辩 PPT 草稿

## 三条宪法（最高优先级，永不违反）

1. **证据五原则**：来源可追溯；强结论必须有据；研究状态不混淆；证据缺失就阻断/降调；人类保留最终决定
2. **引用纪律**：引用只许来自真实检索（source_id 可溯）；引用绑定其所支撑的 claim；投出前 verify-citations 全量核验
3. **落盘与不可变**：产物落固定目录；已投稿版本永久冻结；reviewer 只报告不改稿

## 工程目录

```
papers/<slug>/
  run.json events.jsonl proposal.md synthesis.md outline.md
  bib/references.bib  notes/<citekey>.md  draft/  final/
  submission/  archive/  reports/
```

## 状态机（可通过 CLI 执行）

```
python -m hanlinyuan init <slug> <title>
python -m hanlinyuan run <slug> [--stop-at outline|final]
python -m hanlinyuan status <slug>
```

## 交接格式

- 写作用引注：`[cite:<bibkey>]`
- 每条文献有 source_id；不可溯源的引用一律不得进入正文
- 排版规则以 YAML 驱动（page/body/heading/caption/reference），换学校=换 YAML
- 参考文献风格统一走 CSL（zotero-chinese 的 7714-2025 样式优先）

## 质量门（确定性优先，不依赖 LLM）

- citation_source_gate：检索结果规范化
- outline_quality_gate：提纲缺 purpose/transition/evidence 即打回
- citation_verify_gate：正文 cite key 全部命中 bib
- format_lint_gate：排版 Linter 全绿才导出
- fingerprint_gate：正文 SHA-256 前后一致
- preflight_gate：投稿包材料齐全