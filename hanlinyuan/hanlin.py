"""翰林院 · 太史令主控堂

事件溯源 + 断点续传状态机（借鉴 AcadClaw 的 run.json + events.jsonl 架构）。
零第三方依赖：纯 Python 标准库，双击/命令行即跑。

用法：
  python -m hanlinyuan init <slug> <title>      # 立一项论文工程
  python -m hanlinyuan run <slug>               # 续跑（任一阶段中断后自动对账恢复）
  python -m hanlinyuan status <slug>            # 查看状态与事件日志尾部
  python -m hanlinyuan reset <slug>             # 重置工程（清空尝试记录，产物保留）
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

PAPERS_DIR = Path(__file__).resolve().parent.parent / "papers"

STAGES = ["idle", "topic", "research", "outline", "writing", "review", "format", "submit"]

EVENT_TYPES = {
    "run_created", "stage_entered", "stage_completed", "stage_failed",
    "artifact_written", "gate_passed", "gate_failed", "citation_added",
    "human_approval_requested", "human_approved", "retry", "run_reconciled",
}

# 一次与一个自动断点衔接的默认工作流：判定与写作集（可自写扩展）
DEFAULT_PLAN = {
    "stages": ["topic", "research", "outline", "writing", "review", "format", "submit"],
    "checkpoints": ["outline", "final"],   # 人工确认点：定纲之后、终稿之前
    "max_revisions": 3,
}


class PaperException(Exception):
    pass


class EventLog:
    def __init__(self, path: Path):
        self.path = path

    def append(self, event_type: str, **fields) -> dict:
        if event_type not in EVENT_TYPES:
            raise PaperException(f"未知事件类型: {event_type}")
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": uuid.uuid4().hex[:8], "type": event_type, **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def tail(self, n=10):
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").rstrip().splitlines()
        return [json.loads(x) for x in lines[-n:]]


class Paper:
    def __init__(self, slug: str, title: str = "", create: bool = False):
        self.slug = slug
        self.dir = PAPERS_DIR / slug
        self.run_file = self.dir / "run.json"
        self.events = EventLog(self.dir / "events.jsonl")
        if create:
            if self.dir.exists():
                raise PaperException(f"论文工程已存在: {slug}")
            self._scaffold(title)
        if not self.run_file.exists():
            raise PaperException(f"论文工程不存在，先 init: python -m hanlinyuan init {slug}")
        with self.run_file.open(encoding="utf-8") as f:
            self.state = json.load(f)

    # ---- 目录宪法（借鉴 academic-research-skills 强约束）----
    def _scaffold(self, title: str):
        for sub in ["bib", "notes", "draft", "final", "submission", "archive", "reports"]:
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        (self.dir / "bib" / "references.bib").write_text("% 本库是唯一合法引用来源\n", encoding="utf-8")
        state = {
            "slug": self.slug, "title": title, "version": 1,
            "stage": "idle", "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "plan": DEFAULT_PLAN, "attempts": {}, "artifacts": {},
        }
        self.save(state)
        self.state = state
        self.events.append("run_created", title=title)

    def save(self, state=None):
        if state is None:
            state = self.state
        state["version"] = state.get("version", 0) + 1
        state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with self.run_file.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    # ---- 断点续传核心：启动时对账 ----
    def reconcile(self):
        """恢复超时/失败步骤：幂等重跑是协议，不是口号。"""
        issues = 0
        for stage, at in self.state.get("attempts", {}).items():
            status = at.get("status")
            if status == "running":
                at["status"] = "failed"
                at["reason"] = "overdue: 上次会话中断"
                issues += 1
        if issues:
            self.save()
            self.events.append("run_reconciled", recovered=issues)
        return issues

    def enter_stage(self, stage):
        if stage not in STAGES:
            raise PaperException(f"未知阶段: {stage}")
        self.state["stage"] = stage
        self.state.setdefault("attempts", {}).setdefault(stage, {})
        at = self.state["attempts"][stage]
        at["attempt"] = at.get("attempt", 0) + 1
        at["status"] = "running"
        at["started"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.save()
        self.events.append("stage_entered", stage=stage, attempt=at["attempt"])

    def complete_stage(self, stage, artifact=None, note=""):
        at = self.state.setdefault("attempts", {}).setdefault(stage, {})
        at["status"] = "done"
        at["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if artifact:
            self.state.setdefault("artifacts", {})[stage] = artifact
        self.save()
        self.events.append("stage_completed", stage=stage, artifact=artifact, note=note)

    def fail_stage(self, stage, reason):
        at = self.state.setdefault("attempts", {}).setdefault(stage, {})
        at["status"] = "failed"
        at["reason"] = reason
        self.save()
        self.events.append("stage_failed", stage=stage, reason=reason)

    def checkpoint(self, stage):
        """人工必停点：请求人类批准后返回。"""
        self.events.append("human_approval_requested", stage=stage)
        return (self.dir / "reports" / f"checkpoint_{stage}.md")

    def approve(self, stage):
        self.events.append("human_approved", stage=stage)

    # ---- 产物写盘 ----
    def write_artifact(self, name: str, content: str, subdir: str):
        dest = self.dir / subdir / name
        dest.write_text(content, encoding="utf-8")
        self.events.append("artifact_written", subdir=subdir, name=name)
        return dest

    def status(self):
        last = self.events.tail(8)
        return {
            "slug": self.slug, "title": self.state.get("title"),
            "stage": self.state.get("stage"),
            "version": self.state.get("version"),
            "attempts": {k: v.get("status") for k, v in self.state.get("attempts", {}).items()},
            "artifacts": self.state.get("artifacts", {}),
            "events_tail": last,
        }