# -*- coding: utf-8 -*-
"""本地笔记编辑后台：双击运行后浏览器打开 http://127.0.0.1:8899
写完点「同步到 GitHub」即可，手机访问 https://ckunxing.github.io/notes/
"""
import json, os, re, subprocess, sys, threading, webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
NOTES_DIR = os.path.join(ROOT, "notes")
PORT = 8899
os.makedirs(NOTES_DIR, exist_ok=True)

def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|]', "", name).strip().strip(".")
    if not name:
        name = datetime.now().strftime("%Y-%m-%d_%H%M")
    if not name.endswith(".md"):
        name += ".md"
    return name

def note_title(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^#\s+(.+)", line.strip())
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return os.path.splitext(os.path.basename(path))[0]

def note_excerpt(path, limit=90):
    try:
        text = open(path, encoding="utf-8").read()
    except Exception:
        return ""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#>*`\-]+", "", text)
    text = " ".join(text.split())
    return text[:limit]

def list_notes():
    out = []
    for fn in os.listdir(NOTES_DIR):
        if not fn.endswith(".md"):
            continue
        p = os.path.join(NOTES_DIR, fn)
        out.append({
            "file": fn,
            "title": note_title(p),
            "date": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M"),
            "excerpt": note_excerpt(p),
        })
    out.sort(key=lambda n: n["date"], reverse=True)
    return out

def rebuild_index():
    idx = [{"file": n["file"], "title": n["title"], "date": n["date"][:10],
            "excerpt": n["excerpt"]} for n in list_notes()]
    with open(os.path.join(NOTES_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    return len(idx)

def git(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")

def do_sync():
    n = rebuild_index()
    git("add", "-A")
    st = git("status", "--porcelain")
    if not st.stdout.strip():
        return f"索引已更新（{n} 篇），没有需要提交的改动"
    msg = "notes update " + datetime.now().strftime("%Y-%m-%d %H:%M")
    c = git("commit", "-m", msg)
    p = git("push")
    ok = p.returncode == 0
    return (f"已提交并推送（{n} 篇）" if ok else "推送失败:\n" + (p.stderr or p.stdout))

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>笔记编辑后台</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<style>
:root{--bg:#f4f1ea;--card:#fff;--card2:#faf8f3;--line:#e8e2d5;--text:#221f1a;--dim:#8d8578;--accent:#c8342a;--shadow:0 2px 12px rgba(60,45,20,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#131210;--card:#1e1d1a;--card2:#26241f;--line:#33302a;--text:#ece7dd;--dim:#98907f;--accent:#e85d50;--shadow:0 2px 12px rgba(0,0,0,.35)}}
*{box-sizing:border-box}
body{margin:0;height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--text);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
#top{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line);background:var(--card)}
#top b{font-size:16px}
#top .sp{flex:1}
button{padding:8px 16px;border-radius:9px;border:1.5px solid var(--line);background:var(--card);color:var(--text);font-size:14px;cursor:pointer;font-family:inherit}
button.pri{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button:active{transform:scale(.96)}
#main{flex:1;display:flex;min-height:0}
#side{width:240px;border-right:1px solid var(--line);overflow-y:auto;background:var(--card);padding:10px}
#side .ni{padding:9px 12px;border-radius:10px;cursor:pointer;margin-bottom:4px}
#side .ni:hover{background:var(--card2)}
#side .ni.on{background:color-mix(in srgb,var(--accent) 10%,transparent);border-left:3px solid var(--accent)}
#side .ni .t{font-weight:600;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#side .ni .d{font-size:11.5px;color:var(--dim);font-family:monospace}
#editor{flex:1;display:flex;flex-direction:column;min-width:0}
#namebar{display:flex;gap:10px;padding:10px 14px}
#titleIn{flex:1;padding:9px 14px;border-radius:9px;border:1.5px solid var(--line);background:var(--card);color:var(--text);font-size:15px;outline:none;font-family:inherit}
#panes{flex:1;display:flex;min-height:0;padding:0 14px 14px;gap:14px}
#md{flex:1;resize:none;border:1.5px solid var(--line);border-radius:12px;padding:16px;background:var(--card);color:var(--text);font:14.5px/1.8 ui-monospace,Menlo,Consolas,monospace;outline:none;font-family:inherit}
#preview{flex:1;overflow-y:auto;border:1.5px solid var(--line);border-radius:12px;padding:4px 18px;background:var(--card)}
#preview img{max-width:100%}
#preview pre{background:var(--card2);border-radius:8px;padding:10px;overflow-x:auto}
#preview blockquote{border-left:3px solid var(--accent);margin:1em 0;padding:4px 12px;background:var(--card2);color:var(--dim)}
#status{padding:8px 14px;font-size:13px;color:var(--dim);border-top:1px solid var(--line);white-space:pre-wrap;max-height:90px;overflow-y:auto}
@media (max-width:800px){#side{position:absolute;z-index:5;height:100%;box-shadow:var(--shadow);transform:translateX(-100%);transition:transform .2s}#side.show{transform:none}#preview{display:none}#menubtn{display:inline-block}}
#menubtn{display:none}
</style>
</head>
<body>
<div id="top">
  <button id="menubtn" onclick="document.getElementById('side').classList.toggle('show')">☰</button>
  <b>📝 笔记后台</b><span class="sp"></span>
  <button onclick="newNote()">＋ 新建</button>
  <button onclick="delNote()" id="delBtn">删除</button>
  <button class="pri" onclick="saveNote()">保存</button>
  <button class="pri" onclick="syncNow()">⇪ 同步到 GitHub</button>
</div>
<div id="main">
  <div id="side"></div>
  <div id="editor">
    <div id="namebar"><input id="titleIn" placeholder="笔记标题（作为文件名）"></div>
    <div id="panes">
      <textarea id="md" placeholder="# 标题&#10;&#10;用 Markdown 写正文…" oninput="renderPv()"></textarea>
      <div id="preview"></div>
    </div>
  </div>
</div>
<div id="status">就绪</div>
<script>
let cur=null, notes=[];
const $=id=>document.getElementById(id);
function say(s){$('status').textContent=s}
async function api(path,body){
  const r=await fetch('/api/'+path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);
  return r.json();
}
async function reload(){
  notes=await api('list');
  $('side').innerHTML=notes.map(n=>
    `<div class="ni${cur===n.file?' on':''}" onclick="openNote('${encodeURIComponent(n.file)}')">
     <div class="t">${n.title}</div><div class="d">${n.date}</div></div>`).join('')
    ||'<div style="color:var(--dim);padding:20px;text-align:center">还没有笔记</div>';
}
async function openNote(f){
  const d=await api('get?file='+f);
  cur=d.file; $('titleIn').value=d.file.replace(/\.md$/,''); $('md').value=d.content;
  renderPv(); reload(); document.getElementById('side').classList.remove('show');
}
function newNote(){cur=null;$('titleIn').value='';$('md').value='';renderPv();
  document.getElementById('side').classList.remove('show');$('titleIn').focus()}
async function saveNote(){
  const title=$('titleIn').value.trim()||$('md').value.split('\n')[0].replace(/^#\s*/,'').trim();
  if(!title){say('先写个标题');return}
  const d=await api('save',{old:cur,name:title,content:$('md').value});
  cur=d.file; say('已保存 '+d.file); reload();
}
async function delNote(){
  if(!cur){say('没有打开笔记');return}
  if(!confirm('删除 '+cur+' ?'))return;
  await api('delete',{file:cur}); newNote(); say('已删除'); reload();
}
async function syncNow(){
  say('同步中…');
  const d=await api('sync',{}); say(d.msg); reload();
}
function renderPv(){
  const t=$('md').value;
  $('preview').innerHTML=window.marked?marked.parse(t):'<pre></pre>';
  if(!window.marked)$('preview').textContent=t;
}
reload();
</script>
</body>
</html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            b = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/list":
            self._json(list_notes())
        elif u.path == "/api/get":
            fn = safe_name(parse_qs(u.query).get("file", [""])[0])
            p = os.path.join(NOTES_DIR, fn)
            content = open(p, encoding="utf-8").read() if os.path.isfile(p) else ""
            self._json({"file": fn, "content": content})
        else:
            self.send_error(404)
    def do_POST(self):
        u = urlparse(self.path)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if u.path == "/api/save":
            new = safe_name(body.get("name", ""))
            old = body.get("old")
            if old and old != new:
                op = os.path.join(NOTES_DIR, safe_name(old))
                if os.path.isfile(op):
                    os.remove(op)
            with open(os.path.join(NOTES_DIR, new), "w", encoding="utf-8") as f:
                f.write(body.get("content", ""))
            self._json({"file": new})
        elif u.path == "/api/delete":
            p = os.path.join(NOTES_DIR, safe_name(body.get("file", "")))
            if os.path.isfile(p):
                os.remove(p)
            self._json({"ok": True})
        elif u.path == "/api/sync":
            self._json({"msg": do_sync()})
        else:
            self.send_error(404)

if __name__ == "__main__":
    rebuild_index()
    url = f"http://127.0.0.1:{PORT}"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"笔记编辑后台: {url}  (Ctrl+C 退出)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
