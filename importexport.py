import sqlite3
import feedparser
import requests
from bs4 import BeautifulSoup
import os
import math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ==========================================================================
# KONFIGURASI PATH
# ==========================================================================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = str(BASE_DIR / "database_hasil5" / "database.sqlite")
RSS_FILE = str(BASE_DIR / "rss_list.txt")
OUTPUT_DIR = str(BASE_DIR)
BASE_URL = "https://railfansday.github.io/newera2" # ⚠️ SESUAIKAN NAMA REPO

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

ADSTERRA_CODE = """
<div style="text-align:center; margin:20px 0;">
    <script type="text/javascript">
        atOptions = {'key' : 'f9e40eb3b3cd05f1038aac7b36b33ad2','format' : 'iframe','height' : 90,'width' : 728,'params' : {}};
    </script>
    <script type="text/javascript" src="https://upholdbrilliancerecast.com/f9e40eb3b3cd05f1038aac7b36b33ad2/invoke.js"></script>
</div>
"""

# ==========================================================================
# BAGIAN 1: FUNGSI IMPORT (SCRAPING)
# ==========================================================================
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artikel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE, judul TEXT, konten TEXT, gambar TEXT,
            tanggal_publish TEXT, tanggal_update TEXT
        )
    """)
    conn.commit()
    conn.close()

def extract_full_content(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code != 200: return None, None, None
        soup = BeautifulSoup(response.text, 'html.parser')
        
        image_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image: image_url = og_image.get('content')

        paragraphs = soup.find_all('p')
        full_text = []
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 40 and not any(x in text.lower() for x in ['cookie', 'privacy', 'subscribe', 'rights reserved']):
                full_text.append(f"<p>{text}</p>")
        
        return "\n".join(full_text), image_url, None
    except Exception:
        return None, None, None

def process_single_feed(feed_url):
    feed_url = feed_url.strip()
    if not feed_url or feed_url.startswith("#"): return 0, 0

    baru = 0
    duplikat = 0

    try:
        # Gunakan requests dulu agar tidak macet (timeout 8 detik)
        response = requests.get(feed_url, headers=HEADERS, timeout=8)
        if response.status_code != 200: return 0, 0
        
        feed = feedparser.parse(response.content)
        conn = sqlite3.connect(DB_PATH, timeout=15)
        cursor = conn.cursor()

        for entry in feed.entries:
            link = entry.get('link', '')
            judul = entry.get('title', 'Tanpa Judul')
            if not link: continue

            cursor.execute("SELECT id FROM artikel WHERE link = ?", (link,))
            if cursor.fetchone():
                duplikat += 1
                continue

            full_text_html, image_url, _ = extract_full_content(link)
            if not full_text_html:
                full_text_html = f"<p>{entry.get('summary', 'Konten tidak tersedia.')}</p>"

            tanggal = datetime.now().isoformat()
            img_tag = f'<div style="text-align:center; margin-bottom:20px;"><img src="{image_url}" alt="{judul}" style="max-width:100%; height:auto; border-radius:8px;" loading="lazy"></div>' if image_url else ""

            konten_lengkap = f"""
            {img_tag}
            {ADSTERRA_CODE}
            <div class="article-body" style="font-size: 16px; line-height: 1.8; color: #333;">
                {full_text_html}
                <p style="margin-top: 25px;">
                    <a href="{link}" target="_blank" rel="nofollow noopener" style="color: #0d6efd; text-decoration: none; font-weight: bold;">
                        &rarr; Baca artikel asli
                    </a>
                </p>
            </div>
            {ADSTERRA_CODE}
            """

            try:
                cursor.execute("INSERT INTO artikel (link, judul, konten, gambar, tanggal_publish, tanggal_update) VALUES (?, ?, ?, ?, ?, ?)",
                               (link, judul, konten_lengkap, image_url, tanggal, tanggal))
                conn.commit()
                baru += 1
            except sqlite3.IntegrityError:
                duplikat += 1
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    return baru, duplikat

def jalankan_scraping():
    if not os.path.exists(RSS_FILE):
        print(f"[ERROR] File {RSS_FILE} tidak ditemukan!")
        return
    init_db()
    with open(RSS_FILE, "r", encoding="utf-8") as f:
        rss_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    print(f"[*] Memulai scraping dari {len(rss_urls)} RSS...")
    total_baru, total_duplikat = 0, 0
    
    # Batasi worker agar tidak diblokir server RSS
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_single_feed, url): url for url in rss_urls}
        for future in as_completed(futures):
            b, d = future.result()
            total_baru += b
            total_duplikat += d

    print(f"[SELESAI SCRAPING] Baru: {total_baru} | Duplikat: {total_duplikat}\n")

# ==========================================================================
# BAGIAN 2: FUNGSI EXPORT (GENERATE HTML)
# ==========================================================================
def generate_pagination_nav(current_page, total_pages):
    nav = '<div class="pagination" style="text-align:center; margin: 30px 0; display:flex; flex-wrap:wrap; justify-content:center; gap:8px;">'
    if current_page > 1:
        prev_url = "index.html" if current_page == 2 else f"index_{current_page-1}.html"
        nav += f'<a href="{prev_url}" style="padding:8px 16px; background:#fff; border-radius:5px; text-decoration:none; color:#333;">&laquo; Prev</a>'

    for i in range(1, total_pages + 1):
        url = "index.html" if i == 1 else f"index_{i}.html"
        bg_color = "#27ae60" if i == current_page else "#fff"
        text_color = "#fff" if i == current_page else "#333"
        # Batasi tampilan angka halaman agar tidak terlalu panjang
        if i <= 3 or i > total_pages - 3 or abs(i - current_page) <= 2:
            nav += f'<a href="{url}" style="padding:8px 16px; background:{bg_color}; color:{text_color}; border-radius:5px; text-decoration:none;">{i}</a>'
        elif abs(i - current_page) == 3:
            nav += '<span style="padding:8px;">...</span>'

    if current_page < total_pages:
        next_url = f"index_{current_page+1}.html"
        nav += f'<a href="{next_url}" style="padding:8px 16px; background:#fff; border-radius:5px; text-decoration:none; color:#333;">Next &raquo;</a>'

    nav += '</div>'
    return nav

def jalankan_export_pagination():
    ARTICLES_PER_PAGE = 200
    if not os.path.exists(DB_PATH):
        print(f"Error: Database tidak ditemukan di {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, judul, konten FROM artikel ORDER BY id DESC")
    all_rows = cursor.fetchall()
    conn.close()

    if not all_rows:
        print("Tidak ada artikel di dalam database.")
        return

    total_articles = len(all_rows)
    total_pages = math.ceil(total_articles / ARTICLES_PER_PAGE)
    
    print(f"[*] Total Artikel: {total_articles} | Memecah jadi {total_pages} Halaman HTML...")

    for page in range(1, total_pages + 1):
        start_idx = (page - 1) * ARTICLES_PER_PAGE
        end_idx = start_idx + ARTICLES_PER_PAGE
        chunk = all_rows[start_idx:end_idx]

        filename = "index.html" if page == 1 else f"index_{page}.html"
        output_file = os.path.join(OUTPUT_DIR, filename)
        
        sample_titles = ", ".join([row[1] for row in chunk[:5]])[:150]

        html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kumpulan Berita Terkini - Halaman {page} ({total_articles} Artikel)</title>
    <link rel="canonical" href="{BASE_URL}/{filename}">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .article-card {{ background: #fff; padding: 25px; margin-bottom: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); }}
        .article-card h2 {{ color: #1a0dab; margin-top: 0; }}
        .pagination a {{ padding: 8px 16px; background: #fff; border-radius: 5px; text-decoration: none; color: #333; margin: 0 4px; }}
        .pagination .active {{ background: #27ae60; color: #fff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Katalog Berita (Halaman {page}/{total_pages})</h1>
        <div id="pdf-content">
"""
        for item in chunk:
            artikel_id, judul, konten = item
            html_content += f"""
                <article class="article-card" id="artikel-{artikel_id}">
                    <h2>#{artikel_id}. {judul}</h2>
                    <div class="article-body">{konten}</div>
                </article>
            """

        html_content += f"""
        </div>
        {generate_pagination_nav(page, total_pages)}
    </div>
</body>
</html>"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    # Buat sitemap.xml
    with open(os.path.join(OUTPUT_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{BASE_URL}/</loc></url></urlset>')
    
    # Buat robots.txt
    with open(os.path.join(OUTPUT_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml")

    print(f"[SELESAI] Berhasil membuat {total_pages} file HTML, sitemap.xml, dan robots.txt.")

# ==========================================================================
# BAGIAN 3: JALANKAN SEMUANYA
# ==========================================================================
if __name__ == "__main__":
    print("="*50)
    print("MULAI PROSES IMPORT & EXPORT")
    print("="*50)
    
    # 1. Jalankan Scraping
    jalankan_scraping()
    
    # 2. Jalankan Export
    print("\n" + "="*50)
    print("MULAI EXPORT HTML")
    print("="*50)
    jalankan_export_pagination()
    
    print("\n[PROSES SELESAI]")
