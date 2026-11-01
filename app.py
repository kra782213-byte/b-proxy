from flask import Flask, Response, redirect
import curl_cffi
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route('/liste.m3u')
def generate_m3u():
    try:
        res = curl_cffi.get("https://beyazelma78.com/kanallar", impersonate="chrome", verify=False, timeout=10)
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
    try:
        res = curl_cffi.get("https://beyazelma78.com/kanallar", impersonate="chrome", verify=False, timeout=10)
        regex = re.compile(r'href="/kanal/([^"]+)"[\s\S]*?class="site-channel-row-name">([^<]+)<')
        matches = regex.findall(res.text)
        real_slug = next((id for id, name in matches if kanal_id in id), None)
        if not real_slug:
            return f"Kanal bulunamadi. (Aranan: {kanal_id})", 404

        api_url = f"https://embed.beyazelma78.com/api/play/{real_slug}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers={"Referer": "https://embed.beyazelma78.com/"}, verify=False, timeout=5)

        if api_res.status_code == 200:
            data = api_res.json()
            stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            if stream_url:
                return redirect(stream_url, code=302)

        return f"Yayin linki alinamadi. (ID: {real_slug})", 404
    except Exception as e:
        return f"Hata: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
