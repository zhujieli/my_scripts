# WorkBuddy 每日自动签到（GitHub Actions 版）

无需开电脑、无需登录客户端、无需服务器，每天自动领 Buddy 加油站积分。

## 原理

- GitHub Actions 按 cron 定时启动一台临时 Ubuntu 机器（免费额度完全够用）
- 脚本启动无头 Chrome，把 `WB_COOKIE` 里的登录 Cookie 注入浏览器
- 在页面上下文调用签到接口（与网页版完全一致，因此不会被网关拦）
- 脚本幂等：先查当天是否已签，已签就跳过，可安全重复运行

## 部署步骤（约 5 分钟）

### 1. 新建仓库

在 GitHub 新建一个 **Private** 仓库（比如 `wb-checkin`），把本目录全部文件上传：

```
wb-checkin/
├── .github/workflows/checkin.yml
└── checkin_ci.py
```

> 注意：`.github` 目录必须以点开头，上传时别被隐藏文件过滤掉。

### 2. 配置 Cookie Secret

Cookie 从浏览器导出（Chrome 开发者工具 → Application → Cookies → `https://www.workbuddy.cn`），
拼成一行：

```
session=xxxx; session_2=yyyy; 9c412d6095037d16=zzzz; tgw_l7_route=...
```

必须包含 `session`、`session_2` 以及 `9c412d...` 那段加密串。

然后仓库 → **Settings → Secrets and variables → Actions → New repository secret**：

- Name: `WB_COOKIE`
- Secret: 上面那一整行字符串

### 3. 测试

仓库 → **Actions** → 左侧「WorkBuddy 每日签到」→ 右侧 **Run workflow** 手动跑一次。
日志里出现 `✅ 签到成功` 即部署完成。

### 4. 定时生效

工作流里已配置两个时间（北京时间）：

- `00:05` 主任务
- `00:35` 兜底任务（已签自动跳过）

GitHub 的 cron 可能有 5–15 分钟延迟，属于正常现象。

## 常见问题

**Q: Cookie 多久失效？**
A: 通常数周至数月。失效时 Action 会失败并在日志提示「登录态失效」，重新导出 Cookie 更新 Secret 即可。

**Q: 会消耗 WorkBuddy 积分吗？**
A: 不会。只调用签到接口，不触发任何模型调用。GitHub Actions 本身在免费额度内（私有仓库每月 2000 分钟，本任务每次约 1 分钟）。

**Q: 和小程序/客户端签到冲突吗？**
A: 不会。脚本先查 `checkin-status`，当天已签就跳过，服务端也只允许一天一次。

**Q: 会不会被判定为脚本刷签到？**
A: 每天只请求一次，模拟的是正常网页操作，风险很低。不建议提高频率。
