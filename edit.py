# -*- coding: utf-8 -*-
"""本地笔记编辑后台：双击运行后浏览器打开 http://127.0.0.1:8899
写完点「同步到 GitHub」即可，手机访问 https://ckunxing.github.io/notes/
支持：Ctrl+V 粘贴图片、笔记分组
"""
import base64, json, mimetypes, os, re, subprocess, sys, threading, time, webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

ROOT = os.path.dirname(os.path.abspath(__file__))
NOTES_DIR = os.path.join(ROOT, "notes")
IMG_DIR = os.path.join(NOTES_DIR, "images")
PORT = 8899
os.makedirs(IMG_DIR, exist_ok=True)

def safe_seg(s):
    s = re.sub(r'[\\/:*?"<>|]', "", (s or "")).strip().strip(".")
    return s

def safe_rel(rel):
    """把 '分组/名字.md' 或 '名字.md' 规整为安全的相对路径"""
    rel = (rel or "").replace("\\", "/").strip("/")
    parts = [safe_seg(p) for p in rel.split("/")]
    parts = [p for p in parts if p and p != ".."]
    if not parts:
        parts = [datetime.now().strftime("%Y-%m-%d_%H%M") + ".md"]
    if not parts[-1].endswith(".md"):
        parts[-1] += ".md"
    return "/".join(parts)

def abspath(rel):
    p = os.path.abspath(os.path.join(NOTES_DIR, rel))
    if not p.startswith(os.path.abspath(NOTES_DIR)):
        raise ValueError("bad path")
    return p

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
    return " ".join(text.split())[:limit]

def list_notes():
    out = []
    for dirpath, _, files in os.walk(NOTES_DIR):
        if os.path.abspath(dirpath).startswith(os.path.abspath(IMG_DIR)):
            continue
        for fn in files:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, NOTES_DIR).replace("\\", "/")
            grp = rel.split("/")[0] if "/" in rel else "未分组"
            out.append({
                "file": rel,
                "group": grp,
                "title": note_title(p),
                "date": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M"),
                "excerpt": note_excerpt(p),
            })
    out.sort(key=lambda n: n["date"], reverse=True)
    return out

def rebuild_index():
    idx = [{"file": n["file"], "group": n["group"], "title": n["title"],
            "date": n["date"][:10], "excerpt": n["excerpt"]} for n in list_notes()]
    with open(os.path.join(NOTES_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    return len(idx)

def git(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")

def do_sync():
    n = rebuild_index()
    git("add", "-A")
    if not git("status", "--porcelain").stdout.strip():
        return f"索引已更新（{n} 篇），没有需要提交的改动"
    c = git("commit", "-m", "notes update " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    p = git("push")
    return (f"已提交并推送（{n} 篇）" if p.returncode == 0
            else "推送失败:\n" + (p.stderr or p.stdout))

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>笔记编辑后台</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<style>
:root{--bg:#f4f4f2;--card:#fff;--card2:#fafafa;--line:#e7e7e4;--text:#26262a;--dim:#8a8a90;--accent:#5c6b7a;--shadow:0 2px 12px rgba(0,0,0,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#141516;--card:#1d1e20;--card2:#26282b;--line:#2e3033;--text:#e2e2e4;--dim:#8e9095;--accent:#9aa7b3;--shadow:0 2px 12px rgba(0,0,0,.3)}}
*{box-sizing:border-box}
body{margin:0;height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--text);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
#top{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line);background:var(--card)}
#top b{font-size:16px}
#top .sp{flex:1}
button{padding:8px 16px;border-radius:9px;border:1.5px solid var(--line);background:var(--card);color:var(--text);font-size:14px;cursor:pointer;font-family:inherit}
button.pri{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button:active{transform:scale(.96)}
#main{flex:1;display:flex;min-height:0}
#side{width:250px;border-right:1px solid var(--line);overflow-y:auto;background:var(--card);padding:10px}
.grp{font-size:12px;color:var(--dim);font-weight:600;padding:10px 12px 4px;letter-spacing:1px}
#side .ni{padding:8px 12px;border-radius:9px;cursor:pointer;margin-bottom:3px}
#side .ni:hover{background:var(--card2)}
#side .ni.on{background:var(--card2);border-left:3px solid var(--accent)}
#side .ni .t{font-weight:600;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#side .ni .d{font-size:11.5px;color:var(--dim);font-family:monospace}
#editor{flex:1;display:flex;flex-direction:column;min-width:0}
#namebar{display:flex;gap:10px;padding:10px 14px}
#grpIn{width:150px;padding:9px 12px;border-radius:9px;border:1.5px solid var(--line);background:var(--card);color:var(--text);font-size:14px;outline:none;font-family:inherit}
#titleIn{flex:1;padding:9px 14px;border-radius:9px;border:1.5px solid var(--line);background:var(--card);color:var(--text);font-size:15px;outline:none;font-family:inherit}
#panes{flex:1;display:flex;min-height:0;padding:0 14px 14px;gap:14px}
#md{flex:1;resize:none;border:1.5px solid var(--line);border-radius:12px;padding:16px;background:var(--card);color:var(--text);font-size:14.5px;line-height:1.8;outline:none;font-family:ui-monospace,Menlo,Consolas,monospace}
#preview{flex:1;overflow-y:auto;border:1.5px solid var(--line);border-radius:12px;padding:4px 18px;background:var(--card)}
#preview img{max-width:100%;border-radius:8px}
#preview pre{background:var(--card2);border-radius:8px;padding:10px;overflow-x:auto}
#preview blockquote{border-left:2px solid var(--dim);margin:1em 0;padding:4px 12px;color:var(--dim)}
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
  <button onclick="delNote()">删除</button>
  <button class="pri" onclick="saveNote()">保存</button>
  <button class="pri" onclick="syncNow()">⇪ 同步到 GitHub</button>
</div>
<div id="main">
  <div id="side"></div>
  <div id="editor">
    <div id="namebar">
      <input id="grpIn" list="grplist" placeholder="分组（默认未分组）">
      <datalist id="grplist"></datalist>
      <input id="titleIn" placeholder="笔记标题（作为文件名）">
    </div>
    <div id="panes">
      <textarea id="md" placeholder="# 标题&#10;&#10;用 Markdown 写正文，可直接 Ctrl+V 粘贴图片…" oninput="renderPv()"></textarea>
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
  const groups=[...new Set(notes.map(n=>n.group))];
  $('grplist').innerHTML=groups.map(g=>`<option value="${g}">`).join('');
  let html='';
  for(const g of groups){
    html+=`<div class="grp">${g==='未分组'?'未分组':'📁 '+g}</div>`;
    for(const n of notes.filter(x=>x.group===g))
      html+=`<div class="ni${cur===n.file?' on':''}" onclick="openNote('${encodeURIComponent(n.file)}')">
        <div class="t">${n.title}</div><div class="d">${n.date}</div></div>`;
  }
  $('side').innerHTML=html||'<div style="color:var(--dim);padding:20px;text-align:center">还没有笔记</div>';
}
async function openNote(f){
  const d=await api('get?file='+f);
  cur=d.file;
  const i=d.file.lastIndexOf('/');
  $('grpIn').value=i>0?d.file.slice(0,i):'';
  $('titleIn').value=(i>0?d.file.slice(i+1):d.file).replace(/\.md$/,'');
  $('md').value=d.content; renderPv(); reload();
  document.getElementById('side').classList.remove('show');
}
function newNote(){cur=null;$('titleIn').value='';$('md').value='';renderPv();
  document.getElementById('side').classList.remove('show');$('titleIn').focus()}
async function saveNote(){
  const title=$('titleIn').value.trim()||$('md').value.split('\n')[0].replace(/^#\s*/,'').trim();
  if(!title){say('先写个标题');return}
  const g=$('grpIn').value.trim();
  const d=await api('save',{old:cur,name:(g?g+'/':'')+title,content:$('md').value});
  cur=d.file; say('已保存 '+d.file); reload();
}
async function delNote(){
  if(!cur){say('没有打开笔记');return}
  if(!confirm('删除 '+cur+' ?'))return;
  await api('delete',{file:cur}); newNote(); say('已删除'); reload();
}
async function syncNow(){say('同步中…');const d=await api('sync',{});say(d.msg);reload()}
function renderPv(){
  const t=$('md').value;
  $('preview').innerHTML=window.marked?marked.parse(t):'<pre></pre>';
  if(!window.marked)$('preview').textContent=t;
}
/* Ctrl+V 粘贴图片 */
$('md').addEventListener('paste',async e=>{
  const items=(e.clipboardData||{}).items||[];
  for(const it of items){
    if(!it.type.startsWith('image/'))continue;
    e.preventDefault();
    const file=it.getAsFile(); if(!file)return;
    say('上传图片中…');
    const dataUrl=await new Promise(r=>{const fr=new FileReader();fr.onload=()=>r(fr.result);fr.readAsDataURL(file)});
    const d=await api('upload',{data:dataUrl.split(',')[1],ext:(file.type.split('/')[1]||'png')});
    if(d.path){
      const ta=$('md'),pos=ta.selectionStart;
      ta.value=ta.value.slice(0,pos)+'![]('+d.path+')'+ta.value.slice(pos);
      renderPv(); say('图片已插入 '+d.path);
    }else say('图片上传失败');
    return;
  }
});
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
            try:
                rel = safe_rel(parse_qs(u.query).get("file", [""])[0])
                p = abspath(rel)
                content = open(p, encoding="utf-8").read() if os.path.isfile(p) else ""
                self._json({"file": rel, "content": content})
            except ValueError:
                self.send_error(403)
        elif u.path.startswith("/notes/"):
            try:
                p = abspath(unquote(u.path[len("/notes/"):]))
                if not os.path.isfile(p):
                    self.send_error(404); return
                b = open(p, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(p)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            except ValueError:
                self.send_error(403)
        else:
            self.send_error(404)
    def do_POST(self):
        u = urlparse(self.path)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if u.path == "/api/save":
            new = safe_rel(body.get("name", ""))
            old = body.get("old")
            if old:
                old = safe_rel(old)
                if old != new:
                    op = abspath(old)
                    if os.path.isfile(op):
                        os.remove(op)
            np = abspath(new)
            os.makedirs(os.path.dirname(np), exist_ok=True)
            with open(np, "w", encoding="utf-8") as f:
                f.write(body.get("content", ""))
            self._json({"file": new})
        elif u.path == "/api/delete":
            try:
                p = abspath(safe_rel(body.get("file", "")))
                if os.path.isfile(p):
                    os.remove(p)
            except ValueError:
                pass
            self._json({"ok": True})
        elif u.path == "/api/upload":
            try:
                raw = base64.b64decode(body.get("data", ""))
                ext = safe_seg(body.get("ext", "png")) or "png"
                if len(raw) > 20 * 1024 * 1024:
                    self._json({"error": "too large"}); return
                fn = time.strftime("%Y%m%d_%H%M%S") + "_" + str(os.getpid()) + "." + ext
                with open(os.path.join(IMG_DIR, fn), "wb") as f:
                    f.write(raw)
                self._json({"path": "notes/images/" + fn})
            except Exception as e:
                self._json({"error": str(e)})
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
