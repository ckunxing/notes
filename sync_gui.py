# -*- coding: utf-8 -*-
"""静默同步笔记到 GitHub：小窗显示进度和结果，无控制台黑窗"""
import threading, queue, subprocess, sys
import tkinter as tk
from datetime import datetime
from edit import rebuild_index, ROOT

def git(*args):
    r = subprocess.run(["git", "-C", ROOT] + list(args),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()

def work(q):
    try:
        q.put(("run", "正在重建索引…"))
        n = rebuild_index()
        git("add", "-A")
        if not git("status", "--porcelain")[1]:
            q.put(("ok", f"已是最新（{n} 篇），无需同步"))
            return
        q.put(("run", "正在提交更改…"))
        git("commit", "-m", "notes update " + datetime.now().strftime("%Y-%m-%d %H:%M"))
        q.put(("run", "正在推送到 GitHub…"))
        code, out = git("push")
        if code == 0:
            q.put(("ok", f"同步完成（{n} 篇）\n约 1 分钟后手机可见"))
        else:
            q.put(("err", "推送失败\n" + out[:300]))
    except Exception as e:
        q.put(("err", "出错\n" + str(e)[:300]))

def main():
    root = tk.Tk()
    root.title("同步笔记")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    w, h = 340, 150
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{sw//2-w//2}+{sh//3}")
    status = tk.Label(root, text="准备中…", font=("Microsoft YaHei UI", 11), pady=18)
    status.pack()
    btn = tk.Button(root, text="关闭", width=10, command=root.destroy)

    q = queue.Queue()
    threading.Thread(target=work, args=(q,), daemon=True).start()

    def poll():
        try:
            kind, msg = q.get_nowait()
            status.config(text=msg)
            if kind == "ok":
                status.config(fg="#2e7d32")
                btn.pack(pady=6)
                root.after(6000, root.destroy)
                return
            if kind == "err":
                status.config(fg="#c62828")
                btn.pack(pady=6)
                return
        except queue.Empty:
            pass
        root.after(200, poll)

    poll()
    root.mainloop()

if __name__ == "__main__":
    main()
