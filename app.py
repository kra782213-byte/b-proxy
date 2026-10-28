from flask import Flask, request, Response
import requests
from urllib.parse import quote, unquote
import re
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://beyazelma78.com/",
    "Origin": "https://beyazelma78.com"
}

CACHE = {}
CACHE_TIMEOUT = 60 # 1 dakika önbellek (hız için)

@app.route('/')
def home():
    return "BeyazElma Akilli Proxy Aktif!"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    # Önbellekte varsa direkt ver
    if kanal_id in CACHE:
        if (time.time() - CACHE[kanal_id][1]) < CACHE_TIMEOUT:
            return proxy_stream(CACHE[kanal_id][0])

    # 1. Önce istenen ID ile direkt siteye sor
    api_url = f"https://embed.beyazelma78.com/api/play/{kanal_id}"
    try:
        api_res = requests.get(api_url, headers=HEADERS, verify=False, timeout=5)
        data = api_res.json()
        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        if stream_url:
            CACHE[kanal_id] = (stream_url, time.time())
            return proxy_stream(stream_url)
    except:
        pass

    # 2. Eğer direkt bulamadıysa (isim değişmişse), siteye gidip kanalı isminden arayalım
    try:
        # Örneğin "tr-bein-sports-2" arıyoruz
        base_name = kanal_id.split('-hd')[0].split('-fhd')[0].split('-live')[0]
        
        res = requests.get("https://beyazelma78.com/kanallar", headers=HEADERS, verify=False, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Sayfadaki tüm kanal linklerini tara
        for a in soup.find_all('a', href=True):
            href = a['href']
            if base_name in href:
                # Bugünkü gerçek ID'yi bulduk (örn: tr-bein-sports-2-live-during-events-only)
                real_slug = href.split('/')[-1]
                api_url = f"https://embed.beyazelma78.com/api/play/{real_slug}"
                api_res = requests.get(api_url, headers=HEADERS, verify=False, timeout=5)
                data = api_res.json()
                stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
                
                if stream_url:
                    CACHE[kanal_id] = (stream_url, time.time())
                    return proxy_stream(stream_url)
                    
        return "Kanal bulunamadi (İsim degismis veya yayin yok).", 404
    except Exception as e:
        return f"Hata: {str(e)}", 500

@app.route('/stream')
def stream_proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "URL eksik", 400
    return proxy_stream(unquote(target_url))

def proxy_stream(target_url):
    try:
        req = requests.get(target_url, headers=HEADERS, stream=True, verify=False, timeout=10)
        content_type = req.headers.get('content-type', '')
        if 'mpegurl' in content_type or '.m3u8' in target_url:
            text = req.text
            base_url = target_url[:target_url.rfind('/')+1]
            new_lines = []
            for line in text.split('\n'):
                line = line.strip()
                if line == "": continue
                if line.startswith("#"):
                    line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{request.host_url}stream?url={quote(m.group(1) if m.group(1).startswith("http") else base_url + m.group(1))}"', line)
                    new_lines.append(line)
                else:
                    if not line.startswith("http"):
                        line = base_url + line
                    new_lines.append(f"{request.host_url}stream?url={quote(line)}")
            return Response('\n'.join(new_lines), content_type='application/vnd.apple.mpegurl')
        return Response(req.iter_content(chunk_size=1024*1024), content_type=content_type, direct_passthrough=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
