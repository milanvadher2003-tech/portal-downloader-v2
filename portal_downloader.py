"""
Portal Auto Data Downloader - FINAL VERSION
- Interactive (Y = kal ka data, N = range)
- Headless (PC lock hone par bhi chalti hai)
- Auto ZIP banata hai
- Email automatically bhejta hai (SMTP), fail hone par mail window kholta hai
"""

import os
import sys
import time
import re
import zipfile
import smtplib
import traceback
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ============= PORTAL CONFIG =============
USERNAME = "12202006"
PASSWORD = "JCB@2889"
PORTAL_URL = "http://10.0.1.14/portal/index.php"
DOWNLOAD_FOLDER = r"C:\PortalData"
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

# ============= EMAIL CONFIG =============
# Email bhejna hai?
SEND_EMAIL = True

# Email kisko bhejni hai
EMAIL_TO = ["fa30.corp@shalby.in"]

# SMTP details — IceWarp
# Agar aapko exact details nahi pata, to script khud dono try karegi:
#   - Port 587 (TLS)
#   - Port 465 (SSL)
SMTP_SERVER = "shalbyhospitals.icewarpcloud.in"
SMTP_PORT = 587                # 587 ya 465 — script dono try karegi
SMTP_USERNAME = "fa30.corp@shalby.in"
SMTP_PASSWORD = "Shalby@123"    # <-- YAHAN APNA WEBMAIL PASSWORD DAALO

# ==========================================


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
    date_str = date_str.strip()
    pattern = r'^(\d{1,2})-(\d{1,2})-(\d{4})$'
    match = re.match(pattern, date_str)
    if not match:
        return False, "Format galat hai. DD-MM-YYYY use karo (jaise 01-02-2026)"
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        d = datetime(year, month, day)
    except ValueError:
        return False, f"Ye date valid nahi hai: {date_str}"
    if d.date() > datetime.now().date():
        return False, "Future date nahi de sakte"
    return True, d


def ask_user_choice():
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
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime("%d/%m/%Y")
            print()
            print(f"  ✅ Kal ka data select kiya: {date_str}")
            print()
            return date_str, date_str

        elif choice in ("N", "NO"):
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

            while True:
                from_input = input("  From Date (DD-MM-YYYY): ").strip()
                valid, result = validate_date(from_input)
                if valid:
                    from_dt = result
                    break
                else:
                    print(f"  ❌ {result}")
                    print()

            while True:
                to_input = input("  To Date   (DD-MM-YYYY): ").strip()
                valid, result = validate_date(to_input)
                if valid:
                    to_dt = result
                    break
                else:
                    print(f"  ❌ {result}")
                    print()

            if from_dt > to_dt:
                print()
                print("  ❌ From date, To date se badi nahi ho sakti!")
                print("  Dobara try karo.")
                print()
                continue

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


def make_zip(today_folder, from_date, to_date):
    """Saari files ko zip me pack karo"""
    try:
        from_clean = from_date.replace("/", "-")
        to_clean = to_date.replace("/", "-")

        if from_clean == to_clean:
            zip_name = f"PortalData_{from_clean}.zip"
        else:
            zip_name = f"PortalData_{from_clean}_to_{to_clean}.zip"

        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in os.listdir(today_folder):
                file_path = os.path.join(today_folder, file)
                if os.path.isfile(file_path):
                    zf.write(file_path, arcname=file)

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        log(f"ZIP banayi: {zip_name} ({zip_size_mb:.2f} MB)", "OK")
        return zip_path

    except Exception as e:
        log(f"ZIP banane me error: {e}", "ERROR")
        return None


def send_email_smtp(zip_path, from_date, to_date, success_count, failed_units):
    """SMTP se email bhejo (automatic)"""
    try:
        # Subject
        if from_date == to_date:
            subject = f"Portal Data - {from_date}"
        else:
            subject = f"Portal Data - {from_date} to {to_date}"

        # Body
        body = f"""Namaste,

Portal se data download ho gaya hai.

Details:
--------
Data Range    : {from_date} se {to_date}
Download Time : {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
Total Units   : {len(UNITS)}
Success       : {success_count}/{len(UNITS)}
"""
        if failed_units:
            body += f"Failed        : {', '.join(failed_units)}\n"

        body += f"""
Attached File : {os.path.basename(zip_path)}
ZIP Size      : {os.path.getsize(zip_path) / (1024*1024):.2f} MB

--
Portal Auto Downloader
(Automated email)
"""

        # Message banao
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = ", ".join(EMAIL_TO)
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        # ZIP attach karo
        with open(zip_path, "rb") as f:
            part = MIMEBase("application", "zip")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(zip_path)}"'
        )
        msg.attach(part)

        # SMTP try karo — pehle 587, phir 465
        ports_to_try = []
        if SMTP_PORT == 587:
            ports_to_try = [587, 465]
        elif SMTP_PORT == 465:
            ports_to_try = [465, 587]
        else:
            ports_to_try = [587, 465]

        last_error = None

        for port in ports_to_try:
            try:
                log(f"      SMTP try: {SMTP_SERVER}:{port}")

                if port == 465:
                    # SSL
                    server = smtplib.SMTP_SSL(SMTP_SERVER, port, timeout=30)
                else:
                    # TLS
                    server = smtplib.SMTP(SMTP_SERVER, port, timeout=30)
                    server.starttls()

                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
                server.quit()

                log(f"      ✅ Email bhej diya (port {port}): {', '.join(EMAIL_TO)}", "OK")
                return True

            except smtplib.SMTPAuthenticationError as e:
                log(f"      Port {port}: Authentication FAIL — username/password galat", "ERROR")
                last_error = f"Auth failed: {e}"
                continue  # Doosre port pe try karo

            except Exception as e:
                log(f"      Port {port} fail: {e}", "WARN")
                last_error = str(e)
                continue

        log(f"      SMTP se email nahi gaya. Last error: {last_error}", "ERROR")
        return False

    except Exception as e:
        log(f"Email error: {e}", "ERROR")
        return False


def send_email_outlook(zip_path, from_date, to_date):
    """Fallback: Outlook / Mail app se mail window kholo"""
    try:
        if from_date == to_date:
            subject = f"Portal Data - {from_date}"
        else:
            subject = f"Portal Data - {from_date} to {to_date}"

        body = f"""Namaste,

Portal se data download ho gaya hai.

Data Range: {from_date} to {to_date}
Attached File: {os.path.basename(zip_path)}

--
Portal Auto Downloader
"""

        # Try Outlook COM
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = "; ".join(EMAIL_TO)
            mail.Subject = subject
            mail.Body = body
            mail.Attachments.Add(zip_path)
            mail.Display()
            log("      Outlook me mail window khol diya", "OK")
            return True
        except ImportError:
            log("      Outlook COM available nahi", "WARN")
        except Exception as e:
            log(f"      Outlook fail: {e}", "WARN")

        # Fallback: mailto
        try:
            mailto = f"mailto:{EMAIL_TO[0]}?subject={subject}"
            os.startfile(mailto)
            log("      Default mail app khol diya (attachment manual add karni padegi)", "WARN")
            return True
        except Exception as e:
            log(f"      Mail app fail: {e}", "ERROR")

        return False

    except Exception as e:
        log(f"Outlook fallback error: {e}", "ERROR")
        return False


def download_units(from_date, to_date):
    init_log()

    Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    today_folder = os.path.join(DOWNLOAD_FOLDER, datetime.now().strftime("%Y-%m-%d"))
    Path(today_folder).mkdir(parents=True, exist_ok=True)

    log("=" * 60)
    log("PORTAL AUTO DOWNLOADER - FINAL")
    log(f"Data Range      : {from_date} se {to_date}")
    log(f"Save Folder     : {today_folder}")
    log(f"Username        : {USERNAME}")
    log(f"Email To        : {', '.join(EMAIL_TO)}")
    log(f"Total Units     : {len(UNITS)}")
    log(f"Headless Mode   : {HEADLESS}")
    log("=" * 60)

    success_count = 0
    failed_units = []

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

            log(f"[2/6] Portal khol raha hu: {PORTAL_URL}")
            page.goto(PORTAL_URL, timeout=30000)
            page.wait_for_load_state("networkidle")
            time.sleep(1)

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

            log("[5/6] Dashboard khol raha hu...")
            page.goto(dashboard_url, timeout=30000)
            page.wait_for_load_state("networkidle")
            time.sleep(3)

            if not page.query_selector("#site"):
                log("Dashboard me 'site' dropdown nahi mila!", "WARN")
            else:
                log("      Dashboard ready hai")

            log(f"[6/6] {len(UNITS)} units ka data download kar raha hu...")

            for idx, (unit_name, unit_value) in enumerate(UNITS, 1):
                log("-" * 50)
                log(f"[{idx}/{len(UNITS)}] UNIT: {unit_name} ({unit_value})")

                try:
                    page.select_option("#site", value=unit_value)
                    time.sleep(1)

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

                    log(f"      Submit...")
                    page.click("#Submit")
                    page.wait_for_load_state("networkidle", timeout=20000)
                    time.sleep(3)

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

            log("=" * 60)
            log(f"DOWNLOAD PURA HUA!", "OK")
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

    # ---------- ZIP + EMAIL ----------
    if success_count > 0:
        log("")
        log("=" * 60)
        log("ZIP BANA RAHA HU AUR EMAIL BHEJ RAHA HU...")
        log("=" * 60)

        # ZIP banao
        zip_path = make_zip(today_folder, from_date, to_date)

        if zip_path and SEND_EMAIL:
            # SMTP se try karo pehle
            log("Email bhej raha hu (SMTP)...")
            email_sent = send_email_smtp(zip_path, from_date, to_date, success_count, failed_units)

            # Agar SMTP fail → Outlook/Mail app fallback
            if not email_sent:
                log("SMTP se nahi gaya, Outlook/Mail app try kar raha hu...", "WARN")
                send_email_outlook(zip_path, from_date, to_date)

            log("")
            log(f"ZIP path: {zip_path}", "OK")

        elif zip_path:
            log(f"ZIP ready: {zip_path}", "OK")

    else:
        log("Koi file download nahi hui, email skip kiya", "WARN")


if __name__ == "__main__":
    try:
        from_date, to_date = ask_user_choice()
        download_units(from_date, to_date)
    except KeyboardInterrupt:
        print("\n\nUser ne cancel kiya.")
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        traceback.print_exc()

    if LOG_FILE:
        try:
            LOG_FILE.close()
        except:
            pass

    # App band hone se pehle 5 second wait karo
    try:
        if sys.stdout.isatty():
            print("\n" + "=" * 60)
            print("  5 sec me window band ho jayegi...")
            print("=" * 60)
            time.sleep(5)
    except:
        pass
