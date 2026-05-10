import os
import re
import requests
import shutil
import base64
import time

# --- 配置区 ---
# 💡 改进：支持多个源链接
SOURCE_URLS = [
    "https://spider.rer.de5.net/sub?52GQylQw=txt",
    "这里填入第二个源链接",
    "这里填入第三个源链接"
]
OUTPUT_DIR = "temp_zubo"

# GitHub 配置
GITHUB_TOKEN = os.getenv("LIVE_TOKEN")
GITHUB_REPO = "yubaomo02/LIVE"
GITHUB_BRANCH = "main"
GITHUB_FOLDER = "zubo"
# --- --- --- ---

def translate_isp(raw_isp):
    if not raw_isp: return "其他"
    isp_str = raw_isp.upper()
    if any(x in isp_str for x in ["CHINANET", "TELECOM", "电信"]): return "电信"
    if any(x in isp_str for x in ["CNC", "UNICOM", "联通"]): return "联通"
    if any(x in isp_str for x in ["MOBILE", "CMI", "铁通", "移动"]): return "移动"
    if any(x in isp_str for x in ["CERNET", "教育网"]): return "教育网"
    if any(x in isp_str for x in ["CRTC", "BROADCAST", "广电"]): return "广电"
    cleaned = re.sub(r'[a-zA-Z\s\.\-_]', '', raw_isp)
    return cleaned if cleaned else "其他"

def get_ip_info(ip):
    try:
        # 增加延迟防止 IP-API 封禁
        time.sleep(1)
        response = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
        data = response.json()
        if data.get('status') == 'success':
            region = data.get('regionName', '').replace("省", "").replace("市", "")
            isp = translate_isp(data.get('isp', ''))
            return f"{region}{isp}"
    except:
        pass
    return "未知"

def upload_to_github(file_path, file_name):
    """使用 GitHub API 上传/更新文件"""
    if not GITHUB_TOKEN:
        print(f"❌ 缺失 Token，无法上传 {file_name}")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FOLDER}/{file_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    get_res = requests.get(url, headers=headers)
    sha = None
    if get_res.status_code == 200:
        sha = get_res.json().get("sha")

    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    data = {
        "message": f"🤖 Auto-update zubo: {file_name}",
        "content": content,
        "branch": GITHUB_BRANCH
    }
    if sha:
        data["sha"] = sha

    put_res = requests.put(url, headers=headers, json=data)
    if put_res.status_code in [200, 201]:
        print(f"✅ GitHub 同步成功: {file_name}")
    else:
        print(f"❌ GitHub 同步失败 ({file_name}): {put_res.status_code}")

def main():
    if not GITHUB_TOKEN:
        print("❌ 未检测到 LIVE_TOKEN，请检查 GitHub Secrets 配置！")
        return

    if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ip_groups = {}
    
    # 💡 改进：多源循环逻辑
    for source_url in SOURCE_URLS:
        print(f"\n📥 正在获取源数据: {source_url}")
        try:
            r = requests.get(source_url, timeout=15)
            r.encoding = 'utf-8'
            lines = r.text.split('\n')
        except Exception as e:
            print(f"❌ 获取源失败 ({source_url}): {e}")
            continue

        for line in lines:
            line = line.strip()
            if ',' not in line or "#genre#" in line: continue
            parts = line.split(',', 1)
            if len(parts) < 2: continue
            name, url = parts[0], parts[1]
            
            match = re.search(r'://([\d\.]+):(\d+)', url)
            if match:
                host = match.group(1)
                port = match.group(2)
                key = f"{host}:{port}"
                
                # --- 核心改进：跨源去重逻辑 ---
                # 如果这个 IP:Port 在之前的源或当前源中处理过，直接跳过整个节点
                if key in ip_groups:
                    continue 
                # ----------------------------
                
                print(f"🔍 发现新组播 IP: {host} ... ", end="", flush=True)
                info = get_ip_info(host)
                print(f"结果: {info}")
                
                ip_groups[key] = {
                    "filename": f"{info}_{host.replace('.', '_')}_{port}.m3u",
                    "channels": []
                }
                # 组播通常一个 IP 下会有多个频道，我们需要把当前行的频道存入
                ip_groups[key]["channels"].append({"name": name, "url": url})

    if not ip_groups:
        print("\n⚠️ 未从所有源中解析到任何新的有效数据")
        return

    print(f"\n🚀 开始上传 {len(ip_groups)} 个新发现的 IP 节点到 GitHub...")
    for key, data in ip_groups.items():
        filename = data["filename"]
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in data["channels"]:
                f.write(f"#EXTINF:-1,{ch['name']}\n{ch['url']}\n")
        
        upload_to_github(filepath, filename)

    print("\n✨ Zubo 多源同步任务全部完成！")

if __name__ == "__main__":
    main()