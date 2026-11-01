from flask import Flask, Response, redirect
import curl_cffi
import urllib3
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urlparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Hafıza (Cache) Değişkenleri
CACHED_DOMAIN = "beyazelma78.com" 
LAST_CHECK_TIME = 0

def get_real_domain(force_check=False):
    global CACHED_DOMAIN, LAST_CHECK_TIME
    
    # Eğer zorla kontrol denmediyse ve hafızada domain varsa, direkt onu ver (Hız için)
    if not force_check and CACHED_DOMAIN:
        return CACHED_DOMAIN

    try:
        print("Domain kontrol ediliyor (elmacibaba.com)...")
        res = curl_cffi.get("https://elmacibaba.com", impersonate="chrome", allow_redirects=True, verify=False, timeout=10)
        final_url = res.url
        parsed = urlparse(final_url)
        domain = parsed.netloc

        # Eğer t.ly veya elmacibaba gelirse, varsayılan siteye dön
        if "elmacibaba" in domain or "t.ly" in domain or not domain:
            domain = "beyazelma78.com"
        else:
            parts = domain.split('.')
            if len(parts) >= 2:
                domain = f"{parts[-2]}.{parts[-1]}"

        CACHED_DOMAIN = domain
        print(f"Yeni domain bulundu ve hafızaya alındı: {CACHED_DOMAIN}")
        return CACHED_DOMAIN

    except Exception as e:
        print(f"Domain bulma hatasi: {e}")
        return CACHED_DOMAIN

# --- LİSTE OLUŞTURMA (IPTV'de "Güncelle" dediğinde çalışır) ---
@app.route('/liste.m3u')
def generate_m3u():
    try:
        # LİSTE GÜNCELLENİRKEN domaini zorla kontrol et (elmacibaba'ya git)
        current_domain = get_real_domain(force_check=True)
        url = f"https://{current_domain}/kanallar"
        
        res = curl_cffi.get(url, impersonate="chrome", verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        m3u = "#EXTM3U\n"
        for a in soup.select('a[href^="/kanal/"]'):
            href = a.get('href', '').strip()
            if not href: continue
            
            name_el = a.select_one('.site-channel-row-name')
            name = name_el.get_text(strip=True) if name_el else "Kanal"
            kanal_id = href.split('/')[-1]
            
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f"https://b-proxy-delta.vercel.app/play/{kanal_id}\n"
            
        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

# --- KANAL OYNATMA (Kanala tıkladığında çalışır) ---
@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    try:
        # KANAL AÇILIRKEN domaini zorla kontrol etme, hafızadakini kullan (Hız için)
        current_domain = get_real_domain(force_check=False)
        embed_domain = f"embed.{current_domain}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://{embed_domain}/",
            "Origin": f"https://{embed_domain}"
        }

        page_url = f"https://{current_domain}/kanal/{kanal_id}"
        page_res = curl_cffi.get(page_url, impersonate="chrome", headers=headers, verify=False, timeout=10)
        
        embed_paths = re.findall(r'/api/embed\?u=[A-Za-z0-9_\-]+', page_res.text)
        if not embed_paths:
            return f"Embed linki bulunamadi. Domain: {current_domain}", 404
            
        embed_url = f"https://{current_domain}" + embed_paths[0]
        embed_res = curl_cffi.get(embed_url, impersonate="chrome", headers=headers, verify=False, timeout=10)
        slug_match = re.search(r'"slug"\s*:\s*"([^"]+)"', embed_res.text)
        
        if not slug_match:
            return f"Slug bulunamadi.", 404
            
        api_url = f"https://{embed_domain}/api/play/{slug_match.group(1)}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=headers, verify=False, timeout=10)
        
        if api_res.status_code == 200:
            data = api_res.json()
            stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            if stream_url:
                return redirect(stream_url, code=302)
        
        return f"Yayin linki alinamadi. API Kodu: {api_res.status_code}", 404
    except Exception as e:
        return f"Hata: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
