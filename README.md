# GrokFarmBox

傻瓜式 **Grok 号池管理台**（Windows GUI / 可打包 EXE）

> 私有仓库。功能稳定后再考虑公开。

把「注册机产出的 OAuth 凭证」管起来：一键导入 [sub2api](https://github.com/), 验证 grokbuild、测活、可选自动清理失效号、抽样看额度；并内置 **Cloudflare 临时邮箱** 从零点击教程。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![UI](https://img.shields.io/badge/UI-CustomTkinter-blue)
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
├── main.py                 # 入口
├── app/
│   ├── config.py           # 配置
│   ├── gui/                # CustomTkinter 界面
│   └── services/           # sub2api / 号池 / 农场
├── docs/                   # 教程与用户手册
├── scripts/                # 打包脚本
├── assets/
└── data/                   # 运行时生成（不进 git）
```

---

## 和 grok-register 的关系

- **注册浏览器自动化**仍建议用成熟的 `grok-register`（DrissionPage + CPA 导出）
- **GrokFarmBox** 负责：导入 sub2api、验证、清理、监控、教程、傻瓜 UI / EXE
- 通过设置里的「外部注册命令」可以把两者串成一条挂机流水线

---

## 免责声明

仅供学习、测试与个人号池运维。请遵守 xAI / Cloudflare / 其它服务条款与当地法律。作者不对滥用后果负责。

## License

MIT
