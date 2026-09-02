# 《翰林院》学者论文全生命周期 Agent

> **太史令主控堂 · 七司一堂**：从选题到投稿，一篇论文一个工程，几个文件全包揽。
> 零第三方依赖，纯 Python 标准库，断点续传 + 事件溯源 + 引用纪律硬门。

## 缘起（两次升级）

1. 英语研究课老师：论文/期刊格式问题 Agent 搞不定 → 不服，做了【翰林·修文卷】格式修复引擎（先武器后军团）
2. 深度对照 GitHub 八大权威学术 Agent 架构后升级：**排版只是最后一公里，真正的痛是全局**——于是有了这台全生命周期 Agent。

## 架构（参照八大自然仓库）

| 仓库原型 | 偷师 |
| --- | --- |
| seele-scholar-agent | 生命周期流水线、8 类确定性质量门、ClaimEvidenceBinding |
| AcadClaw | 六角色分工、run.json+events.jsonl 事件溯源、断点续传 |
| research-paper-lifecycle-skills | 42 技能全集、preflight / simulate-reviewers |
| academic-paper-writing-skill | 证据优先五原则、capability 路由 |
| scholar-skill | 目录宪法、无向量 RAG、中文定稿→翻译闭环 |
| academic-research-skills | references.bib 唯一合法引用源、reviewer 只读 |
| DeepResearcher | prompt 分层、阶段化 IMRaD |
| deepseek-harness + THUDM 系 | Everything is a Plugin、官方权威背书的 skill |

## 七司一堂

```
①立题 ②采风 ③定纲(✓) ④著书 ⑤磨镜(✓) ⑥铸卷 ⑦呈堂
│      │      │      │      │      │      │
proposal bib  outline draft review final submission
               └ 人工确认点     └ 人工确认点
```

- ①②③ = 选题、文献、大纲（提纲必须过 OutlineQualityGate）
- ④⑤ = 分节写作、审稿循环（引用门违规直接阻断，杜撰引用无法混过）
- ⑥ = 排版交付（将 GBT 7713.1-2025 规则引擎接入，产出合规报告+内容指纹）
- ⑦ = 投稿（preflight 预检验收）

## 快速开始

```bat
python -m hanlinyuan init mythesis "我的论文标题"

:: 1) 把文献写进 papers\mythesis\bib\references.bib（bibtex 格式）
:: 2) 一路跑，出问题就停在当前阶段

python -m hanlinyuan run mythesis

:: 查看状态/日志尾部
python -m hanlinyuan status mythesis
```

**中断无损**：任何一步挂了，修复后重跑即可——已完成的阶段记录在 run.json + events.jsonl，不会重跑也不会丢。

## 已经实现的硬能力

- ✅ 状态机七司流水线（可 --stop-at 停在任一步）
- ✅ 事件溯源 events.jsonl（append-only，可审计）
- ✅ 断点续传 reconcile（超时/失败自动对账）
- ✅ 引用可信门：r/doc 里每处 `[cite:key]` 必须命中 bib 库，否则阻断
- ✅ content fingerprint SHA-256：证明只改格式不动字
- ✅ 合规报告 + preflight checklist
- ⏳ AI 深度写作（待接 DeepSeek：著书司自动分节起草 + 磨镜司 LLM 审稿）

## 目录宪法

```
papers/<slug>/
  run.json / events.jsonl    状态快照 / 事件溯源
  proposal.md outline.md synthesis.md
  bib/references.bib         唯一合法引用来源
  notes/ draft/ final/ submission/ archive/ reports/
```

## 开源协议

MIT License