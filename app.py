from flask import Flask, Response
import curl_cffi
import urllib3
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

BASE_URL = "https://beyazelma78.com"
EMBED_URL = "https://embed.beyazelma78.com"
WORKER_URL = "https://beyazelma-proxy.najsjskak80.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"{EMBED_URL}/",
    "Origin": EMBED_URL
}

def find_real_id(clean_id):
    # Sitedeki kanal isimlerini bulup, doğru ID'yi eşleştiren kurtarıcı fonksiyon
    try:
        res = curl_cffi.get(f"{BASE_URL}/kanallar", impersonate="chrome", verify=False, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        links = [a['href'].split('/')[-1] for a in soup.select('a[href^="/kanal/"]')]

        if clean_id in links: return clean_id
        if f"tr-{clean_id}" in links: return f"tr-{clean_id}"

        base_name = clean_id.replace("-fhd", "").replace("-hd", "").replace("-4k", "")
        for link in links:
            if base_name in link:
                return link
        return clean_id
    except:
        return clean_id

@app.route('/')
def home():
    return "Vercel ve Cloudflare Hibrit Sistem Aktif!"

@app.route('/liste.m3u')
def generate_m3u():
    try:
        res = curl_cffi.get(f"{BASE_URL}/kanallar", impersonate="chrome", verify=False, timeout=10)
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

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    clean_id = kanal_id.replace(".m3u8", "")
    real_id = find_real_id(clean_id)
    
    try:
        api_url = f"{EMBED_URL}/api/play/{real_id}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
        
        if api_res.status_code != 200:
            return f"API Hatasi: {api_res.status_code} (Aranan: {clean_id}, Bulunan: {real_id})", 404
            
        data = api_res.json()
        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        
        if not stream_url:
            return "Yayin linki bulunamadi", 404
            
        m3u8_res = curl_cffi.get(stream_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
        
        if m3u8_res.status_code != 200:
            return f"Yayin Sunucusu Hatasi: {m3u8_res.status_code}", 403
            
        base_url = stream_url[:stream_url.rfind('/')+1]
        new_lines = []
        
        for line in m3u8_res.text.split('\n'):
            line = line.strip()
            if line == "": continue
            
            if line.startswith("#"):
                line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{WORKER_URL}/stream?url={quote(m.group(1) if m.group(1).startswith("http") else base_url + m.group(1))}"', line)
                new_lines.append(line)
            else:
                if not line.startswith("http"):
                    line = base_url + line
                new_lines.append(f"{WORKER_URL}/stream?url={quote(line)}")
                
        return Response(
            '\n'.join(new_lines), 
            mimetype='application/vnd.apple.mpegurl',
            headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}
        )
    except Exception as e:
        return f"Hata: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
