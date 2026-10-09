"""
Portal Auto Data Downloader - Headless Version
PC lock hone par bhi chalti hai
Kal ka data, 10 units, automatic download
"""

import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ============= CONFIG =============
USERNAME = "12202006"
PASSWORD = "JCB@2889"
PORTAL_URL = "http://10.0.1.14/portal/index.php"
DOWNLOAD_FOLDER = r"C:\PortalData"

# Headless: True = PC lock hone par bhi chalega, screen nahi dikhega
#           False = screen par dikhega (debugging ke liye)
HEADLESS = True

UNITS = [
    ("Krishna",  "17423313"),
    ("SG",       "17423312"),
    ("Indore",   "17423317"),
    ("Jabalpur", "17423318"),
    ("Jaipur",   "17423461"),
    ("Mohali",   "17423460"),
    ("Vapi",     "17423464"),
    ("Vijay",    "17423315"),
    ("Naroda",   "17423314"),
    ("Surat",    "17423463"),
]
# ==================================


# Global log file handle
LOG_FILE = None


def init_log():
    """Log file initialize karo"""
    global LOG_FILE
    try:
        log_dir = Path(DOWNLOAD_FOLDER) / "_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"run_{datetime.now().strftime('%Y-%m-%d')}.log"
        LOG_FILE = open(log_path, "a", encoding="utf-8")
    except Exception as e:
        print(f"Log file nahi ban payi: {e}")
        LOG_FILE = None


def log(msg, level="INFO"):
    """Console + log file me likho"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    
    # Console par print karo
    print(line, flush=True)
    
    # Log file me likho
    if LOG_FILE:
        try:
            LOG_FILE.write(line + "\n")
            LOG_FILE.flush()
        except:
            pass


def get_yesterday_dates():
    """Kal ki date — DD/MM/YYYY format"""
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%d/%m/%Y")
    return date_str, date_str


def download_units():
    """Main automation function"""

    init_log()
    from_date, to_date = get_yesterday_dates()

    # Folders banao
    Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    today_folder = os.path.join(DOWNLOAD_FOLDER, datetime.now().strftime("%Y-%m-%d"))
    Path(today_folder).mkdir(parents=True, exist_ok=True)

    log("=" * 60)
    log("PORTAL AUTO DOWNLOADER - HEADLESS")
    log(f"Data Date (Kal) : {from_date}")
    log(f"Save Folder     : {today_folder}")
    log(f"Username        : {USERNAME}")
    log(f"Total Units     : {len(UNITS)}")
    log(f"Headless Mode   : {HEADLESS}")
    log("=" * 60)

    with sync_playwright() as p:
        log("[1/6] Browser launch kar raha hu...")
        
        try:
            browser = p.chromium.launch(
                headless=HEADLESS,
                slow_mo=0 if HEADLESS else 200,
                args=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1366,768"
                ]
            )
            log("      Browser launched OK")
        except Exception as e:
            log(f"Browser launch fail: {e}")
            log("Chromium browser missing ho sakta hai!")
            return

        try:
            context = browser.new_context(
                accept_downloads=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768}
            )

            page = context.new_page()
            page.set_default_timeout(30000)

            # ---------- STEP 1: Portal kholo ----------
            log(f"[2/6] Portal khol raha hu: {PORTAL_URL}")
            page.goto(PORTAL_URL, timeout=30000)
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # ---------- STEP 2: Login ----------
            log("[3/6] Login kar raha hu...")

            page.fill("#j_username", USERNAME)
            time.sleep(0.3)
            page.fill("input[name='j_password']", PASSWORD)
            time.sleep(0.3)
            page.click("input[name='Login']")
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(3)

            current_url = page.url
            log(f"      Current URL: {current_url}")

            if "Invalid" in current_url:
                log("LOGIN FAIL! Username/Password galat.", "ERROR")
                return

            log("      Login OK")

            # ---------- STEP 3: Dashboard link ----------
            log("[4/6] NMI Dashboard link dhundh raha hu...")

            dashboard_url = None
            links = page.query_selector_all("a")
            for link in links:
                try:
                    text = link.inner_text() or ""
                    if "NMI Dashboard" in text:
                        dashboard_url = link.get_attribute("href")
                        break
                except:
                    continue

            if not dashboard_url:
                log("NMI Dashboard link nahi mila!", "ERROR")
                return

            # Relative URL ko absolute banao
            if dashboard_url.startswith("../"):
                dashboard_url = "http://10.0.1.14/portal/" + dashboard_url[3:]
            elif dashboard_url.startswith("/"):
                dashboard_url = "http://10.0.1.14" + dashboard_url

            log(f"      Dashboard URL: {dashboard_url}")

            # ---------- STEP 4: Dashboard kholo ----------
            log("[5/6] Dashboard khol raha hu...")
            page.goto(dashboard_url, timeout=30000)
            page.wait_for_load_state("networkidle")
            time.sleep(3)

            if not page.query_selector("#site"):
                log("Dashboard me 'site' dropdown nahi mila!", "WARN")
            else:
                log("      Dashboard ready hai")

            # ---------- STEP 5: Har unit ka data ----------
            log(f"[6/6] {len(UNITS)} units ka data download kar raha hu...")

            success_count = 0
            failed_units = []

            for idx, (unit_name, unit_value) in enumerate(UNITS, 1):
                log("-" * 50)
                log(f"[{idx}/{len(UNITS)}] UNIT: {unit_name} ({unit_value})")

                try:
                    # Unit select
                    page.select_option("#site", value=unit_value)
                    time.sleep(1)

                    # From Date
                    page.evaluate(f"""
                        var fd = document.getElementById('txt_fromdt');
                        if (fd) {{
                            fd.removeAttribute('readonly');
                            fd.value = '{from_date}';
                            fd.dispatchEvent(new Event('change', {{bubbles: true}}));
                            fd.dispatchEvent(new Event('blur', {{bubbles: true}}));
                        }}
                    """)
                    time.sleep(0.8)

                    # To Date
                    page.evaluate(f"""
                        var td = document.getElementById('txt_todt');
                        if (td) {{
                            td.removeAttribute('readonly');
                            td.value = '{to_date}';
                            td.dispatchEvent(new Event('change', {{bubbles: true}}));
                            td.dispatchEvent(new Event('blur', {{bubbles: true}}));
                        }}
                    """)
                    time.sleep(0.8)

                    # Submit
                    log(f"      Submit...")
                    page.click("#Submit")
                    page.wait_for_load_state("networkidle", timeout=20000)
                    time.sleep(3)

                    # Export — download handle karo
                    log(f"      Export...")
                    with page.expect_download(timeout=30000) as download_info:
                        page.click("#export")

                    download = download_info.value
                    suggested_name = download.suggested_filename or f"{unit_name}.xlsb"
                    ext = os.path.splitext(suggested_name)[1] or ".xlsb"
                    save_name = f"{unit_name}{ext}"
                    save_path = os.path.join(today_folder, save_name)

                    download.save_as(save_path)
                    log(f"      SAVED: {save_name}", "OK")

                    success_count += 1

                    # Agli unit ke liye dashboard reload
                    if idx < len(UNITS):
                        page.goto(dashboard_url, timeout=30000)
                        page.wait_for_load_state("networkidle")
                        time.sleep(2)

                except PlaywrightTimeout:
                    log(f"      TIMEOUT — {unit_name} fail", "ERROR")
                    failed_units.append(unit_name)
                    try:
                        page.goto(dashboard_url, timeout=30000)
                        page.wait_for_load_state("networkidle")
                        time.sleep(2)
                    except:
                        pass
                    continue

                except Exception as e:
                    log(f"      ERROR: {e}", "ERROR")
                    failed_units.append(unit_name)
                    try:
                        page.goto(dashboard_url, timeout=30000)
                        page.wait_for_load_state("networkidle")
                        time.sleep(2)
                    except:
                        pass
                    continue

            # ---------- SUMMARY ----------
            log("=" * 60)
            log(f"KAAM PURA HUA!", "OK")
            log(f"Success: {success_count}/{len(UNITS)}", "OK")
            log(f"Files  : {today_folder}", "OK")

            if failed_units:
                log(f"Failed : {', '.join(failed_units)}", "ERROR")

            log("=" * 60)

        except Exception as e:
            log(f"MAIN ERROR: {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")

        finally:
            try:
                browser.close()
                log("Browser band kar diya")
            except:
                pass


if __name__ == "__main__":
    try:
        download_units()
    except KeyboardInterrupt:
        log("User ne cancel kiya")
    except Exception as e:
        log(f"FATAL ERROR: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")

    # Log file close karo
    if LOG_FILE:
        try:
            LOG_FILE.close()
        except:
            pass

    # Console window band na ho jaye
    try:
        if sys.stdout.isatty():
            input("\nBand karne ke liye Enter dabao...")
    except:
        pass
