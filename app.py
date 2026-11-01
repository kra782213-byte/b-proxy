from flask import Flask, Response, redirect
import curl_cffi
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# 1. AŞAMA: SADECE LİSTEYİ OLUŞTURAN KISIM
@app.route('/liste.m3u')
def generate_m3u():
    try:
        # Siteye gerçek bir tarayıcı gibi gir
        res = curl_cffi.get("https://beyazelma78.com/kanallar", 
            impersonate="chrome", 
            verify=False, 
            timeout=10)
        
        # Kanalları ve isimlerini ayıkla
        regex = re.compile(r'href="/kanal/([^"]+)"[\s\S]*?class="site-channel-row-name">([^<]+)<')
        matches = regex.findall(res.text)
        
        m3u = "#EXTM3U\n"
        for kanal_id, name in matches:
            name = name.strip().replace('&amp;', '&')
            
            # DİKKAT: Buraya doğrudan token yazmıyoruz!
            # Sadece senin Render sunucunun 'play' adresini yazıyoruz.
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f'#EXTVLCOPT:http-referrer=https://embed.beyazelma78.com/\n'
            # Gelen isteği yönlendireceğimiz için Render linkini veriyoruz
            m3u += f"https://beyazelma-proxy.onrender.com/play/{kanal_id}\n"

        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

# 2. AŞAMA: KANALA TIKLANDIĞINDA TAZE TOKEN ALAN KISIM
@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    # Sitedeki olası isim değişikliklerini dene (tr-, -fhd vb.)
    variations = [kanal_id, f"tr-{kanal_id}", f"tr-{kanal_id}-fhd", f"tr-{kanal_id}-hd"]
    
    for slug in variations:
        api_url = f"https://embed.beyazelma78.com/api/play/{slug}"
        try:
            # O ANKİ taze token'ı al
            api_res = curl_cffi.get(api_url, 
                impersonate="chrome", 
                headers={"Referer": "https://embed.beyazelma78.com/"}, 
                verify=False, 
                timeout=5)
            
            if api_res.status_code == 200:
                data = api_res.json()
                stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
                
                if stream_url:
                    # Token'ı bulduk! IPTV'yi doğrudan bu taze linke yönlendir
                    return redirect(stream_url, code=302)
        except Exception:
            continue

    return "Kanal bulunamadi veya yayinda degil.", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
