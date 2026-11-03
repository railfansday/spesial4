import os
from pathlib import Path

# ⚠️ GANTI DENGAN URL YANG BENAR
BASE_URL = "https://railfansday.github.io/spesial4" 

def generate_sitemap():
    print("[*] Memindai file HTML...")
    output_dir = Path(".")
    # Cari semua file HTML, urutkan berdasarkan nama
    html_files = sorted(output_dir.glob("*.html"))
    
    if not html_files:
        print("[!] Tidak ada file HTML ditemukan.")
        return

    print(f"[*] Ditemukan {len(html_files)} file HTML. Membuat sitemap...")
    
    sitemap_path = output_dir / "sitemap.xml"
    
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        
        for file in html_files:
            # Abaikan jika ada file html aneh (misal 404.html)
            if file.name in ["404.html"]:
                continue
                
            # Jika file index.html, jadikan URL utama
            if file.name == "index.html":
                url = f"{BASE_URL}/"
            else:
                url = f"{BASE_URL}/{file.name}"
                
            f.write(f'  <url><loc>{url}</loc></url>\n')
            
        f.write('</urlset>')
        
    print(f"[SELESAI] sitemap.xml berhasil dibuat dengan {len(html_files)} URL.")

if __name__ == "__main__":
    generate_sitemap()
