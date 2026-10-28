from flask import Flask, request, Response
import requests
from urllib.parse import quote, unquote
import re
import urllib3
import time
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

CACHE = {}
CACHE_TIMEOUT = 120 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def find_real_slug(search_id):
    """Sitenin kanal listesine gider ve aranan ID'yi (örn: bein-sports-2) içeren gerçek linki bulur."""
    try:
        # Arama terimini temizle (tr-, -fhd, -hd gibi ekleri at)
        clean_term = search_id.lower()
        for prefix in ["tr-", "de-", "en-"]:
            if clean_term.startswith(prefix):
                clean_term = clean_term.replace(prefix, "")
        for suffix in ["-fhd", "-hd", "-4k", "-live-during-events-only", "-live", "-2"]:
            if clean_term.endswith(suffix):
                clean_term = clean_term.replace(suffix, "")

        # Sitenin kanal listesini çek
        res = requests.get("https://beyazelma78.com/kanallar", headers=HEADERS, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Sayfadaki tüm kanal linklerini tara
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/kanal/' in href and clean_term in href.lower():
                # Aranan kanalı bulduk! Gerçek ID'yi (slug) döndür
                real_slug = href.split('/')[-1]
                return real_slug
        return None
    except Exception as e:
        print(f"Arama hatası: {e}")
        return None

def get_real_stream(real_slug):
    """Bulunan gerçek ID ile API'ye gidip yayın linkini alır."""
    try:
        # Kanal sayfasına git (iframe'i bulmak için)
        page_url = f"https://beyazelma78.com/kanal/{real_slug}"
        res = requests.get(page_url, headers=HEADERS, verify=False, timeout=10)
        
        embed_paths = re.findall(r'/api/embed\?u=[A-Za-z0-9_\-]+', res.text)
        if not embed_paths: return None
        
        embed_full_url = "https://beyazelma78.com" + list(set(embed_paths))[0]
        embed_res = requests.get(embed_full_url, headers=HEADERS, verify=False, timeout=10)
        slug_match = re.search(r'"slug"\s*:\s*"([^"]+)"', embed_res.text)
        if not slug_match: return None
        
        api_slug = slug_match.group(1)
        api_url = f"https://embed.beyazelma78.com/api/play/{api_slug}"
        api_res = requests.get(api_url, headers=HEADERS, verify=False, timeout=10)
        data = api_res.json()
        
        return data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
    except Exception:
        return None

@app.route('/')
def home():
    return "BeyazElma Dinamik Tarayici Aktif!"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    # Önbellekte varsa anında dön
    if kanal_id in CACHE:
        if (time.time() - CACHE[kanal_id][1]) < CACHE_TIMEOUT:
            return proxy_stream(CACHE[kanal_id][0])

    # 1. Siteden gerçek ismi bul
    real_slug = find_real_slug(kanal_id)
    
    if not real_slug:
        # Eğer tam eşleşme bulamazsa (örn: s-sport-plus-2 gibi), belki doğrudan ID'dir diye deneyelim
        real_slug = kanal_id

    # 2. Bulunan gerçek isimle yayın linkini çek
    stream_url = get_real_stream(real_slug)
    
    if stream_url:
        CACHE[kanal_id] = (stream_url, time.time())
        return proxy_stream(stream_url)

    return f"Kanal bulunamadi. Aranan: {kanal_id}, Bulunan ID: {real_slug}", 404

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
