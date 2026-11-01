from flask import Flask, Response, request
import curl_cffi
import urllib3
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

BASE_URL = "https://beyazelma78.com"
EMBED_URL = "https://embed.beyazelma78.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"{EMBED_URL}/",
    "Origin": EMBED_URL
}

@app.route('/')
def home():
    return "BeyazElma Proxy Aktif ve Calisiyor!"

@app.route('/liste.m3u')
def generate_m3u():
    try:
        res = curl_cffi.get(f"{BASE_URL}/kanallar", impersonate="chrome", verify=False, timeout=15)
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
    try:
        # 1. Önce güncel ID'yi siteden bul (isim değişmiş olabilir diye)
        real_slug = kanal_id
        try:
            res = curl_cffi.get(f"{BASE_URL}/kanallar", impersonate="chrome", verify=False, timeout=5)
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.select('a[href^="/kanal/"]'):
                if kanal_id in a['href']:
                    real_slug = a['href'].split('/')[-1]
                    break
        except:
            pass

        # 2. Taze token'ı al
        api_url = f"{EMBED_URL}/api/play/{real_slug}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        
        if api_res.status_code != 200:
            return f"API Hatasi: {api_res.status_code}", 404
            
        data = api_res.json()
        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        
        if not stream_url:
            return "Yayin linki bulunamadi", 404
            
        # 3. M3u8 içeriğini Vercel üzerinden proxy'le (IPTV'nin kesin açması için)
        m3u8_res = curl_cffi.get(stream_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        
        if m3u8_res.status_code != 200:
            return f"Yayin Sunucusu Hatasi: {m3u8_res.status_code}", 403
            
        base_url = stream_url[:stream_url.rfind('/')+1]
        new_lines = []
        
        for line in m3u8_res.text.split('\n'):
            line = line.strip()
            if line == "": continue
            
            if line.startswith("#"):
                line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{request.host_url}stream?url={quote(m.group(1) if m.group(1).startswith("http") else base_url + m.group(1))}"', line)
                new_lines.append(line)
            else:
                if not line.startswith("http"):
                    line = base_url + line
                new_lines.append(f"{request.host_url}stream?url={quote(line)}")
                
        return Response('\n'.join(new_lines), mimetype='application/vnd.apple.mpegurl')
        
    except Exception as e:
        return f"Hata: {str(e)}", 500

@app.route('/stream')
def stream_proxy():
    target_url = request.args.get('url')
    if not target_url: return "URL eksik", 400
    try:
        req = curl_cffi.get(target_url, impersonate="chrome", headers=HEADERS, verify=False, stream=True, timeout=15)
        return Response(req.iter_content(chunk_size=1024*1024), content_type=req.headers.get('content-type', 'video/mp2t'), direct_passthrough=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
