from flask import Flask, request, Response
import requests
from urllib.parse import quote, unquote
import re
import urllib3
from urllib.parse import urlparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Yönlendirici (Redirect) Sitesi
REDIRECT_URL = "https://elmacibaba.com/"

def get_real_domain():
    """Yönlendirici siteye gidip, asıl hedef domaini bulur."""
    try:
        # Yönlendirmeleri takip ederek nihai hedefe ulaş
        res = requests.get(REDIRECT_URL, allow_redirects=True, timeout=10, verify=False)
        final_url = res.url
        parsed_uri = urlparse(final_url)
        domain = '{uri.netloc}'.format(uri=parsed_uri)
        
        # Eğer elmacibaba.com'dan başka bir yere yönlendirdiyse o domaini döndür
        if "elmacibaba" not in domain:
            # Sadece kök domaini al (örn: beyazelma78.com)
            parts = domain.split('.')
            if len(parts) >= 2:
                root_domain = f"{parts[-2]}.{parts[-1]}"
                return root_domain
        return domain
    except Exception as e:
        print(f"Domain bulma hatası: {e}")
        return "beyazelma78.com" # Hata olursa eski çalışan domaine dön

@app.route('/')
def home():
    real_domain = get_real_domain()
    return f"Akıllı Proxy Aktif! Şu anki hedef domain: {real_domain}"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    real_domain = get_real_domain()
    embed_domain = f"embed.{real_domain}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://{embed_domain}/",
        "Origin": f"https://{embed_domain}"
    }

    api_url = f"https://{embed_domain}/api/play/{kanal_id}"
    
    try:
        api_res = requests.get(api_url, headers=headers, verify=False, timeout=10)
        data = api_res.json()
        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        
        if not stream_url:
            return f"Yayin linki bulunamadi. Denenen API: {api_url}", 404
            
        return proxy_stream(stream_url, headers)
    except Exception as e:
        return f"Hata: {str(e)} | Denenen API: {api_url}", 500

@app.route('/stream')
def stream_proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "URL eksik", 400
        
    real_domain = get_real_domain()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://embed.{real_domain}/",
        "Origin": f"https://embed.{real_domain}"
    }
    return proxy_stream(unquote(target_url), headers)

def proxy_stream(target_url, headers):
    try:
        req = requests.get(target_url, headers=headers, stream=True, verify=False, timeout=15)
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
