# GrokFarmBox 使用说明

## 这是什么

Windows 傻瓜式 **Grok 号池管理台**：

- 导入 CPA / xAI OAuth 凭证到 **sub2api**
- 自动验证 grokbuild（account test + 可选 chat 冒烟）
- 一键测活 / 可选自动杀坏号
- 额度抽样与号池健康概览
- 内置 Cloudflare 临时邮箱点击教程
- 可挂接现有 `grok-register` 做循环刷号

## 快速开始（开发模式）

```bash
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

产物：`dist/GrokFarmBox/GrokFarmBox.exe`  
首次运行会在 exe 旁生成 `data/` 目录。

## 推荐配置流程

1. 先按 **CF 教程** 页把临时邮箱搞定  
2. **设置** 里填 sub2api：
   - Base URL（如 `http://175.x.x.x` 或域名）
   - 管理员邮箱/密码
   - Grok 分组 ID、代理 ID
   - 安全后缀（默认只动 `*@your-domain.com`）
3. 若本机已有 grok-register：
   - 外部注册命令：`C:\path\to\.venv\Scripts\python.exe grok_register_ttk.py cli`
   - 工作目录：`C:\path\to\grok-register`
4. 回仪表盘：
   - 刷新概况
   - 导入 CPA
   - 一键测活
   - 需要挂机再点「启动农场循环」

## 安全规则

- **只操作** `sub2api_safe_suffix` 匹配的账号（例如你自己批量注册用的域名后缀）
- 不匹配后缀的账号只统计数量，导入 / 测活 / 删除都不会碰
- 自动杀号默认开，可在设置关
- 若希望管理全部账号，把安全后缀留空（请谨慎）

## 额度说明（free grok build 实测）

单号窗口内常见：

- `limit-requests = 21`
- `limit-tokens = 1_000_000`

窗口耗尽会 402 spending-limit；清理任务会把硬失败号删掉，避免拖垮网关。

## 目录结构

```
GrokFarmBox/
  main.py
  app/
    config.py
    gui/
    services/
  docs/
  scripts/
  data/          # 运行时生成
```
