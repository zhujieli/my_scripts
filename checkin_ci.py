#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 加油站自动签到 · CI 版（GitHub Actions / 任意云主机）
特点：不依赖预先存在的浏览器配置，Cookie 由环境变量 WB_COOKIE 注入。
依赖：websocket-client（pip install websocket-client）

环境变量：
  WB_COOKIE  必填，形如 "session=xxx; session_2=yyy; ..."（从浏览器导出）
  WB_CHROME  可选，Chrome 可执行文件路径，默认 google-chrome
"""
import json, os, subprocess, sys, time, urllib.request

CHROME = os.environ.get("WB_CHROME", "google-chrome")
PORT = 9222
PROFILE = "/tmp/wb-profile"


def die(msg, code=1):
    print(msg, flush=True)
    sys.exit(code)


def cdp_ready(timeout=30):
    for _ in range(timeout):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def main():
    cookie = os.environ.get("WB_COOKIE", "").strip()
    if not cookie:
        die("❌ 缺少 WB_COOKIE 环境变量（GitHub Secrets 里配置）", 2)

    os.makedirs(PROFILE, exist_ok=True)
    subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         "--remote-allow-origins=*", f"--user-data-dir={PROFILE}",
         "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    if not cdp_ready(30):
        die("❌ Chrome 启动失败")

    # 先开空白页：避免页面先加载时服务端下发新的匿名 session 覆盖注入值
    tab = json.loads(urllib.request.urlopen(
        urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT"),
        timeout=15).read())

    import websocket
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=60)
    ws.settimeout(10)
    mid = [0]

    def call(method, params=None):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid[0]:
                return m

    call("Network.enable")
    ok_count = 0
    for kv in cookie.split("; "):
        k, _, v = kv.partition("=")
        if not k:
            continue
        r = call("Network.setCookie", {"name": k.strip(), "value": v.strip(),
                                       "url": "https://www.workbuddy.cn/", "path": "/"})
        if r.get("result", {}).get("success"):
            ok_count += 1
    print(f"Cookie 注入 {ok_count}/{len(cookie.split('; '))}", flush=True)

    # 注入完成后再导航到应用页
    call("Page.enable")
    call("Page.navigate", {"url": "https://www.workbuddy.cn/app"})
    time.sleep(8)
    cur = call("Runtime.evaluate", {"expression": "location.href + '|' + document.cookie.length",
                                    "returnByValue": True})["result"]["result"].get("value")
    print(f"当前页面: {cur}", flush=True)

    js = """
      (async () => {
        const post = (p,b) => fetch(p,{method:'POST',credentials:'include',
          headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):'{}'}).then(r=>r.text());
        const out={checkin:null,claim:null,depart:null,ok:false,auth:true};
        try{
          const st=JSON.parse(await post('/billing/meter/checkin-status'));
          if(st.code!==0){out.checkin='fail '+st.code+' '+(st.msg||'');}
          else{
            const d=st.data||{};
            if(d.today_checked_in){out.checkin='已签到 连续'+d.streak_days+'天';out.ok=true;}
            else{
              const ck=JSON.parse(await post('/billing/meter/daily-checkin'));
              if(ck.code===0&&ck.data){out.checkin='成功 +'+ck.data.credit+'积分 连续'+ck.data.streak_days+'天';out.ok=true;}
              else if(ck.code===10001){out.checkin='已签到(服务端确认)';out.ok=true;}
              else out.checkin='fail '+ck.code+' '+(ck.msg||'');
            }
          }
        }catch(e){out.checkin='error '+e;out.auth=false;}
        try{
          const cl=JSON.parse(await post('/activity/growth/buddy/travel/claim'));
          if(cl.code===0)out.claim='领取成功 +'+(cl.data?.reward_credit??cl.data?.credit??'?')+'积分';
          else if((cl.msg||'').includes('no unclaimed'))out.claim='暂无可领';
          else out.claim=cl.code+' '+(cl.msg||'');
        }catch(e){out.claim='error '+e;}
        try{
          const dp=JSON.parse(await post('/activity/growth/buddy/travel/depart',{location_id:1}));
          if(dp.code===0)out.depart='已出发 → '+(dp.data?.location?.name||'旅行中');
          else out.depart='旅行中/无需再派';
        }catch(e){out.depart='error '+e;}
        return JSON.stringify(out);
      })()
    """
    r = call("Runtime.evaluate", {"expression": js, "awaitPromise": True, "returnByValue": True})
    val = r["result"]["result"].get("value")
    if not val:
        die(f"❌ 执行异常: {json.dumps(r)[:200]}")
    data = json.loads(val)
    print("RESULT " + json.dumps(data, ensure_ascii=False), flush=True)
    if data.get("ok"):
        print("✅ 签到成功", flush=True)
        return 0
    if "401" in str(data) or not data.get("auth"):
        print("⚠️ 登录态失效，请重新导出 Cookie 并更新 Secret WB_COOKIE", flush=True)
        return 2
    print("❌ 签到失败", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
