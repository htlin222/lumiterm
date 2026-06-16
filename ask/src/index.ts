// Workers runtime globals (avoids needing @cloudflare/workers-types in-editor).
declare const WebSocketPair: { new (): { 0: WebSocket; 1: WebSocket } };

// ask — a tiny Slido-like live comment system (deploy to your own domain).
//   /          audience page (name + comment + quick snippets)
//   /present   presenter page (comments pop top-right, macOS-notification style)
//   POST /api/comment   {name,text} -> store + broadcast
//   GET  /ws            presenter WebSocket subscription
//   GET  /api/comments  recent comments (JSON)
// Real-time fan-out + persistence live in one Durable Object (SQLite storage).

const PAGE_HEAD =
  '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">';

const AUDIENCE = '<!doctype html><html lang="zh-Hant"><head>' + PAGE_HEAD +
'<title>ask · 即時回饋</title><style>' +
'*{box-sizing:border-box}html,body{margin:0;height:100%}' +
'body{font-family:-apple-system,BlinkMacSystemFont,"PingFang TC","Segoe UI",sans-serif;' +
'background:radial-gradient(1100px 700px at 10% -10%,#eef2ff,transparent 55%),radial-gradient(900px 600px at 110% 120%,#fdeef6,transparent 50%),linear-gradient(135deg,#f6f7fb,#eef0f6);' +
'display:flex;align-items:center;justify-content:center;padding:20px}' +
'.card{width:100%;max-width:460px;background:#fff;border-radius:20px;padding:22px;' +
'box-shadow:0 20px 50px -18px rgba(40,50,90,.35);border:1px solid rgba(0,0,0,.05)}' +
'h1{font-size:19px;margin:0 0 2px}.sub{color:#8a8f98;font-size:13px;margin:0 0 18px}' +
'label{display:block;font-size:12px;font-weight:700;color:#6b7178;letter-spacing:.3px;margin:14px 0 6px;text-transform:uppercase}' +
'input,textarea{width:100%;border:1px solid #dcdce4;border-radius:12px;padding:12px 13px;font:inherit;font-size:16px;background:#fbfbfd}' +
'input:focus,textarea:focus{outline:none;border-color:#2563eb;background:#fff}' +
'textarea{resize:vertical;min-height:80px}' +
'.snips{display:flex;flex-direction:column;gap:8px;margin-top:6px}' +
'.snip{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:1px solid #e2e2ea;background:#f7f8fb;' +
'border-radius:12px;padding:12px 14px;font:inherit;font-size:15px;font-weight:600;color:#2b2d31;cursor:pointer}' +
'.snip:active{transform:scale(.99)}.snip .e{font-size:18px}' +
'.snip.q{border-color:#fde0b4}.snip.ok{border-color:#bfe6c9}.snip.pr{border-color:#c9d8fb}' +
'.send{margin-top:14px;width:100%;height:50px;border:0;border-radius:14px;background:linear-gradient(180deg,#3b82f6,#2563eb);' +
'color:#fff;font-size:16px;font-weight:700;cursor:pointer}.send:active{filter:brightness(1.05)}' +
'.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);opacity:0;' +
'background:#111827;color:#fff;padding:11px 18px;border-radius:999px;font-size:14px;font-weight:600;transition:.25s;pointer-events:none}' +
'.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}' +
'</style></head><body><div class="card">' +
'<h1>有什麼想說的嗎？ 🙋</h1><p class="sub">你的回饋會即時出現在講者畫面上</p>' +
'<label>你的名字</label><input id="name" placeholder="匿名" maxlength="40">' +
'<label>快速回饋</label><div class="snips">' +
'<button class="snip q" data-t="聽不太懂，想要再講一次"><span class="e">🤔</span>聽不太懂，想要再講一次</button>' +
'<button class="snip ok" data-t="聽懂了"><span class="e">✅</span>聽懂了</button>' +
'<button class="snip pr" data-t="想要有一些練習時間"><span class="e">⏳</span>想要有一些練習時間</button>' +
'</div>' +
'<label>或自己打一段</label><textarea id="text" placeholder="輸入你的問題或留言…" maxlength="500"></textarea>' +
'<button class="send" id="send">送出</button>' +
'</div><div class="toast" id="toast"></div><script>' +
'var nm=document.getElementById("name"),tx=document.getElementById("text"),tp=document.getElementById("toast");' +
'nm.value=localStorage.getItem("ask-name")||"";' +
'nm.addEventListener("input",function(){localStorage.setItem("ask-name",nm.value)});' +
'var tt;function toast(m){tp.textContent=m;tp.classList.add("show");clearTimeout(tt);tt=setTimeout(function(){tp.classList.remove("show")},1800)}' +
'function send(t){t=(t||"").trim();if(!t)return;var name=(nm.value||"").trim()||"匿名";' +
'fetch("/api/comment",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({name:name,text:t})})' +
'.then(function(r){return r.json()}).then(function(){toast("已送出 ✓")}).catch(function(){toast("送出失敗，再試一次")})}' +
'document.getElementById("send").onclick=function(){send(tx.value);tx.value=""};' +
'var bs=document.querySelectorAll(".snip");for(var i=0;i<bs.length;i++){bs[i].onclick=function(){send(this.getAttribute("data-t"))}}' +
'tx.addEventListener("keydown",function(e){if((e.metaKey||e.ctrlKey)&&e.key==="Enter"){send(tx.value);tx.value=""}});' +
'</script></body></html>';

const PRESENTER = '<!doctype html><html lang="zh-Hant"><head>' + PAGE_HEAD +
'<title>ask · 講者畫面</title><style>' +
'*{box-sizing:border-box}html,body{margin:0;height:100%}' +
'body{font-family:-apple-system,BlinkMacSystemFont,"PingFang TC","Segoe UI",sans-serif;' +
'background:linear-gradient(135deg,#0f1117,#1b1e27);color:#e8e8ee;overflow:hidden}' +
'.bar{position:fixed;top:0;left:0;right:0;display:flex;align-items:center;gap:10px;padding:14px 18px;font-size:13px;color:#aeb4be}' +
'.dot{width:9px;height:9px;border-radius:50%;background:#f55;box-shadow:0 0 0 0 rgba(40,200,120,.5)}' +
'.dot.on{background:#28c840;animation:pulse 2s infinite}' +
'@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(40,200,64,.5)}70%{box-shadow:0 0 0 8px rgba(40,200,64,0)}100%{box-shadow:0 0 0 0 rgba(40,200,64,0)}}' +
'.clear{margin-left:auto;border:1px solid #353a45;background:#1f232d;color:#cfd3db;border-radius:8px;padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer}' +
'.hint{position:fixed;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;color:#4b515c;font-size:15px}' +
'#stack{position:fixed;top:54px;right:18px;width:360px;max-width:calc(100vw - 36px);display:flex;flex-direction:column;gap:10px;z-index:9}' +
'.note{position:relative;background:rgba(255,255,255,.96);color:#1d1f25;border-radius:14px;padding:13px 15px 12px;' +
'box-shadow:0 12px 30px -8px rgba(0,0,0,.5);border:1px solid rgba(255,255,255,.5);' +
'opacity:0;transform:translateX(40px) scale(.98);transition:opacity .35s ease,transform .35s ease}' +
'.note.in{opacity:1;transform:none}.note.out{opacity:0;transform:translateX(40px) scale(.98)}' +
'.note .nm{font-weight:800;font-size:13px;color:#2563eb;margin-bottom:3px}' +
'.note .tx{font-size:16px;line-height:1.45;white-space:pre-wrap;word-break:break-word}' +
'.note .tm{font-size:11px;color:#9aa0a8;margin-top:6px}' +
'.note .x{position:absolute;top:8px;right:9px;border:0;background:none;color:#b8bdc6;font-size:16px;line-height:1;cursor:pointer}' +
'.note .x:hover{color:#1d1f25}' +
'</style></head><body>' +
'<div class="bar"><span class="dot" id="dot"></span><span id="st">連線中…</span>' +
'<button class="clear" id="clear">清除全部</button></div>' +
'<div class="hint" id="hint">等待觀眾回饋…</div>' +
'<div id="stack"></div><script>' +
'var box=document.getElementById("stack"),dot=document.getElementById("dot"),st=document.getElementById("st"),hint=document.getElementById("hint");' +
'if(hint)hint.textContent="等待觀眾回饋 · 把這頁開在講者畫面，分享 "+location.host+" 給觀眾";' +
'function rm(c){c.classList.remove("in");c.classList.add("out");setTimeout(function(){c.remove()},360)}' +
'function add(c){if(hint)hint.style.display="none";' +
'var d=document.createElement("div");d.className="note";' +
'var x=document.createElement("button");x.className="x";x.textContent="\\u00d7";x.onclick=function(){rm(d)};' +
'var nm=document.createElement("div");nm.className="nm";nm.textContent=c.name||"匿名";' +
'var tx=document.createElement("div");tx.className="tx";tx.textContent=c.text||"";' +
'var tm=document.createElement("div");tm.className="tm";tm.textContent=new Date(c.ts||Date.now()).toLocaleTimeString();' +
'd.appendChild(x);d.appendChild(nm);d.appendChild(tx);d.appendChild(tm);box.appendChild(d);' +
'requestAnimationFrame(function(){d.classList.add("in")});' +
'while(box.children.length>8){box.removeChild(box.firstChild)}}' +
'document.getElementById("clear").onclick=function(){var n=box.children;for(var i=n.length-1;i>=0;i--)rm(n[i])};' +
'function setSt(on){dot.className=on?"dot on":"dot";st.textContent=on?"已連線 · 即時":"重新連線中…"}' +
'var ws;function connect(){ws=new WebSocket((location.protocol==="https:"?"wss://":"ws://")+location.host+"/ws");' +
'ws.onopen=function(){setSt(true)};ws.onclose=function(){setSt(false);setTimeout(connect,2000)};' +
'ws.onmessage=function(e){try{var d=JSON.parse(e.data);if(d.type==="comment")add(d)}catch(_){}}}' +
'connect();' +
'</script></body></html>';

function htmlResponse(s: string): Response {
  return new Response(s, { headers: { "content-type": "text/html; charset=utf-8" } });
}

function withCors(resp: Response): Response {
  resp.headers.set("Access-Control-Allow-Origin", "*");
  resp.headers.set("Access-Control-Allow-Headers", "content-type");
  resp.headers.set("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  return resp;
}

export default {
  async fetch(req: Request, env: any): Promise<Response> {
    const url = new URL(req.url);

    // Force HTTPS so a typed bare domain / QR code never loads over plaintext
    // (Chrome flags any http:// page as "not secure").
    let scheme = url.protocol.replace(":", "");
    const visitor = req.headers.get("cf-visitor");
    if (visitor) { try { scheme = JSON.parse(visitor).scheme || scheme; } catch (_e) {} }
    if (scheme === "http") {
      url.protocol = "https:";
      return Response.redirect(url.href, 301);
    }

    const p = url.pathname;
    const room = env.ROOM.get(env.ROOM.idFromName("global"));

    if (req.method === "OPTIONS") return withCors(new Response(null, { status: 204 }));
    if (p === "/" || p === "") return htmlResponse(AUDIENCE);
    if (p === "/present") return htmlResponse(PRESENTER);
    if (p === "/ws") return room.fetch(req);
    if (p === "/api/comment" && req.method === "POST") {
      const body = await req.text();
      const r = await room.fetch("https://do/broadcast", {
        method: "POST", body, headers: { "content-type": "application/json" },
      });
      return withCors(new Response(await r.text(), { status: r.status, headers: { "content-type": "application/json" } }));
    }
    if (p === "/api/comments") {
      const r = await room.fetch("https://do/list");
      return withCors(new Response(await r.text(), { headers: { "content-type": "application/json" } }));
    }
    return new Response("not found", { status: 404 });
  },
};

export class Room {
  ctx: any;
  env: any;
  constructor(ctx: any, env: any) {
    this.ctx = ctx;
    this.env = env;
    this.ctx.storage.sql.exec(
      "CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, name TEXT, text TEXT)"
    );
  }

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);

    if (url.pathname === "/ws") {
      const pair = new WebSocketPair();
      this.ctx.acceptWebSocket(pair[1]);
      return new Response(null, { status: 101, webSocket: pair[0] } as any);
    }

    if (url.pathname === "/broadcast") {
      const data = await req.json().catch(() => ({}));
      const name = String((data as any).name || "匿名").slice(0, 40);
      const text = String((data as any).text || "").slice(0, 500);
      if (!text.trim()) return Response.json({ error: "empty" }, { status: 400 });
      const ts = Date.now();
      this.ctx.storage.sql.exec("INSERT INTO comments(ts,name,text) VALUES(?,?,?)", ts, name, text);
      const msg = JSON.stringify({ type: "comment", name, text, ts });
      for (const ws of this.ctx.getWebSockets()) {
        try { ws.send(msg); } catch (_e) { /* ignore dead socket */ }
      }
      return Response.json({ ok: true });
    }

    if (url.pathname === "/list") {
      const rows = this.ctx.storage.sql
        .exec("SELECT id,ts,name,text FROM comments ORDER BY id DESC LIMIT 50")
        .toArray();
      return Response.json({ items: rows });
    }

    return new Response("not found", { status: 404 });
  }

  async webSocketMessage(ws: any, msg: any) {
    if (msg === "ping") { try { ws.send("pong"); } catch (_e) {} }
  }
  async webSocketClose(ws: any) { try { ws.close(); } catch (_e) {} }
  async webSocketError() {}
}
