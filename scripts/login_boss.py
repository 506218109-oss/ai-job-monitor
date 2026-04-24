#!/usr/bin/env python3
"""
BOSS直聘登录助手

打开一个可见的 Chrome 浏览器，跳转到 BOSS直聘 登录页面。
用户用微信扫码登录后，浏览器状态（Cookie、LocalStorage等）会自动保存到本地。
之后运行 scrape 时会复用这个登录状态。

使用方法：
    python3 scripts/login_boss.py

如果登录过期（通常7-30天），重新运行此脚本即可。
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from playwright.async_api import async_playwright

PROFILE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "backend", "data", "browser_profile"
)
os.makedirs(PROFILE_DIR, exist_ok=True)


async def main():
    print("=" * 60)
    print("BOSS直聘 登录助手")
    print("=" * 60)
    print()
    print("即将打开浏览器窗口...")
    print("1. 在浏览器中点击「登录」")
    print("2. 用微信扫码完成登录")
    print("3. 登录成功后，回到这里按 Enter 键保存状态并关闭")
    print()
    print(f"浏览器数据保存在: {PROFILE_DIR}")
    print()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        """)

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.zhipin.com/web/user/?ka=header-login", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        print("请在浏览器中完成登录...")
        print()

        input("登录完成后按 Enter 键关闭浏览器... ")

        await context.close()
        print("登录状态已保存！")
        print("现在可以运行抓取: make scrape")


if __name__ == "__main__":
    asyncio.run(main())
