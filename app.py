@app.route('/play/<kanal_id>')
def play_channel(kanal_id):
    clean_id = kanal_id.replace(".m3u8", "")
    
    try:
        # 1. Doğrudan API'yi dene
        api_url = f"{EMBED_URL}/api/play/{clean_id}"
        api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
        
        stream_url = None
        if api_res.status_code == 200:
            data = api_res.json()
            stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
            
        # 2. Eğer bulamadıysa iframe'e bak
        if not stream_url:
            page_url = f"{BASE_URL}/kanal/{clean_id}"
            page_res = curl_cffi.get(page_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
            embed_paths = re.findall(r'/api/embed\?u=[A-Za-z0-9_\-]+', page_res.text)
            
            if embed_paths:
                embed_url = f"{BASE_URL}" + embed_paths[0]
                embed_res = curl_cffi.get(embed_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
                slug_match = re.search(r'"slug"\s*:\s*"([^"]+)"', embed_res.text)
                
                if slug_match:
                    real_slug = slug_match.group(1)
                    api_url = f"{EMBED_URL}/api/play/{real_slug}"
                    api_res = curl_cffi.get(api_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
                    
                    if api_res.status_code == 200:
                        data = api_res.json()
                        stream_url = data.get("primary") or (data.get("fallbacks")[0] if data.get("fallbacks") else None)
        
        if not stream_url:
            return f"Yayin linki bulunamadi (ID: {clean_id})", 404
            
        # M3U8 metnini al
        m3u8_res = curl_cffi.get(stream_url, impersonate="chrome", headers=HEADERS, verify=False, timeout=8)
        
        if m3u8_res.status_code != 200:
            return f"Yayin Sunucusu Hatasi: {m3u8_res.status_code}", 403
            
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
                
        # EĞER LİSTE BOŞSA EKRANA YAZDIR (Hata ayıklama için)
        if len(new_lines) <= 1:
            return f"M3U8 BOS GELDI. Site URL: {stream_url} | Gelen Cevap: {m3u8_res.text[:100]}", 500
                
        return Response(
            '\n'.join(new_lines), 
            mimetype='application/vnd.apple.mpegurl',
            headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}
        )
        
    except Exception as e:
        return f"Hata: {str(e)}", 500
