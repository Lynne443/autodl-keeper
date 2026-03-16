# AutoDL 释放时间守护

自动刷新 [AutoDL](https://www.autodl.com) 容器实例的释放倒计时，避免实例因长时间未使用被平台回收。

---

## 功能说明

- **一键刷新**：点击按钮对账号下所有实例执行一次「无卡开机 → 等待 → 关机」操作，将释放时间重置为 15 天后
- **实时日志**：操作过程中的日志实时滚动显示在界面内
- **自动登录**：首次使用时会弹出浏览器引导完成 AutoDL 登录，Token 自动保存，后续无需重复登录
- **串行处理**：AutoDL 同一时刻只允许一个无卡实例运行，程序会逐个处理每个实例

## 原理说明

### 释放时间机制

AutoDL 的容器实例在**关机状态下**会从上次关机时刻起计 **15 天**后自动释放。
因此只需定期做一次「开机 + 关机」，即可将释放时间重置回 15 天后，避免实例被回收。

```
上次关机时间 + 15天 = 实例释放时间
```

### Token 获取原理

AutoDL 的 API 使用 JWT Token 进行鉴权（请求头 `Authorization: eyJ...`）。
程序通过 Playwright 启动一个持久化 Chromium 浏览器：

1. 打开 AutoDL 登录页，等待用户手动完成登录（支持验证码、短信等所有方式）
2. 登录成功后自动跳转到实例列表页，拦截页面发出的 API 请求
3. 从请求头中提取 Token，保存到本地 `token.json`
4. 后续启动直接读取 `token.json`，无需重复登录

如果 Token 过期，程序会自动删除旧 Token 并重新弹出浏览器登录。

### 技术架构

```
AutoDL.exe
├── PyWebView (Edge WebView2)   ← 原生窗口容器
│   └── React + Vite            ← 前端 UI
│       └── HTTP 轮询 /api/logs ← 实时日志
└── Flask (127.0.0.1:7890)      ← 后端 API
    ├── autodl_keeper.py        ← 核心业务逻辑
    └── get_token.py            ← Playwright 自动登录
```

---

## 直接使用（EXE）

在 [Releases](../../releases) 页面下载最新版，解压后双击 `AutoDL.exe` 即可。

**注意**：分发的是整个文件夹，不能只运行单个 `AutoDL.exe`。

---

## 从源码构建

### 环境要求

- Python 3.11+
- Node.js 18+

### 构建步骤

```bat
git clone https://github.com/your-username/autodl-keeper.git
cd autodl-keeper
build.bat
```

`build.bat` 会自动完成以下步骤：
1. 编译 React 前端（`npm install` + `npm run build`）
2. 安装 Python 依赖（Flask、PyWebView、Playwright、PyInstaller）
3. 自动查找本机 Playwright Chromium，打包进 EXE
4. 输出到 `dist/AutoDL/AutoDL.exe`

### 开发调试

```bash
# 安装依赖
pip install flask pywebview playwright requests
playwright install chromium
cd ui && npm install && npm run build && cd ..

# 运行（开发模式）
python main.py

# 仅测试 API 连通性
python test_connection.py
```

---

## 文件结构

```
├── main.py              # 入口：启动 Flask + PyWebView 窗口
├── app.py               # Flask 后端，提供 /api/logs 和 /api/refresh 接口
├── autodl_keeper.py     # 核心逻辑：AutoDLClient、实例操作、释放时间计算
├── get_token.py         # Playwright 自动登录，获取并缓存 JWT Token
├── test_connection.py   # 连通性测试脚本
├── build.bat            # 一键构建脚本
└── ui/
    └── src/
        ├── App.tsx      # React 主界面
        └── App.css      # 样式
```

---

## 注意事项

- `token.json` 和 `browser_profile/` 包含登录凭据，**不要上传到公开仓库**（已在 `.gitignore` 中排除）
- 如需更换账号，删除 `token.json` 后重新打开程序重新登录即可
- AutoDL 同一时刻只允许一个无卡实例开机，程序已按串行顺序处理
