import json
import time
import requests
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

# ==========================================
# KONFIGURASI
# ==========================================
SERVICE_ACCOUNT_FILE = 'service_account.json' # Ganti dengan path file JSON Anda
SITEMAP_URL = 'https://railfansday.github.io/spesial4/sitemap.xml'
SCOPES = ['https://www.googleapis.com/auth/indexing']
ENDPOINT = 'https://indexing.googleapis.com/v3/urlNotifications:publish'

def get_urls_from_sitemap(sitemap_url):
    """Mengambil daftar URL dari file sitemap.xml"""
    print(f"[*] Mengambil URL dari sitemap: {sitemap_url}")
    try:
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]
        print(f"[*] Ditemukan {len(urls)} URL.")
        return urls
    except Exception as e:
        print(f"[!] Gagal mengambil sitemap: {e}")
        return []

def send_indexing_request(session, url):
    """Mengirim satu URL ke Google Indexing API"""
    body = {
        "url": url,
        "type": "URL_UPDATED"
    }
    try:
        response = session.post(ENDPOINT, json=body)
        if response.status_code == 200:
            print(f"  [OK] Terkirim: {url}")
            return True
        elif response.status_code == 429:
            print(f"  [LIMIT] Kuota habis untuk hari ini. Berhenti.")
            return False
        else:
            print(f"  [ERR] {url} -> Status: {response.status_code} - {response.text}")
            return True # Tetap lanjut ke URL berikutnya
    except Exception as e:
        print(f"  [ERR] {url} -> Exception: {e}")
        return True

def main():
    print("="*50)
    print("MEMULAI PENGIRIMAN URL KE GOOGLE INDEXING API")
    print("="*50)
    
    # 1. Autentikasi
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        session = AuthorizedSession(credentials)
        print("[*] Autentikasi berhasil.")
    except Exception as e:
        print(f"[!] Gagal autentikasi. Pastikan file {SERVICE_ACCOUNT_FILE} valid: {e}")
        return

    # 2. Ambil URL dari Sitemap
    urls = get_urls_from_sitemap(SITEMAP_URL)
    if not urls:
        print("[!] Tidak ada URL untuk diproses.")
        return

    # 3. Kirim URL satu per satu
    print(f"\n[*] Memulai pengiriman (Maksimal 200 URL/hari)...")
    count = 0
    for url in urls:
        # Batasi maksimal 190 agar aman dari limit harian
        if count >= 190:
            print("\n[!] Mencapai batas aman pengiriman (190 URL). Berhenti.")
            break
            
        if send_indexing_request(session, url):
            count += 1
            # Jeda sedikit agar tidak dianggap spam
            time.sleep(1) 
        else:
            # Jika kuota habis (429), hentikan loop
            break

    print("\n" + "="*50)
    print(f"[SELESAI] Berhasil mengirim {count} URL.")
    print("="*50)

if __name__ == "__main__":
    main()
