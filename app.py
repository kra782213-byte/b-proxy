from flask import Flask, Response
import curl_cffi
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://beyazelma78.com/"
}

@app.route('/liste.m3u')
def generate_m3u():
    try:
        # Siteye erişmeyi dene
        res = curl_cffi.get("https://beyazelma78.com/kanallar", impersonate="chrome", verify=False, timeout=15)
        
        # Eğer site 200 (Başarılı) dönmezse, hatayı ekrana yaz
        if res.status_code != 200:
            return f"HATA: Siteye erisilemedi. Site Durum Kodu: {res.status_code}"

        soup = BeautifulSoup(res.text, "html.parser")
        
        m3u = "#EXTM3U\n"
        kanal_sayisi = 0
        
        for a in soup.select('a[href^="/kanal/"]'):
            href = a.get('href', '').strip()
            if not href: continue
            
            name_el = a.select_one('.site-channel-row-name')
            name = name_el.get_text(strip=True) if name_el else "Kanal"
            kanal_id = href.split('/')[-1]
            
            # Sadece senin anlayacağın, Render kotasını harcamayan yönlendirme linki
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f"https://beyazelma-proxy.onrender.com/play/{kanal_id}\n"
            kanal_sayisi += 1
            
        if kanal_sayisi == 0:
            return "HATA: Siteye girildi ama sayfa icinde hicbir kanal bulunamadi (HTML yapisi degismis olabilir)."
            
        return Response(m3u, mimetype='application/x-mpegurl')
        
    except Exception as e:
        return f"HATA: Kod calisirken bir sorun olustu: {str(e)}"

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    try:
        api_url = f"https://embed.beyazelma78.com/api/play/{kanal_id}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=10)
        
        if api_res.status_code == 200:
            data = api_res.json()
            stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            if stream_url:
                # Doğrudan yayına yönlendir
                from flask import redirect
                return redirect(stream_url, code=302)
        
        return f"Yayin alinamadi. API Kodu: {api_res.status_code} | Cevap: {api_res.text[:50]}"
    except Exception as e:
        return f"Yonlendirme Hatasi: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
