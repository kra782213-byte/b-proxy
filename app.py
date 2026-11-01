from flask import Flask, Response
import curl_cffi
import urllib3
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

BASE_URL = "https://beyazelma78.com"
EMBED_URL = "https://embed.beyazelma78.com"
WORKER_URL = "https://beyazelma-proxy.najsjskak80.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"{EMBED_URL}/",
    "Origin": EMBED_URL
}

@app.route('/')
def home():
    return "Vercel ve Cloudflare Hibrit Sistem Aktif!"

@app.route('/liste.m3u')
def generate_m3u():
    try:
        res = curl_cffi.get(f"{BASE_URL}/kanallar", impersonate="chrome", verify=False, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        
        m3u = "#EXTM3U\n"
        for a in soup.select('a[href^="/kanal/"]'):
            href = a.get('href', '').strip()
            if not href: continue
            
            name_el = a.select_one('.site-channel-row-name')
            name = name_el.get_text(strip=True) if name_el else "Kanal"
            kanal_id = href.split('/')[-1]
            
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f"https://b-proxy-delta.vercel.app/play/{kanal_id}\n"
            
        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    clean_id = kanal_id.replace(".m3u8", "")
    
    # Sadece sitenin kullandığı gerçek ID ve onun "tr-" önekli halini dene.
    # FHD veya 4K'yı birbirine karıştırma!
    variations = [
        clean_id, 
        f"tr-{clean_id}"
    ]

    for slug in variations:
        try:
            api_url = f"{EMBED_URL}/api/play/{slug}"
            api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
            
            if api_res.status_code == 200:
                data = api_res.json()
                stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
                
                if stream_url:
                    m3u8_res = curl_cffi.get(stream_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
                    
                    if m3u8_res.status_code == 200:
                        base_url = stream_url[:stream_url.rfind('/')+1]
                        new_lines = []
                        
                        for line in m3u8_res.text.split('\n'):
                            line = line.strip()
                            if line == "": continue
                            
                            if line.startswith("#"):
                                line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{WORKER_URL}/stream?url={quote(m.group(1) if m.group(1).startswith("http") else base_url + m.group(1))}"', line)
                                new_lines.append(line)
                            else:
                                if not line.startswith("http"):
                                    line = base_url + line
                                new_lines.append(f"{WORKER_URL}/stream?url={quote(line)}")
                                
                        return Response('\n'.join(new_lines), mimetype='application/vnd.apple.mpegurl')
        except Exception:
            continue
            
    return f"Kanal su an yayinda degil veya API kapali. (ID: {clean_id})", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
