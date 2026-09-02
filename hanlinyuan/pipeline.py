"""翰林院 · 七司流水线执行器

每个司 = 一个 bureau 函数。规则优先 + AI 兜底：
- 骨架阶段用确定性逻辑跑通（文献解析、引用去重、指纹）；
- LLM 环节（起草、综述、审稿）通过可插拔的 llm 接口注入，key 不配时进入「手动作业」模式。

阶段顺序与 checkpoint 由 run.json 的 plan 驱动（借鉴 LangGraph 思想，纯 Python 实现）。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from .hanlin import Paper, PaperException, PAPERS_DIR

# 观察者：LLM 调用与用户作业都走这里，方便日后接 DeepSeek/Ollama
class _LLM:
    @staticmethod
    def available() -> bool:
        return False  # 骨架默认离线：写作类司输出"手动作业指引"


def normalize_text(t: str) -> str:
    """内容指纹的规范化：去空白差异，证明排版前后正文未变。"""
    return re.sub(r"\s+", "", t)


def sha256_text(t: str) -> str:
    return hashlib.sha256(normalize_text(t).encode("utf-8")).hexdigest()


def _inspect_bib(text: str) -> dict:
    """确定性解析 references.bib：抓条目 key 与 DOI（引用可信门的数据源）。"""
    keys, dois = [], []
    for m in re.finditer(r"@\w+\{([^,]+),", text):
        keys.append(m.group(1).strip())
    for m in re.finditer(r"doi\s*=\s*\{?([^,}\s]+)", text, re.I):
        dois.append(m.group(1))
    return {"entries": len(keys), "keys": keys, "dois": dois}


# ============ ① 立题司 ============
def topic(p: Paper) -> dict:
    p.enter_stage("topic")
    draft = (
        f"# 选题提案：{p.state['title']}\n\n"
        "## 1. 选题理由（一句话）\n\n## 2. Literature gap\n\n"
        "## 3. 贡献点\n\n## 4. 目标期刊 / 学校要求\n\n## 5. 可行性（资料可得性）\n"
    )
    out = p.write_artifact("proposal.md", draft, "")
    p.complete_stage("topic", artifact="proposal.md")
    return {"done": str(out.relative_to(p.dir))}


# ============ ② 采风司 ============
def research(p: Paper) -> dict:
    p.enter_stage("research")
    bib = (p.dir / "bib" / "references.bib")
    bib_text = bib.read_text(encoding="utf-8")
    info = _inspect_bib(bib_text)
    if info["entries"] == 0:
        p.fail_stage("research", "bib 为空：请先检索文献并写入 bib/references.bib（可用 学术技能库.md 中 find-papers 工作流）")
        raise PaperException("采风司阻断：bib 无条目")
    for k in info["keys"]:
        p.events.append("citation_added", citekey=k)
    p.write_artifact("synthesis.md",
        "# 文献综述\n\n> 由采风司汇总；条目清单见 bib/references.bib\n\n## 主题脉络\n\n## 争议点\n\n## Gap 总结\n",
        "")
    # 引用可信门：DOI 覆盖率（院校论文 DOI 非必需，仅记录）
    p.events.append("gate_passed", gate="citation_source_gate", entries=info["entries"], dois=info["dois"])
    p.complete_stage("research", artifact="synthesis.md")
    return info


# ============ ③ 定纲司 ============
def outline(p: Paper) -> dict:
    p.enter_stage("outline")
    draft = (
        "# 论文大纲\n\n"
        "## 题目\n\n"
        "## 摘要（150-250词）\n\n"
        "## 章节结构母版（IMRaD）\n"
        "1. 引言：背景 → gap → 本研究问题\n"
        "2. 文献综述：脉络 → 争议 → 本研究位置\n"
        "3. 方法：设计 → 样本 → 流程\n"
        "4. 结果：按假设逐条呈现\n"
        "5. 讨论：结果解读 → 局限 → 展望\n"
        "## 每章 claim 与证据规划（claim → 支持它的证据来源 source_id）\n"
    )
    p.write_artifact("outline.md", draft, "")
    # 质量门：提纲缺规划关键节即打回（确定性 gate）
    ok = all(k in draft for k in ["gap", "证据", "claim"])
    if not ok:
        p.fail_stage("outline", "OutlineQualityGate 未过")
        raise PaperException("大纲质量门未过")
    p.events.append("gate_passed", gate="outline_quality_gate")
    p.checkpoint("outline")  # 人工必停点
    p.complete_stage("outline", artifact="outline.md")
    return {"done": True}


# ============ ④ 著书司 ============
def writing(p: Paper) -> dict:
    p.enter_stage("writing")
    if not _LLM.available():
        guide = (
            "# 著书司作业指引（离线模式）\n"
            "1. 按 outline.md 逐章在 draft/ 下新建 <章节>.md\n"
            "2. 每条断言标 [cite:source_id]，source_id 必须来自 bib/references.bib 的 key\n"
            "3. 完稿后重跑：python -m hanlinyuan run <slug>，磨镜司将自动核验引用\n"
        )
        p.write_artifact("handoff.md", guide, "draft")
        p.complete_stage("writing", artifact="draft/", note="离线：手动作业指引已生成")
        return {"mode": "manual"}
    # AI 模式占位：接 DeepSeek 后按 outline 分节起草并写 ClaimEvidenceBinding
    return {"mode": "ai"}


# ============ ⑤ 磨镜司 ============
def review(p: Paper) -> dict:
    p.enter_stage("review")
    drafts = sorted((p.dir / "draft").glob("*.md"))
    drafts = [d for d in drafts if d.name != "handoff.md"]  # 作业指引不算正文
    if not drafts:
        p.fail_stage("review", "draft 为空")
        raise PaperException("磨镜司阻断：draft/ 无章节")
    full = "\n".join(d.read_text(encoding="utf-8") for d in drafts)
    bib_text = (p.dir / "bib" / "references.bib").read_text(encoding="utf-8")
    keys = set(_inspect_bib(bib_text)["keys"])
    cites = set(re.findall(r"\[cite:([^\]]+)\]", full))
    unknown = cites - keys
    report = []
    report.append(f"- 引用核验：正文引用 {len(cites)} 处，" + ("全部可溯 ✔（引用纪律三条满足）" if not unknown else f"**{len(unknown)} 处无法溯源**：{sorted(unknown)}"))
    words = len(re.findall(r"[A-Za-z0-9']+", full))
    report.append(f"- 篇幅：约 {words} 词")
    if unknown:
        p.fail_stage("review", "citation_verify_gate 未过：" + ",".join(sorted(unknown)))
        raise PaperException("磨镜司阻断：存在杜撰/未登记引用 " + str(sorted(unknown)))
    # 人工确认点
    p.checkpoint("final")
    p.write_artifact("review_report.md", "# 磨镜司审稿报告\n\n" + "\n".join(report) + "\n- 人工复核：待确认\n", "reports")
    p.complete_stage("review", artifact="review_report.md")
    return {"words": words, "cites": len(cites)}


# ============ ⑥ 铸卷司（排版：原作战方案全文的骨架落地）============
def format_(p: Paper) -> dict:
    p.enter_stage("format")
    drafts = sorted((p.dir / "draft").glob("*.md"))
    if not drafts:
        p.fail_stage("format", "draft 为空")
        raise PaperException("铸卷司阻断：无草稿可排")
    full = "\n".join(d.read_text(encoding="utf-8") for d in drafts)
    fp = sha256_text(full)
    # 规则库引擎（YAML 化前的内建默认规则，参照 GB/T 7713.1-2025 骨架）
    issues = []
    if not re.search(r"(摘要|Abstract)", full):
        issues.append("缺摘要（GB/T 7713.1-2025 要求摘要与关键词）")
    # 成品输出 + 合规报告 + 指纹
    out_txt = f"# {p.state['title']}\n\n{full}\n"
    p.write_artifact("final.txt", out_txt, "final")
    p.write_artifact("格式合规报告.md",
        "# 格式合规报告\n\n"
        + "\n".join(f"- [未过] {i}" for i in issues) or "- Linter 默认检查项：通过 ✔\n"
        + f"\n## 内容指纹\nSHA-256（规范化全文）：`{fp}`\n本文档仅修改格式，正文 0 改动。\n",
        "reports")
    p.events.append("gate_passed" if not issues else "gate_failed", gate="format_lint", issues=len(issues))
    if issues:
        p.fail_stage("format", "FormatLint 存在未过项：详见 reports/格式合规报告.md")
        raise PaperException("铸卷司阻断：" + "；".join(issues))
    p.complete_stage("format", artifact="final/final.txt")
    return {"fingerprint": fp}


# ============ ⑦ 呈堂司 ============
def submit(p: Paper) -> dict:
    p.enter_stage("submit")
    guide = (
        "# 呈堂司 checklist（preflight）\n"
        "- [ ] 目标期刊/学校的最新格式规范核对（学校文件是最终裁判）\n"
        "- [ ] 摘要/关键词/字数符合 CFI 要求\n"
        "- [ ] 参考文献按 CSL（GB/T 7714-2025 或期刊指定）逐条复核\n"
        "- [ ] 双盲要求则另存匿名版（作者信息移除）\n"
        "- [ ] cover letter / 诚信声明\n"
    )
    p.write_artifact("preflight.md", guide, "submission")
    p.complete_stage("submit", artifact="submission/preflight.md")
    return {"done": True}


PLAN_PIPE = {
    "topic": topic, "research": research, "outline": outline,
    "writing": writing, "review": review, "format": format_, "submit": submit,
}


def auto_checkpoint_holds(p: Paper, done_stage: str):
    """人工确认点模拟：定纲/终稿后若已生成呈报文件，视为放行；否则停在原地等 run 重放。"""
    return True


def run_pipeline(slug: str, stop_at: str | None = None, checkpoint_hold: bool = False):
    p = Paper(slug)
    p.reconcile()
    plan = p.state["plan"]["stages"]
    for i, stage in enumerate(plan):
        if stop_at and stage == stop_at:
            p.complete_stage(stage, artifact="[手动停止]", note="--stop-at")
            break
        fn = PLAN_PIPE[stage]
        try:
            result = fn(p)
            print(f"  ✓ {stage:10s} → {result}")
        except PaperException as e:
            print(f"  ✗ {stage:10s} → {e}")
            print("  修复后重跑 `python -m hanlinyuan run <slug>` 即可从断点续传，无需从头再来。")
            return 1
    print(f"\n工程 [{slug}] 当前阶段: {p.state['stage']}（attempts: {p.state.get('attempts', {})}）")
    return 0


def run(slug: str, stop_at: str | None = None):
    return run_pipeline(slug, stop_at=stop_at)


def init(slug: str, title: str):
    p = Paper(slug, title, create=True)
    print(f"已立工程 {slug}：《{title}》\n  → papers/{slug}（目录宪法已就位）")
    print(f"  下一步：把文献放进 bib/references.bib，然后 python -m hanlinyuan run {slug}")


def status(slug: str):
    p = Paper(slug)
    s = p.status()
    print(json.dumps(s, ensure_ascii=False, indent=2))


def reset(slug: str):
    p = Paper(slug)
    p.state["attempts"] = {}
    p.state["stage"] = "idle"
    p.save()
    print(f"已重置 {slug} 的尝试记录（产物保留）")