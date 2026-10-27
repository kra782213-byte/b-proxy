from flask import Flask, request, Response
import requests
from urllib.parse import quote, unquote, urlparse
import re
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

REDIRECT_URL = "https://elmacibaba.com"
# Hız için önbellek (Hafıza)
CACHE = {} 
CACHE_TIMEOUT = 300 # 5 Dakika

def get_real_domain():
    try:
        # Yönlendirmeleri takip et
        res = requests.get(REDIRECT_URL, allow_redirects=True, timeout=5, verify=False)
        final_url = res.url
        parsed_uri = urlparse(final_url)
        domain = parsed_uri.netloc
        
        # t.ly veya elmacibaba gelirse eski çalışan siteye dön
        if "elmacibaba" in domain or "t.ly" in domain or not domain:
            return "beyazelma78.com"
        
        parts = domain.split('.')
        if len(parts) >= 2:
            return f"{parts[-2]}.{parts[-1]}"
        return domain
    except Exception:
        return "beyazelma78.com"

@app.route('/')
def home():
    return "Akıllı ve Hızlı Proxy Aktif!"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    global CACHE
    
    # 1. Önce önbelleğe (hafızaya) bak
    if kanal_id in CACHE:
        cached_url, timestamp = CACHE[kanal_id]
        if time.time() - timestamp < CACHE_TIMEOUT:
            print(f"[CACHE HIT] {kanal_id}")
            return proxy_stream(cached_url)
            
    print(f"[CACHE MISS] {kanal_id} - API'ye gidiliyor")
    real_domain = get_real_domain()
    embed_domain = f"embed.{real_domain}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://{embed_domain}/",
        "Origin": f"https://{embed_domain}"
    }

    api_url = f"https://{embed_domain}/api/play/{kanal_id}"
    
    try:
        session = requests.Session()
        session.get(f"https://{real_domain}/", headers=headers, verify=False, timeout=5)
        
        api_res = session.get(api_url, headers=headers, verify=False, timeout=8)
        data = api_res.json()
        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        
        if not stream_url:
            return f"Yayin linki bulunamadi.", 404
            
        # Başarılıysa önbelleğe kaydet
        CACHE[kanal_id] = (stream_url, time.time())
        
        return proxy_stream(stream_url)
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
        # Yayın sunucusuna giderken en temel başlıklar
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://beyazelma78.com/"
        }
        req = requests.get(target_url, headers=headers, stream=True, verify=False, timeout=10)
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
