from flask import Flask, request, Response
import requests
from urllib.parse import quote, unquote
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Kendini bir iPad (Safari) olarak tanıtan en güncel başlıklar
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://beyazelma78.com/",
    "Origin": "https://beyazelma78.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Connection": "keep-alive"
}

@app.route('/')
def home():
    return "BeyazElma Proxy Aktif (iPad Modu)!"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    api_url = f"https://embed.beyazelma78.com/api/play/{kanal_id}"
    
    try:
        session = requests.Session()
        # Ana siteye iPad olarak girip çerezleri topluyoruz
        session.get("https://beyazelma78.com/", headers=HEADERS, verify=False, timeout=10)
        
        # Embed sitesine de girip oradan da çerez topluyoruz
        session.get("https://embed.beyazelma78.com/", headers=HEADERS, verify=False, timeout=10)

        # Şimdi API isteğini atıyoruz
        api_res = session.get(api_url, headers=HEADERS, verify=False, timeout=10)
        
        try:
            data = api_res.json()
        except:
            return f"API JSON dondurmedi. Cevap: {api_res.text}", 500

        stream_url = data.get("primary")
        if not stream_url and "fallbacks" in data and isinstance(data["fallbacks"], list) and len(data["fallbacks"]) > 0:
            stream_url = data["fallbacks"][0]
        
        if not stream_url:
            return f"Yayin linki bulunamadi. Sitenin Cevabi: {data}", 404
            
        return proxy_stream(stream_url, session)
    except Exception as e:
        return f"Hata: {str(e)}", 500

@app.route('/stream')
def stream_proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "URL eksik", 400
    return proxy_stream(unquote(target_url), None)

def proxy_stream(target_url, existing_session=None):
    try:
        req_session = existing_session if existing_session else requests.Session()
        req = req_session.get(target_url, headers=HEADERS, stream=True, verify=False, timeout=15)
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
