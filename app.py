from flask import Flask, Response, request
import curl_cffi
import urllib3
import re
from bs4 import BeautifulSoup
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://embed.beyazelma78.com/",
    "Origin": "https://embed.beyazelma78.com"
}

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
            # IPTV'ye tıklanacak linki veriyoruz
            m3u += f"https://beyazelma-proxy.onrender.com/play/{kanal_id}\n"
            
        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    # 1. Kanalın taze token'ını (m3u8 linkini) al
    api_url = f"https://embed.beyazelma78.com/api/play/{kanal_id}"
    try:
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        if api_res.status_code != 200:
            return f"API Hatasi: {api_res.status_code}", 404
            
        data = api_res.json()
        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        
        if not stream_url:
            return "Yayin linki bulunamadi.", 404
            
        # 2. m3u8 içeriğini indir
        m3u8_res = curl_cffi.get(stream_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        if m3u8_res.status_code != 200:
            return f"Yayin Sunucusu Hatasi: {m3u8_res.status_code}", 404
            
        # 3. m3u8 içindeki parçaları (.ts) IPTV'nin anlayacağı formata çevir
        base_url = stream_url[:stream_url.rfind('/')+1]
        new_lines = []
        
        for line in m3u8_res.text.split('\n'):
            line = line.strip()
            if line == "": continue
            
            if line.startswith("#"):
                # Şifreleme anahtarları varsa onları da proxy'le
                line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{request.host_url}stream?url={quote(m.group(1) if m.group(1).startswith("http") else base_url + m.group(1))}"', line)
                new_lines.append(line)
            else:
                # Video parçalarını kendi proxy'mize yönlendir
                if not line.startswith("http"):
                    line = base_url + line
                new_lines.append(f"{request.host_url}stream?url={quote(line)}")
                
        # 4. IPTV'ye geçerli bir m3u8 listesi dön
        return Response('\n'.join(new_lines), mimetype='application/vnd.apple.mpegurl')
        
    except Exception as e:
        return f"Hata: {str(e)}", 500

@app.route('/stream')
def stream_proxy():
    # Video parçalarını (.ts) doğrudan sunucudan çekip IPTV'ye ver
    target_url = request.args.get('url')
    if not target_url:
        return "URL eksik", 400
        
    target_url = target_url.replace(" ", "")
    try:
        req = curl_cffi.get(target_url, impersonate="chrome", headers=HEADERS, verify=False, stream=True, timeout=15)
        
        content_type = req.headers.get('content-type', 'video/mp2t')
        
        return Response(req.iter_content(chunk_size=1024*1024), content_type=content_type, direct_passthrough=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
