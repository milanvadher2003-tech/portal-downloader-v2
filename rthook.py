"""
Runtime hook — Playwright ko batata hai ki bundled Chromium kahan hai
PyInstaller EXE ke andar se Playwright ko sahi path deta hai
"""

import os
import sys

# PyInstaller temp folder (_MEIxxxxxx) ya script folder
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
else:
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# Bundled browsers ka path
bundled_browsers = os.path.join(bundle_dir, 'playwright_browsers')

# Agar bundled browsers mile, to environment variable set karo
if os.path.exists(bundled_browsers):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = bundled_browsers
    print(f"[rthook] PLAYWRIGHT_BROWSERS_PATH = {bundled_browsers}")
else:
    print(f"[rthook] Bundled browsers nahi mile: {bundled_browsers}")
    print(f"[rthook] Fallback: default Playwright path use hoga")
