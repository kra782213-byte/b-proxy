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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def get_real_stream(page_url):
    """Kanal sayfasına gidip gerçek m3u8 linkini bulur."""
    try:
        res = requests.get(page_url, headers=HEADERS, verify=False, timeout=10)
        embed_paths = re.findall(r'/api/embed\?u=[A-Za-z0-9_\-]+', res.text)
        if not embed_paths: return None
        
        embed_full_url = "https://beyazelma78.com" + list(set(embed_paths))[0]
        embed_res = requests.get(embed_full_url, headers=HEADERS, verify=False, timeout=10)
        slug_match = re.search(r'"slug"\s*:\s*"([^"]+)"', embed_res.text)
        if not slug_match: return None
        
        real_slug = slug_match.group(1)
        api_url = f"https://embed.beyazelma78.com/api/play/{real_slug}"
        api_res = requests.get(api_url, headers=HEADERS, verify=False, timeout=10)
        data = api_res.json()
        
        return data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
    except Exception:
        return None

@app.route('/')
def home():
    return "BeyazElma Akilli Sunucu Aktif!"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    if kanal_id in CACHE:
        if (time.time() - CACHE[kanal_id][1]) < CACHE_TIMEOUT:
            return proxy_stream(CACHE[kanal_id][0])

    # Yeni URL yapısı: tr- öneki YOK
    page_url = f"https://beyazelma78.com/kanal/{kanal_id}"
    
    stream_url = get_real_stream(page_url)
    
    # Eğer bulamazsa, bazı kanalların sonunda -fhd, -hd gibi ekler olabilir
    if not stream_url:
        for suffix in ["-fhd", "-hd", "-4k"]:
            stream_url = get_real_stream(f"{page_url}{suffix}")
            if stream_url: break

    if not stream_url:
        return f"Kanal bulunamadi. Denenen URL: {page_url}", 404

    CACHE[kanal_id] = (stream_url, time.time())
    return proxy_stream(stream_url)

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
