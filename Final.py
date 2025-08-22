import requests
import base64
import re
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ===== Login Info =====

'''
If u forget them just reset via
https://www.etisalat.eg/ecare/faces/oracle/webcenter/portalapp/pages/Account/ForgetPassword.jspx?locale=ar
Enter your phone number 011xxxxx
and u will receive Message contain username:pass info
'''

username_dial = 'Username_or_ur_email_Mrfa0gh'
password = 'ur_Pass_Ghawlash'
phone_number = '114xxxxxxx'

credentials = f"{username_dial}:{password}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

# =====Main Headers =====
headers_base = {
    "applicationVersion": "2",
    "applicationName": "MAB",
    "Accept": "text/xml",
    "Authorization": f"Basic {encoded_credentials}",
    "Language": "ar",
    "APP-BuildNumber": "10655",
    "APP-Version": "33.3.0",
    "OS-Type": "Android",
    "OS-Version": "15",
    "APP-STORE": "GOOGLE",
    "C-Type": "WIFI",
    "Is-Corporate": "false",
    "Content-Type": "text/xml; charset=UTF-8",
    "User-Agent": "okhttp/5.0.0-alpha.11",
    "ADRUM_1": "isMobile:true",
    "ADRUM": "isAjax:true",
}

# ===== body =====
body_login = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<loginRequest>
  <deviceId>f80aa062b99f6205</deviceId>
  <firstLoginAttempt>true</firstLoginAttempt>
  <modelType>SM-A226B</modelType>
  <osVersion>12</osVersion>
  <platform>Android</platform>
  <udid>f80aa062b99f6205</udid>
</loginRequest>"""

# ===== urls =====
url_login = "https://mab.etisalat.com.eg:11003/Saytar/rest/authentication/loginWithPlan"
url_usage = f"https://mab.etisalat.com.eg:11003/Saytar/rest/General/getMyUsage?req=%3CdialAndLanguageRequest%3E%3CsubscriberNumber%3E{phone_number}%3C%2FsubscriberNumber%3E%3Clanguage%3E1%3C%2Flanguage%3E%3CcategoryName%3ETELECOME_FAN_ZONE_BUNDLES%2CFAN_ZONE_ALBUM_MEMBERS%3C%2FcategoryName%3E%3C%2FdialAndLanguageRequest%3E"

body_unsub = f"""<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<submitOrderRequest><mabOperation></mabOperation><msisdn>{phone_number}</msisdn><operation>UNSUBSCRIBE_FANZONE</operation><productName>MAIN_FAN_ZONE</productName></submitOrderRequest>"""

body_activate = f"""<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<submitOrderRequest><mabOperation></mabOperation><msisdn>{phone_number}</msisdn><operation>ACTIVATE</operation><productName>ALBUMS_FAN_ZONE</productName></submitOrderRequest>"""

session = requests.Session()
auth_token = None

def login():
    global auth_token
    while True:
        try:
            resp = session.post(url_login, headers=headers_base, data=body_login.encode("utf-8"), timeout=10)
            auth_token = resp.headers.get("auth")

            if resp.status_code == 200 and "<status>true</status>" in resp.text:
                logging.info("Login successful!")
                if auth_token:
                    logging.info(f"Auth token extracted: {auth_token[:15]}...")
                else:
                    logging.warning("No auth token found, fallback to Basic Auth.")
                return True
            else:
                logging.error("Login failed. Response:")
                logging.error(resp.text)
        except Exception as e:
            logging.error(f"Login exception: {e}")

        logging.warning("Retrying login in 5s...")
        time.sleep(5)

def get_headers_with_token():
    h = headers_base.copy()
    if auth_token:
        h["auth"] = auth_token
    return h

def get_remaining_quota(retries=2, delay=1.75):
    for attempt in range(retries + 1):
        try:
            resp = session.get(url_usage, headers=get_headers_with_token(), timeout=10)
            if resp.status_code != 200:
                logging.warning(f"Usage check failed with HTTP {resp.status_code}")
            else:
                m = re.search(r"<remainingQuota>(.*?)</remainingQuota>", resp.text)
                if m:
                    return float(m.group(1))
                else:
                    logging.warning("No <remainingQuota> found. Response snippet:")
                    logging.warning(resp.text[:300] + "...")
        except Exception as e:
            #logging.error(f"Usage check exception (attempt {attempt+1}/{retries+1}): {e}")
            pass
        if attempt < retries:
            #logging.info(f"Retrying quota fetch in {delay}s...")
            time.sleep(delay)

    return None

def send_order(body, label):
    try:
        resp = session.post(
            "https://mab.etisalat.com.eg:11003/Saytar/rest/servicemanagement/submitOrderV2",
            headers=get_headers_with_token(),
            data=body.encode("utf-8"),
            timeout=15
        )
        if resp.status_code == 200:
            logging.info(f"{label} order sent successfully.")
        else:
            logging.warning(f"{label} order failed: HTTP {resp.status_code}")
            logging.debug(resp.text)
    except Exception as e:
        logging.error(f"{label} order exception: {e}")

if __name__ == "__main__":
    while True:
        try:
            login()
            logging.info("Starting main loop...")

            last_quota = None
            same_quota_count = 0

            while True:
                quota = get_remaining_quota()
                if quota is None:
                    logging.info("Quota fetch failed. Re-login...")
                    session = requests.Session()
                    login()
                    time.sleep(1)
                    continue

                logging.info(f"Current quota: {quota} MB")

                if last_quota is not None and abs(quota - last_quota) < 0.01:
                    same_quota_count += 1
                else:
                    same_quota_count = 0

                if same_quota_count >= 3:
                    logging.info("Quota seems stuck. Force subscription.")
                    send_order(body_activate, "FORCE_ACTIVATE")
                    time.sleep(2)
                    same_quota_count = 0
                    quota = get_remaining_quota()
                    logging.info(f"Quota after forced activation: {quota} MB")

                if quota <= 30:
                    logging.info("Quota low. UNSUBSCRIBE -> wait 10s -> ACTIVATE")
                    send_order(body_unsub, "UNSUBSCRIBE")
                    time.sleep(15)
                    send_order(body_activate, "ACTIVATE")
                    time.sleep(15)

                last_quota = quota
                time.sleep(5)

        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}")
            logging.info("Restarting loop after 5s...")
            time.sleep(5)

