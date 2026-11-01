from flask import Flask, Response, redirect
import curl_cffi
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route('/liste.m3u')
def generate_m3u():
    try:
        res = curl_cffi.get("https://beyazelma78.com/kanallar", 
            impersonate="chrome", 
            verify=False, 
            timeout=10)
        
        regex = re.compile(r'href="/kanal/([^"]+)"[\s\S]*?class="site-channel-row-name">([^<]+)<')
        matches = regex.findall(res.text)
        
        m3u = "#EXTM3U\n"
        for kanal_id, name in matches:
            name = name.strip().replace('&amp;', '&')
            m3u += f'#EXTINF:-1, {name}\n'
            m3u += f"https://beyazelma-proxy.onrender.com/play/{kanal_id}\n"

        return Response(m3u, mimetype='application/x-mpegurl')
    except Exception as e:
        return str(e), 500

@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    # Denenecek isim varyasyonları
    variations = [kanal_id, f"tr-{kanal_id}", f"tr-{kanal_id}-fhd", f"tr-{kanal_id}-hd", f"tr-{kanal_id}-4k"]
    
    debug_log = "" # Ne olduğunu görmek için log tutuyoruz

    for slug in variations:
        api_url = f"https://embed.beyazelma78.com/api/play/{slug}"
        try:
            api_res = curl_cffi.get(api_url, 
                impersonate="chrome", 
                headers={"Referer": "https://embed.beyazelma78.com/"}, 
                verify=False, 
                timeout=5)
            
            # Gelen cevabı loga ekle
            debug_log += f"Denenen ID: {slug} | Site Kodu: {api_res.status_code}\n"

            if api_res.status_code == 200:
                data = api_res.json()
                stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
                
                if stream_url:
                    # Token'ı bulduk! IPTV'yi doğrudan bu taze linke yönlendir
                    return redirect(stream_url, code=302)
                else:
                    debug_log += f"Cevap (Link Yok): {api_res.text[:100]}...\n"
            else:
                debug_log += f"Cevap (Hata): {api_res.text[:50]}...\n"
        except Exception as e:
            debug_log += f"Baglanti Hatasi: {str(e)}\n"

    # Hepsi başarısız olursa ekrana logu bas
    return f"Kanal bulunamadi. Detaylar:\n{debug_log}", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
