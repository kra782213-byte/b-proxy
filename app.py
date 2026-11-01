export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // 1. LİSTE OLUŞTURMA (.m3u ve .m3u8 destekler)
    if (path === "/liste.m3u" || path === "/liste.m3u8" || path === "/liste") {
      return await generateM3U(url.origin);
    }

    // 2. KANAL İZLEME
    if (path.startsWith("/play/")) {
      const kanalId = path.replace("/play/", "").replace(".m3u8", "");
      return await playChannel(kanalId, url.origin);
    }

    // 3. VİDEO PARÇALARINI PROXY'LEME
    const targetUrl = url.searchParams.get("url");
    if (targetUrl) {
      return await proxyStream(targetUrl);
    }

    return new Response("BeyazElma Cloudflare Proxy Aktif!", { status: 200 });
  }
};

async function generateM3U(origin) {
  try {
    // Siteye istek at
    const res = await fetch("https://beyazelma78.com/kanallar", {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9"
      }
    });
    
    if (!res.ok) {
      throw new Error(`Siteye erisilemedi (Kod: ${res.status})`);
    }

    const html = await res.text();

    // Kanalları ayıkla (Daha esnek bir regex)
    const regex = /href="\/kanal\/([^"]+)"[\s\S]*?class="site-channel-row-name"[^>]*>([^<]+)</g;
    let match;
    let m3u = "#EXTM3U\n";
    let added = 0;

    while ((match = regex.exec(html)) !== null) {
      const id = match[1];
      const name = match[2].trim().replace(/&amp;/g, '&');
      
      m3u += `#EXTINF:-1, ${name}\n`;
      m3u += `${origin}/play/${id}\n`;
      added++;
    }

    // Eğer hiç kanal bulunamadıysa IPTV'ye hata mesajı gönder (IPTV bunu kanal olarak gösterir)
    if (added === 0) {
      m3u += `#EXTINF:-1, HATA: Kanal bulunamadi (Site yapisi degismis olabilir)\n`;
      m3u += `http://hata\n`;
    }

    return new Response(m3u, {
      headers: { 
        "Content-Type": "application/x-mpegURL", // IPTV'lerin en sevdiği format
        "Content-Disposition": "attachment; filename=\"playlist.m3u8\"",
        "Access-Control-Allow-Origin": "*" 
      }
    });
  } catch (e) {
    // Eğer sistem çökerse, IPTV'ye geçerli bir m3u içinde hatayı gönder
    let errorM3u = "#EXTM3U\n";
    errorM3u += `#EXTINF:-1, HATA: ${e.message}\n`;
    errorM3u += `http://hata\n`;
    return new Response(errorM3u, {
      headers: { "Content-Type": "application/x-mpegURL", "Access-Control-Allow-Origin": "*" }
    });
  }
}

async function playChannel(kanalId, origin) {
  const headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://embed.beyazelma78.com/",
    "Origin": "https://embed.beyazelma78.com"
  };

  try {
    const apiRes = await fetch(`https://embed.beyazelma78.com/api/play/${kanalId}`, { headers });
    if (!apiRes.ok) return new Response("API Hatasi: " + apiRes.status, { status: apiRes.status });
    
    const data = await apiRes.json();
    const streamUrl = data.primary || (data.fallbacks && data.fallbacks[0]);
    if (!streamUrl) return new Response("Yayin linki yok", { status: 404 });

    const m3u8Res = await fetch(streamUrl, { headers });
    if (!m3u8Res.ok) return new Response("M3U8 Hatasi: " + m3u8Res.status, { status: m3u8Res.status });
    
    const text = await m3u8Res.text();
    const baseUrl = streamUrl.substring(0, streamUrl.lastIndexOf('/') + 1);

    const newText = text.split('\n').map(line => {
      line = line.trim();
      if (line === "" || line.startsWith("#")) return line;
      const absolute = line.startsWith("http") ? line : baseUrl + line;
      return `${origin}?url=${encodeURIComponent(absolute)}`;
    }).join('\n');

    return new Response(newText, {
      headers: { "Content-Type": "application/vnd.apple.mpegurl", "Access-Control-Allow-Origin": "*" }
    });

  } catch (e) {
    return new Response("Hata: " + e.message, { status: 500 });
  }
}

async function proxyStream(targetUrl) {
  try {
    const res = await fetch(targetUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://embed.beyazelma78.com/",
        "Origin": "https://embed.beyazelma78.com"
      }
    });
    
    return new Response(res.body, {
      headers: { 
        "Content-Type": res.headers.get("content-type") || "video/mp2t",
        "Access-Control-Allow-Origin": "*" 
      }
    });
  } catch (e) {
    return new Response("Proxy Hatasi: " + e.message, { status: 500 });
  }
}
