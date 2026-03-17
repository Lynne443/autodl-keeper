# AutoDL 释放时间守护

定时刷新 AutoDL 容器实例的释放倒计时，防止实例被回收。

## 怎么用

### 直接下载

去 [Releases](../../releases) 下载最新版，解压整个文件夹，双击 `AutoDL.exe` 运行。

> 不能只拷贝单个 exe 出来跑，要保留完整目录结构。

### 从源码构建

需要 Python 3.11+、Node.js 18+。

```bash
git clone https://github.com/Lynne443/autodl-keeper.git
cd autodl-keeper
build.bat
```

构建产物在 `dist/AutoDL/AutoDL.exe`。

### 开发调试

```bash
pip install flask pywebview playwright requests
playwright install chromium
cd ui && npm install && npm run build && cd ..
python main.py
```

## 它做了什么

AutoDL 的实例关机后 15 天没动静就会被释放。这个工具就是帮你自动做一轮「无卡开机 → 关机」，把释放时间重置回 15 天后。

首次使用会弹浏览器让你登录 AutoDL，登录后 Token 自动保存到本地，之后就不用再登了。Token 过期会自动重新弹登录。

## 项目结构

```
main.py              # 入口，启动 Flask + PyWebView
app.py               # 后端 API
autodl_keeper.py     # 核心逻辑：开关机、释放时间计算
get_token.py         # Playwright 自动登录拿 Token
build.bat            # 构建脚本
ui/src/App.tsx       # 前端界面
```

## 注意

- `token.json` 和 `browser_profile/` 含登录凭据，别传到公开仓库（已加 `.gitignore`）
- 换账号的话删掉 `token.json` 重新打开就行
