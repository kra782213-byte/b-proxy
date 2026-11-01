from flask import Flask, Response, redirect
import curl_cffi
import urllib3
from bs4 import BeautifulSoup
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://beyazelma78.com/"
}

@app.route('/liste.m3u')
def generate_m3u():
    try:
        res = curl_cffi.get("https://beyazelma78.com/kanallar", impersonate="chrome", verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        m3u = "#EXTM3U\n"
        for a in soup.select('a[href^="/kanal/"]'):
            href = a.get('href', '').strip()
            if not href: continue
            
            name_el = a.select_one('.site-channel-row-name')
            name = name_el.get_text(strip=True) if name_el else "Kanal"
            kanal_id = href.split('/')[-1]
            
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f"https://beyazelma-proxy.onrender.com/play/{kanal_id}\n"
            
        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    try:
        # 1. Kanal sayfasına git
        page_url = f"https://beyazelma78.com/kanal/{kanal_id}"
        page_res = curl_cffi.get(page_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        
        # 2. Sayfa içinden gizli embed linkini bul (örn: /api/embed?u=...)
        embed_paths = re.findall(r'/api/embed\?u=[A-Za-z0-9_\-]+', page_res.text)
        if not embed_paths:
            return f"Embed linki bulunamadi. (Sayfa acildi ama iframe yok)", 404
            
        embed_url = "https://beyazelma78.com" + embed_paths[0]
        
        # 3. Embed sayfasına git ve asıl slug değerini çek
        embed_res = curl_cffi.get(embed_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        slug_match = re.search(r'"slug"\s*:\s*"([^"]+)"', embed_res.text)
        
        if not slug_match:
            return f"Slug bulunamadi (Embed sayfasi acildi ama kod farkli).", 404
            
        real_slug = slug_match.group(1)
        
        # 4. Gerçek slug ile API'ye istek at
        api_url = f"https://embed.beyazelma78.com/api/play/{real_slug}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        
        if api_res.status_code == 200:
            data = api_res.json()
            stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            if stream_url:
                # Başarılı! Yayına yönlendir
                return redirect(stream_url, code=302)
        
        return f"Yayin linki alinamadi. Gercek Slug: {real_slug} | API Kodu: {api_res.status_code}", 404
        
    except Exception as e:
        return f"Hata: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
