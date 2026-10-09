"""
Portal Auto Data Downloader - Interactive Version
- Y dabao: kal ka data (normal)
- N dabao: manual date range
Headless mode - PC lock hone par bhi chalti hai
"""

import os
import sys
import time
import re
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ============= CONFIG =============
USERNAME = "12202006"
PASSWORD = "JCB@2889"
PORTAL_URL = "http://10.0.1.14/portal/index.php"
DOWNLOAD_FOLDER = r"C:\PortalData"

# Headless: True = PC lock hone par bhi chalega
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


LOG_FILE = None


def init_log():
    global LOG_FILE
    try:
        log_dir = Path(DOWNLOAD_FOLDER) / "_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        LOG_FILE = open(log_path, "a", encoding="utf-8")
    except Exception as e:
        print(f"Log file nahi ban payi: {e}")
        LOG_FILE = None


def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        try:
            LOG_FILE.write(line + "\n")
            LOG_FILE.flush()
        except:
            pass


def validate_date(date_str):
    """
    Date format check karo: DD-MM-YYYY
    Return: (True, datetime) ya (False, error_msg)
    """
    date_str = date_str.strip()
    
    # Format check: DD-MM-YYYY
    pattern = r'^(\d{1,2})-(\d{1,2})-(\d{4})$'
    match = re.match(pattern, date_str)
    
    if not match:
        return False, "Format galat hai. DD-MM-YYYY use karo (jaise 01-02-2026)"
    
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    
    try:
        d = datetime(year, month, day)
    except ValueError:
        return False, f"Ye date valid nahi hai: {date_str}"
    
    # Future date check
    if d.date() > datetime.now().date():
        return False, "Future date nahi de sakte"
    
    return True, d


def ask_user_choice():
    """
    User se poochho: kal ka data ya range
    Return: (from_date_str, to_date_str) DD/MM/YYYY format me
    """
    
    print()
    print("=" * 60)
    print("  PORTAL DOWNLOADER - KYA DOWNLOAD KARNA HAI?")
    print("=" * 60)
    print()
    print("  [Y] Kal ka data (default - 1 din)")
    print("  [N] Manual date range")
    print()
    
    while True:
        choice = input("  Aapka choice (Y/N): ").strip().upper()
        
        if choice in ("Y", "YES", ""):
            # Kal ka data
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime("%d/%m/%Y")
            print()
            print(f"  ✅ Kal ka data select kiya: {date_str}")
            print()
            return date_str, date_str
        
        elif choice in ("N", "NO"):
            # Manual range
            print()
            print("=" * 60)
            print("  MANUAL DATE RANGE")
            print("=" * 60)
            print()
            print("  ⚠️  FORMAT DHYAN SE PADHO:")
            print()
            print("      DD-MM-YYYY")
            print()
            print("      Example:")
            print("        01-02-2026   (1 February 2026)")
            print("        15-10-2026   (15 October 2026)")
            print()
            print("=" * 60)
            print()
            
            # From date
            while True:
                from_input = input("  From Date (DD-MM-YYYY): ").strip()
                valid, result = validate_date(from_input)
                if valid:
                    from_dt = result
                    break
                else:
                    print(f"  ❌ {result}")
                    print()
            
            # To date
            while True:
                to_input = input("  To Date   (DD-MM-YYYY): ").strip()
                valid, result = validate_date(to_input)
                if valid:
                    to_dt = result
                    break
                else:
                    print(f"  ❌ {result}")
                    print()
            
            # Check: from <= to
            if from_dt > to_dt:
                print()
                print("  ❌ From date, To date se badi nahi ho sakti!")
                print("  Dobara try karo.")
                print()
                continue
            
            # Convert to DD/MM/YYYY (portal format)
            from_str = from_dt.strftime("%d/%m/%Y")
            to_str = to_dt.strftime("%d/%m/%Y")
            
            days_diff = (to_dt - from_dt).days + 1
            
            print()
            print("=" * 60)
            print(f"  ✅ Range confirm:")
            print(f"     From: {from_str}")
            print(f"     To  : {to_str}")
            print(f"     Total: {days_diff} din")
            print("=" * 60)
            print()
            
            # Final confirm
            confirm = input("  Confirm? (Y/N): ").strip().upper()
            if confirm in ("Y", "YES", ""):
                return from_str, to_str
            else:
                print()
                print("  Dobara try karo...")
                print()
                continue
        
        else:
            print("  ❌ Sirf Y ya N likho")
            print()


def download_units(from_date, to_date):
    """Main automation function"""

    init_log()

    Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    today_folder = os.path.join(DOWNLOAD_FOLDER, datetime.now().strftime("%Y-%m-%d"))
    Path(today_folder).mkdir(parents=True, exist_ok=True)

    log("=" * 60)
    log("PORTAL AUTO DOWNLOADER - INTERACTIVE")
    log(f"Data Range      : {from_date} se {to_date}")
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
            log(f"Browser launch fail: {e}", "ERROR")
            return

        try:
            context = browser.new_context(
                accept_downloads=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768}
            )

            page = context.new_page()
            page.set_default_timeout(30000)

            # STEP 1: Portal kholo
            log(f"[2/6] Portal khol raha hu: {PORTAL_URL}")
            page.goto(PORTAL_URL, timeout=30000)
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # STEP 2: Login
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

            # STEP 3: Dashboard link
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

            if dashboard_url.startswith("../"):
                dashboard_url = "http://10.0.1.14/portal/" + dashboard_url[3:]
            elif dashboard_url.startswith("/"):
                dashboard_url = "http://10.0.1.14" + dashboard_url

            log(f"      Dashboard URL: {dashboard_url}")

            # STEP 4: Dashboard kholo
            log("[5/6] Dashboard khol raha hu...")
            page.goto(dashboard_url, timeout=30000)
            page.wait_for_load_state("networkidle")
            time.sleep(3)

            if not page.query_selector("#site"):
                log("Dashboard me 'site' dropdown nahi mila!", "WARN")
            else:
                log("      Dashboard ready hai")

            # STEP 5: Har unit ka data
            log(f"[6/6] {len(UNITS)} units ka data download kar raha hu...")
            log(f"      Date Range: {from_date} to {to_date}")

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

                    # Export
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

            # SUMMARY
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
        # User se poochho
        from_date, to_date = ask_user_choice()
        
        # Download karo
        download_units(from_date, to_date)
        
    except KeyboardInterrupt:
        print("\n\nUser ne cancel kiya.")
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        traceback.print_exc()

    # Log close
    if LOG_FILE:
        try:
            LOG_FILE.close()
        except:
            pass

    # Window band na ho
    try:
        if sys.stdout.isatty():
            input("\nBand karne ke liye Enter dabao...")
    except:
        pass
