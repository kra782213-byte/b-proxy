from flask import Flask, request, Response
import requests
from urllib.parse import quote, unquote
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# YENİ DOMAIN VE HEADERS AYARLARI
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://embed.elmacibaba.com/",
    "Origin": "https://embed.elmacibaba.com"
}

@app.route('/')
def home():
    return "BeyazElma (Elmacibaba) Dinamik Proxy Aktif ve Calisiyor!"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    # API isteği yeni domain üzerinden yapılıyor
    api_url = f"https://embed.elmacibaba.com/api/play/{kanal_id}"
    try:
        api_res = requests.get(api_url, headers=HEADERS, verify=False, timeout=10)
        data = api_res.json()
        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        
        if not stream_url:
            return "Yayin linki bulunamadi", 404
            
        return proxy_stream(stream_url)
    except Exception as e:
        return str(e), 500

@app.route('/stream')
def stream_proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "URL eksik", 400
    return proxy_stream(unquote(target_url))

def proxy_stream(target_url):
    try:
        req = requests.get(target_url, headers=HEADERS, stream=True, verify=False, timeout=15)
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
