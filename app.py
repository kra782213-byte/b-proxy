from flask import Flask, request, Response
import requests
from urllib.parse import quote, unquote
import re
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

CACHE = {}
CACHE_TIMEOUT = 120 

# Tarayıcı taklidi ve doğru Referer
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://embed.beyazelma78.com/",
    "Origin": "https://embed.beyazelma78.com",
    "Accept": "application/json, text/plain, */*"
}

def try_api(slug):
    """Verilen ID ile API'ye gidip yayın linkini almayı dener."""
    api_url = f"https://embed.beyazelma78.com/api/play/{slug}"
    try:
        res = requests.get(api_url, headers=HEADERS, verify=False, timeout=5)
        if res.status_code == 200:
            data = res.json()
            stream = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            if stream:
                return stream
    except:
        pass
    return None

@app.route('/')
def home():
    return "BeyazElma Akilli API Sunucusu Aktif!"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    if kanal_id in CACHE:
        if (time.time() - CACHE[kanal_id][1]) < CACHE_TIMEOUT:
            return proxy_stream(CACHE[kanal_id][0])

    # Kanal ID'sinin olası tüm varyasyonlarını dene (Site sürekli değiştiriyor)
    slugs_to_try = [
        kanal_id,                                      # tr-bein-sports-2
        f"{kanal_id}-fhd",                             # tr-bein-sports-2-fhd
        f"{kanal_id}-hd",                              # tr-bein-sports-2-hd
        f"{kanal_id}-hd-2",                            # tr-bein-sports-2-hd-2
        f"{kanal_id}-live-during-events-only",         # tr-bein-sports-2-live-during-events-only
        kanal_id.replace("tr-", ""),                   # bein-sports-2 (Belki tr- öneki kalkmıştır)
        f"{kanal_id.replace('tr-', '')}-fhd",          # bein-sports-2-fhd
        f"{kanal_id.replace('tr-', '')}-hd"            # bein-sports-2-hd
    ]

    for slug in slugs_to_try:
        stream_url = try_api(slug)
        if stream_url:
            # Bulunca hafızaya kaydet (hız için)
            CACHE[kanal_id] = (stream_url, time.time())
            return proxy_stream(stream_url)

    return f"Kanal bulunamadi. Denenen ID'ler: {', '.join(slugs_to_try)}", 404

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
