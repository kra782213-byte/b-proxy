from flask import Flask, Response
import curl_cffi
import urllib3
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://embed.beyazelma78.com/",
    "Origin": "https://embed.beyazelma78.com"
}

# Her kanal için anlık token alan yardımcı fonksiyon
def get_stream_url(kanal_id):
    api_url = f"https://embed.beyazelma78.com/api/play/{kanal_id}"
    try:
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        if api_res.status_code == 200:
            data = api_res.json()
            return data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
    except:
        pass
    return None

@app.route('/liste.m3u')
def generate_m3u():
    try:
        # Siteye git ve kanalları çek
        res = curl_cffi.get("https://beyazelma78.com/kanallar", impersonate="chrome", verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        channels = []
        for a in soup.select('a[href^="/kanal/"]'):
            href = a.get('href', '').strip()
            if not href: continue
            name_el = a.select_one('.site-channel-row-name')
            name = name_el.get_text(strip=True) if name_el else "Kanal"
            kanal_id = href.split('/')[-1]
            channels.append({"name": name, "id": kanal_id})
        
        # Tüm kanalların linklerini aynı anda (paralel) çekerek listeyi hızlı oluştur
        def build_channel_line(ch):
            stream_url = get_stream_url(ch["id"])
            if stream_url:
                # #EXTVLCOPT ile IPTV'ye kimlik bilgilerini gönderiyoruz
                return f'#EXTINF:-1, {ch["name"]}\n#EXTVLCOPT:http-referrer=https://embed.beyazelma78.com/\n#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n{stream_url}\n'
            return ""
        
        # 10 kanalı aynı anda çekecek şekilde ayarladık (Hız için)
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(build_channel_line, channels))
        
        m3u = "#EXTM3U\n" + "".join(results)
        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
