# -*- coding: utf-8 -*-
"""一键同步：重建 notes/index.json 并提交推送到 GitHub"""
import subprocess, sys
from datetime import datetime
from edit import rebuild_index, ROOT

def git(*args):
    r = subprocess.run(["git", "-C", ROOT] + list(args),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")

if __name__ == "__main__":
    n = rebuild_index()
    git("add", "-A")
    code, out = git("status", "--porcelain")
    if not out.strip():
        print(f"索引已更新（{n} 篇），没有需要提交的改动")
        sys.exit(0)
    git("commit", "-m", "notes update " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    code, out = git("push")
    print(f"已提交并推送（{n} 篇）" if code == 0 else "推送失败:\n" + out)
