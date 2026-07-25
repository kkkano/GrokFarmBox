# Cloudflare 临时邮箱配置（傻瓜点击版）

> 目标：拥有一个 `*@yourdomain.com` 可程序化创建/收信的临时邮箱，给 Grok 注册收验证码用。

## 0. 你要得到的三样东西

做完以后，在 GrokFarmBox「设置」里填：

| 字段 | 例子 |
|---|---|
| Worker API Base | `https://mail.yourdomain.com` |
| Admin Token | 你自己设的超长密码 |
| 邮箱域名 | `yourdomain.com` |

---

## 1. 域名接入 Cloudflare

1. 打开 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 左侧点 **Websites**
3. 右上角 **Add a site**
4. 输入域名 → 继续
5. 套餐选 **Free**
6. Cloudflare 显示 2 个 Nameserver（NS）
7. 去你的域名注册商（阿里云/Namecheap/Cloudflare Registrar…）把 NS 改成这两条
8. 回到 Cloudflare，等状态变成 **Active**

**你会点哪里：**
- Dashboard 首页 → Websites → Add a site
- 域名注册商控制台 → DNS / Nameservers

---

## 2. 创建 D1 数据库

临时邮箱项目用 D1 存邮件。

1. 左侧菜单 **Workers & Pages**
2. 点顶部/侧边的 **D1**
3. **Create database**
4. 名称填：`temp-mail-db`（随便，记下来）
5. Create

**路径记忆：** Workers & Pages → D1 → Create database

---

## 3. 部署临时邮箱 Worker

推荐开源项目：[`dreamhunter2333/cloudflare_temp_email`](https://github.com/dreamhunter2333/cloudflare_temp_email)

### 3.1 一键/按官方 README 部署

1. 打开上面的 GitHub
2. 按 README 的 **Deploy** / `wrangler` 说明操作
3. 部署成功后，Cloudflare 会给你一个 `*.workers.dev` 地址

### 3.2 必配变量

进入 Worker → **Settings** → **Variables and Secrets**：

| 名称 | 类型 | 值 |
|---|---|---|
| `ADMIN_PASSWORDS` | Secret | 自己生成的长随机串（这就是 Admin Token） |

> 有的版本字段名可能是 `ADMIN_PASSWORD` / `ADMIN_PASS`——以你克隆的 README 为准。

### 3.3 绑定 D1

Worker → **Settings** → **Bindings** → **Add** → D1：

- Variable name：按项目文档（常见 `DB`）
- D1 database：选 `temp-mail-db`

保存后 **Deploy** 一次。

---

## 4. 绑定自定义域名

`*.workers.dev` 能用，但建议绑自己的子域：

1. 打开该 Worker
2. **Settings** → **Domains & Routes**
3. **Add** → **Custom Domain**
4. 填 `mail.yourdomain.com`
5. 等 SSL 变成 Active
6. 浏览器访问 `https://mail.yourdomain.com` 确认不是 404/522

---

## 5. Email Routing（最容易漏！）

没有这一步，邮箱“创建成功”也收不到 Grok 验证码。

1. 选中你的**域名**（不是 Worker）
2. 左侧 **Email** → **Email Routing**
3. 点 **Get started / Enable**
4. **Destination addresses**：先添加并验证一个真实邮箱（Cloudflare 强制要求）
5. 打开 **Routing rules**
6. 配置 **Catch-all address**：
   - Action：**Send to a Worker**
   - Worker：选你的 temp-mail Worker
7. Save

**检查清单：**
- [ ] Email Routing = Enabled
- [ ] Catch-all → Worker（不是 forward 到个人邮箱）
- [ ] Worker 已绑定 D1
- [ ] Admin Token 已设

---

## 6. 填回 GrokFarmBox

打开软件 → **设置**：

```
Worker API Base = https://mail.yourdomain.com
Admin Token     = （ADMIN_PASSWORDS 的值）
邮箱域名         = yourdomain.com
鉴权模式         = x-admin-auth   # 若 401 再试 bearer / x-api-key
```

保存后，把外部注册机（若使用）也指向同一套 CF 邮箱配置。

---

## 7. 常见问题速查

### 7.1 创建邮箱返回 401 / 403
- Admin Token 填错
- 鉴权模式不匹配（`x-admin-auth` / `bearer` / `x-api-key` / `query-key` / `none`）
- Worker 变量没 Deploy 生效

### 7.2 创建成功，但一直等不到验证码
1. Email Routing 是否 Enable
2. Catch-all 是否指向 **Worker**
3. 域名 MX 记录是否由 Cloudflare Email Routing 托管
4. 到 Worker 日志看有没有入站邮件事件

### 7.3 Worker 5xx
- D1 绑定名不对 / 没绑
- 数据库是空的，项目需要初始化 SQL（看官方 README 的 schema）

### 7.4 自定义域 526 / 522
- SSL/TLS 模式建议 Full
- 等证书签发完成再测

### 7.5 OTP 抽错 / 抽不到
- 打开邮件 raw，看验证码是不是 6 位
- 排除邮件里的颜色值、时间戳、邮箱本地部分误伤

---

## 8. 和本软件其它模块的关系

```
CF 临时邮箱 ──收验证码──▶ 注册机(浏览器自动化)
                              │
                              ▼
                         cpa_auths/*.json
                              │
                              ▼
              GrokFarmBox 导入 ──▶ sub2api grok 分组
                              │
                              ├─ 一键测活
                              ├─ 自动杀号(402/403/502…)
                              └─ 额度抽样 / 冒烟
```

---

## 9. 安全提醒

- Admin Token 等同于邮箱管理员密码，不要发到公开群
- 本软件配置只存在本机 `data/config.json`
- 生产环境建议限制 Worker 的管理接口，仅本机/受控网络使用
