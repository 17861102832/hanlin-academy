"""翰林院 CLI 入口

用法见 hanlin.py 顶部 docstring。
"""

import sys

from . import pipeline
from .hanlin import PaperException


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__)
        print("\n命令：init <slug> <title> | run <slug> [--stop-at <stage>] | status <slug> | reset <slug>")
        return 0
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "init":
            pipeline.init(rest[0], " ".join(rest[1:]))
        elif cmd == "run":
            slug = rest[0]
            stop = None
            if len(rest) >= 3 and rest[1] == "--stop-at":
                stop = rest[2]
            return pipeline.run(slug, stop_at=stop)
        elif cmd == "status":
            pipeline.status(rest[0])
        elif cmd == "reset":
            pipeline.reset(rest[0])
        else:
            print(f"未知命令: {cmd}")
            return 1
        return 0
    except (IndexError, PaperException) as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())