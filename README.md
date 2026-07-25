# GrokFarmBox

傻瓜式 **Grok 号池管理台**（Windows GUI / 可打包 EXE）

把「注册机产出的 OAuth 凭证」管起来：一键导入 [sub2api](https://github.com/), 验证 grokbuild、测活、可选自动清理失效号、抽样看额度；并内置 **Cloudflare 临时邮箱** 从零点击教程。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![UI](https://img.shields.io/badge/UI-Flask%20%2B%20HTML%2FCSS%2FJS-000000)
![Pack](https://img.shields.io/badge/Pack-PyInstaller-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 功能

| 模块 | 能力 |
|---|---|
| 仪表盘 | 号池概况、账号列表、运行日志 |
| 导入 | 扫描 `cpa_auths/*.json` → 写入 sub2api grok 分组，可挂代理 |
| 测活 | 管理端 account test + 业务 key 冒烟 `grok-4.5` |
| 自动杀号 | 402/403/permission-denied/quota 等硬失败可自动删除 |
| 额度监控 | 抽样 remaining requests / tokens |
| 农场循环 | 可选挂接外部注册命令，循环：注册→导入→测活 |
| CF 教程 | 域名 / D1 / Worker / Email Routing 逐步点哪里 |

### 安全默认

- 仅操作 **安全邮箱后缀** 匹配的账号（设置里可改）
- 不匹配的账号只读统计，不会被导入逻辑覆盖，也不会被清理删除
- 密钥只存在本机 `data/config.json`

---

## 截图位置（可自行补）

```
assets/screenshot-dashboard.png
assets/screenshot-settings.png
assets/screenshot-guide.png
```

---

## 开发运行

```bash
git clone https://github.com/kkkano/GrokFarmBox.git
cd GrokFarmBox
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 打包 EXE

```bash
scripts\build_exe.bat
```

输出：`dist/GrokFarmBox/GrokFarmBox.exe`  
首次运行自动创建 `data/`（配置、日志、CPA 目录）。

---

## 推荐使用顺序

1. 打开软件 → **CF 教程**，把临时邮箱跑通  
2. **设置** 填写 sub2api 地址 / 管理员账号 / 分组 ID / 代理 ID / 安全后缀  
3. （可选）填写外部注册命令，挂接现有 `grok-register`  
4. **仪表盘**：刷新概况 → 导入 CPA → 一键测活 → 需要挂机再开农场循环  

更细的说明见 [`docs/user_guide.md`](docs/user_guide.md)  
Cloudflare 逐步图文见 [`docs/cloudflare_temp_email.md`](docs/cloudflare_temp_email.md)

---

## 配置项摘要

| 键 | 含义 |
|---|---|
| `sub2api_base` | 网关地址 |
| `sub2api_email` / `sub2api_password` | 管理员登录 |
| `sub2api_group_id` | grok 分组 ID |
| `sub2api_proxy_id` | 代理 ID，`0` 表示不绑定 |
| `sub2api_safe_suffix` | 仅操作此外缀邮箱账号 |
| `external_register_cmd` | 外部注册命令（可空） |
| `external_register_cwd` | 外部注册工作目录 |
| `auto_kill_bad` | 测活失败是否删除 |
| `cf_*` | Cloudflare 临时邮箱参数 |

---

## 目录

```
GrokFarmBox/
├── main.py                 # 入口（Flask）
├── app/
│   ├── config.py           # 配置
│   ├── web/                # 前端：index.html / styles.css / app.js
│   ├── web_api.py          # Flask API 桥
│   ├── webapp.py           # 窗口启动
│   └── services/           # sub2api / 号池 / 农场
├── vendor/grok-register/   # 内置注册机(基于 AaronL725/grok-register, MIT, 含静默改动)
├── docs/                   # 教程与用户手册
├── scripts/                # 打包脚本
├── assets/
└── data/                   # 运行时生成（不进 git）
```

## 界面

Grok 风黑白极简：纯黑底 + 白字、白底黑字主按钮，Hanken Grotesk + Spline Sans Mono 字体，品牌区与页头植入 Grok logo。
教程页用内置零依赖 markdown 渲染器正确排版（标题 / 表格 / 代码块 / 引用 / 列表）。

---

## 内置注册机 (vendor/grok-register)

本项目**内置** `vendor/grok-register/`（基于 [AaronL725/grok-register](https://github.com/AaronL725/grok-register)，MIT License，已含「静默注册」改动）。开箱默认调用它，无需另装。

首次使用需在 vendor 里建虚拟环境装依赖：
```bat
cd vendor\grok-register
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

GrokFarmBox 默认配置已指向 `vendor/grok-register`，启动农场循环即可：注册（浏览器静默移屏外）→ 产出 cpa_auths → 导入 sub2api → 测活。

> 也可在设置里改成外部 grok-register 路径（自己独立维护的版本）。

---

## 免责声明

仅供学习、测试与个人号池运维。请遵守 xAI / Cloudflare / 其它服务条款与当地法律。作者不对滥用后果负责。

## 致谢

`vendor/grok-register/` 源自 [AaronL725/grok-register](https://github.com/AaronL725/grok-register)（MIT License, Copyright (c) 2026 AaronL725），完整保留原作者的 LICENSE 与代码，仅新增「静默注册（窗口移屏外）」4 行改动。GrokFarmBox 在其注册能力之上构建号池管理：sub2api 导入、测活/清理、额度监控与傻瓜式 UI。感谢 AaronL725 的开源贡献。

## License

MIT
