from flask import Flask, Response, redirect, request
import curl_cffi
import urllib3
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Kimlik bilgileri (403 hatasını önlemek için kritik)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://embed.beyazelma78.com/",
    "Origin": "https://embed.beyazelma78.com"
}

@app.route('/')
def home():
    return "BeyazElma Proxy Aktif ve Calisiyor!"

@app.route('/liste.m3u')
def generate_m3u():
    try:
        res = curl_cffi.get("https://beyazelma78.com/kanallar", impersonate="chrome", verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        m3u = "#EXTM3U\n"
        for a in soup.select('a[href^="/kanal/"]'):
            href = a.get('href', '').strip()
            if not href: continue
            
            name_el = a.select_one('.site-channel-row-name')
            name = name_el.get_text(strip=True) if name_el else "Kanal"
            kanal_id = href.split('/')[-1]
            
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f"https://beyazelma-proxy.onrender.com/play/{kanal_id}\n"
            
        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    try:
        # 1. Kanal sayfasına git, gerçek slug'ı bul
        page_url = f"https://beyazelma78.com/kanal/{kanal_id}"
        page_res = curl_cffi.get(page_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        embed_paths = re.findall(r'/api/embed\?u=[A-Za-z0-9_\-]+', page_res.text)
        
        if not embed_paths:
            return "Embed linki bulunamadi.", 404
            
        embed_url = "https://beyazelma78.com" + embed_paths[0]
        embed_res = curl_cffi.get(embed_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        slug_match = re.search(r'"slug"\s*:\s*"([^"]+)"', embed_res.text)
        
        if not slug_match:
            return "Slug bulunamadi.", 404
            
        # 2. Taze token'ı al
        api_url = f"https://embed.beyazelma78.com/api/play/{slug_match.group(1)}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        
        if api_res.status_code == 200:
            data = api_res.json()
            stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            
            if stream_url:
                # 3. IPTV'yi doğrudan yönlendirmek yerine m3u8 içeriğini indir
                m3u8_res = curl_cffi.get(stream_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
                
                if m3u8_res.status_code != 200:
                    return f"Yayin sunucusu reddetti (Kod: {m3u8_res.status_code}).", 403

                # 4. m3u8 içindeki parçaları Render üzerinden proxy'le (Kimlik bilgileriyle)
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
        
        return "Yayin linki alinamadi.", 404
    except Exception as e:
        return f"Hata: {str(e)}", 500

@app.route('/stream')
def stream_proxy():
    # Video parçalarını (.ts) IPTV'ye gönderirken kimlik bilgilerini ekleyerek gönder
    target_url = request.args.get('url')
    if not target_url:
        return "URL eksik", 400
        
    try:
        req = curl_cffi.get(target_url, impersonate="chrome", headers=HEADERS, verify=False, stream=True, timeout=15)
        content_type = req.headers.get('content-type', 'video/mp2t')
        return Response(req.iter_content(chunk_size=1024*1024), content_type=content_type, direct_passthrough=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
