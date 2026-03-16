"""
通过 Playwright 打开浏览器，用户登录后自动跳转实例列表、提取 Token 并关闭浏览器
"""
import json
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright


def _base_dir() -> Path:
    """打包后返回 EXE 所在目录，开发时返回源码目录"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


if getattr(sys, 'frozen', False):
    # 打包后让 playwright 使用包内自带的浏览器
    import os
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'


_BASE = _base_dir()
TOKEN_FILE = _BASE / "token.json"
BROWSER_PROFILE = _BASE / "browser_profile"
INSTANCE_SAMPLE_FILE = _BASE / "instance_sample.json"


async def _fetch_token() -> str | None:
    captured = {"token": None}
    BROWSER_PROFILE.mkdir(exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            headless=False,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")

        def handle_request(request):
            auth = request.headers.get("authorization")
            if auth and auth.startswith("eyJ") and "/api/v1/" in request.url:
                captured["token"] = auth

        async def handle_response(response):
            # 拦截实例列表响应，保存字段样本
            if "/api/v1/instance" in response.url and "?" not in response.url:
                try:
                    data = await response.json()
                    instances = data.get("data", {}).get("list", [])
                    if instances:
                        INSTANCE_SAMPLE_FILE.write_text(
                            json.dumps(instances[0], ensure_ascii=False, indent=2)
                        )
                except Exception:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        print(">>> 浏览器已打开，请完成登录...")
        await page.goto("https://www.autodl.com/login")

        # 等待登录成功（URL 跳转离开 /login 页面）
        await page.wait_for_url(
            lambda url: "login" not in url,
            timeout=300_000,
        )

        # 登录成功后跳转到实例列表，触发 API 请求
        await page.goto("https://www.autodl.com/console/instance/list")
        await asyncio.sleep(3)  # 等待 API 请求发出

        await context.close()

    return captured["token"]


def get_token() -> str:
    if TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text())
            token = data.get("token", "")
            if token and token.startswith("eyJ"):
                return token
        except Exception:
            pass

    print(">>> 未找到有效 Token，启动浏览器登录 ...")
    token = asyncio.run(_fetch_token())

    if token:
        TOKEN_FILE.write_text(json.dumps({"token": token}, ensure_ascii=False))
        print(f"[OK] Token saved to {TOKEN_FILE.name}")
        return token
    else:
        print("[ERROR] Token not captured, please retry")
        sys.exit(1)


def refresh_token() -> str:
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    return get_token()


if __name__ == "__main__":
    token = refresh_token()
    print(f"[OK] Token: {token[:40]}...")
