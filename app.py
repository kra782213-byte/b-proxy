from flask import Flask, Response, redirect
import curl_cffi
import urllib3
from bs4 import BeautifulSoup

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
            # IPTV'ye yönlendirme sırasında Referer göndermesini söylüyoruz (Render'dan video geçmez)
            m3u += f'#EXTVLCOPT:http-referrer=https://embed.beyazelma78.com/\n'
            m3u += f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n'
            m3u += f"https://beyazelma-proxy.onrender.com/play/{kanal_id}\n"
            
        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    # Sadece taze token'ı alıp IPTV'yi o linke yönlendiriyoruz (Video Render'dan geçmez)
    api_url = f"https://embed.beyazelma78.com/api/play/{kanal_id}"
    try:
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        if api_res.status_code == 200:
            data = api_res.json()
            stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            if stream_url:
                # 302 Yönlendirme: IPTV'ye "Bunu değil, şu linki aç" der.
                return redirect(stream_url, code=302)
        
        return f"Yayin linki alinamadi. Site Kodu: {api_res.status_code}", 404
    except Exception as e:
        return f"Hata: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
