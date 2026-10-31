from flask import Flask, Response
import requests
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route('/liste.m3u')
def generate_m3u():
    try:
        # Sitenin kanallar sayfasına git
        res = requests.get("https://beyazelma78.com/kanallar", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9"
        }, verify=False, timeout=10)
        
        # Kanalları ve linkleri regex ile çek
        regex = re.compile(r'href="/kanal/([^"]+)"[\s\S]*?class="site-channel-row-name">([^<]+)<')
        matches = regex.findall(res.text)
        
        m3u = "#EXTM3U\n"
        for kanal_id, name in matches:
            name = name.strip()
            # Video linkini DOĞRUDAN veriyoruz. Render video sunmuyor!
            # Referer ve User-Agent ayarlarını da listeye ekliyoruz
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f'#EXTVLCOPT:http-referrer=https://embed.beyazelma78.com/\n'
            m3u += f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n'
            
            # API'den o anki yayın linkini çek (Sadece API'ye istek atıyor, video indirmiyor)
            api_url = f"https://embed.beyazelma78.com/api/play/{kanal_id}"
            api_res = requests.get(api_url, headers={"Referer": "https://embed.beyazelma78.com/"}, verify=False, timeout=5)
            if api_res.status_code == 200:
                data = api_res.json()
                stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
                if stream_url:
                    # Linki doğrudan listeye yazıyoruz, Render üzerinden geçirmiyoruz
                    m3u += f"{stream_url}\n"
                    continue
            
            # Eğer link bulunamazsa API'nin kendi linkini ver (en azından dener)
            m3u += f"https://embed.beyazelma78.com/api/play/{kanal_id}\n"

        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
