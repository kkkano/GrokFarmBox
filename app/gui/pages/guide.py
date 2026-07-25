"""Cloudflare 临时邮箱 + 域名 傻瓜式教程页。"""
from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from app.gui.theme import FONT_BODY, FONT_H2, FONT_MONO, FONT_TITLE

GUIDE_MD = Path(__file__).resolve().parents[3] / "docs" / "cloudflare_temp_email.md"


class GuidePage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Cloudflare 配置教程", font=FONT_TITLE).pack(
            anchor="w", padx=16, pady=(16, 4)
        )
        ctk.CTkLabel(
            self,
            text="按顺序点，别跳。做完把 Worker 地址 / Admin Token / 域名填到「设置」。",
            font=FONT_BODY,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # quick steps chips
        steps = ctk.CTkFrame(self)
        steps.pack(fill="x", padx=16, pady=8)
        for i, t in enumerate(
            [
                "1. 域名接入 CF",
                "2. 建 D1 数据库",
                "3. 部署 temp-mail Worker",
                "4. 绑自定义域",
                "5. 配 Email Routing",
                "6. 填回本软件",
            ],
            start=1,
        ):
            ctk.CTkLabel(steps, text=t, font=FONT_BODY, width=160).grid(
                row=(i - 1) // 3, column=(i - 1) % 3, padx=8, pady=6, sticky="w"
            )

        box = ctk.CTkTextbox(self, font=FONT_MONO)
        box.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        text = self._load_guide()
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _load_guide(self) -> str:
        if GUIDE_MD.exists():
            try:
                return GUIDE_MD.read_text(encoding="utf-8")
            except Exception as e:
                return f"读取教程失败: {e}"
        return FALLBACK_GUIDE


FALLBACK_GUIDE = """# Cloudflare 临时邮箱配置（点击路线图）

## 你需要准备
1. 一个域名（任意便宜域名都行）
2. Cloudflare 账号（免费计划即可）
3. 10-20 分钟

## Step 1 — 域名接入 Cloudflare
1. 打开 https://dash.cloudflare.com
2. 左侧点 **Websites** → **Add a site**
3. 输入你的域名 → 选 Free 计划
4. Cloudflare 会给你 2 个 NS，去域名注册商改 NS
5. 等 Status 变成 Active（可能几分钟到几小时）

## Step 2 — 创建 D1 数据库
1. 左侧 **Workers & Pages** → **D1**
2. **Create database**
3. 名字例如：`temp-mail-db`
4. 创建完点进去，记住 database name

## Step 3 — 部署 cloudflare_temp_email Worker
推荐项目：dreamhunter2333/cloudflare_temp_email

最省事方式（Pages/Worker 一键）：
1. 打开项目 README 的 Deploy 按钮（或按官方 wrangler 部署）
2. 在 Worker Settings → Variables 里设置：
   - `ADMIN_PASSWORDS` = 一串足够长的随机密码（这就是 Admin Token）
   - 绑定 D1：把刚才的 `temp-mail-db` 绑到变量名 `DB`（以项目文档为准）
3. 保存并 Deploy

如果用 wrangler：
```bash
npm i -g wrangler
wrangler login
# 按项目文档填 wrangler.toml 后
wrangler deploy
```

## Step 4 — 绑定自定义域
1. Worker 详情 → **Settings** → **Domains & Routes**
2. **Add** → Custom Domain
3. 例如：`mail.yourdomain.com`
4. 等 SSL 就绪
5. 浏览器打开 `https://mail.yourdomain.com` 应能访问

## Step 5 — Email Routing（关键：收信）
1. 域名 → **Email** → **Email Routing**
2. Enable Email Routing
3. **Destination addresses** 先随便验证一个真邮箱（CF 要求）
4. **Routing rules** → Catch-all：
   - 动作选 **Send to a Worker**
   - Worker 选你刚部署的 temp-mail
5. 保存

> 没有这一步，邮箱创建了也收不到验证码！

## Step 6 — 填回 GrokFarmBox
打开本软件「设置」：
- Worker API Base: `https://mail.yourdomain.com`
- Admin Token: 你设的 `ADMIN_PASSWORDS`
- 邮箱域名: `yourdomain.com`（或你配置的收信域）
- 鉴权模式: 一般 `x-admin-auth`（按你 Worker 版本）

## 常见踩坑
| 现象 | 原因 | 处理 |
|---|---|---|
| 创建邮箱 401/403 | Admin Token 错或鉴权模式不对 | 核对 ADMIN_PASSWORDS / auth mode |
| 创建成功但收不到信 | Email Routing 没指到 Worker | 查 Catch-all → Worker |
| Worker 502 | D1 没绑定 | Settings → 绑定 D1 |
| 域名打不开 | 自定义域/SSL 未好 | 等 Active，查 DNS |
| OTP 抽不到 | 邮件格式变了 | 看 raw 邮件，调提取规则 |

## 和 sub2api 的关系
- 临时邮箱只负责「注册时收验证码」
- 注册成功后的 OAuth 凭证进 `cpa_auths/`
- 本软件把凭证导入 sub2api 的 grok 分组，再测活/杀号/监控额度
"""
