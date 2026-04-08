import os
import re
import requests
import shutil
import base64
import time

# --- 配置区 ---
SOURCE_URL = "https://spider.rer.de5.net/sub?3Rkha5PK=txt"
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
        # 增加延迟防止 IP-API 封禁 (保持每秒1次左右)
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
    
    # 检查 SHA
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
        # 💡 这里增加了同步成功的提示
        print(f"✅ GitHub 同步成功: {file_name}")
    else:
        print(f"❌ GitHub 同步失败 ({file_name}): {put_res.status_code}")

def main():
    if not GITHUB_TOKEN:
        print("❌ 未检测到 LIVE_TOKEN，请检查 GitHub Secrets 配置！")
        return

    if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"📥 正在获取源数据: {SOURCE_URL}")
    try:
        r = requests.get(SOURCE_URL, timeout=15)
        r.encoding = 'utf-8'
        lines = r.text.split('\n')
    except Exception as e:
        print(f"❌ 获取源失败: {e}"); return

    ip_groups = {}
    for line in lines:
        if ',' not in line or "#genre#" in line: continue
        parts = line.strip().split(',', 1)
        if len(parts) < 2: continue
        name, url = parts[0], parts[1]
        
        match = re.search(r'://([\d\.]+):(\d+)', url)
        if match:
            host = match.group(1)
            port = match.group(2)
            key = f"{host}:{port}"
            if key not in ip_groups:
                # 💡 在这里增加查询 IP 的实时反馈
                print(f"🔍 查询 IP: {host} ... ", end="", flush=True)
                info = get_ip_info(host)
                print(f"结果: {info}")
                
                ip_groups[key] = {
                    "filename": f"{info}_{host.replace('.', '_')}_{port}.m3u",
                    "channels": []
                }
            ip_groups[key]["channels"].append({"name": name, "url": url})

    if not ip_groups:
        print("⚠️ 未解析到有效数据")
        return

    print(f"🚀 开始通过 API 同步到 GitHub 库 (目标文件夹: {GITHUB_FOLDER})...")
    for key, data in ip_groups.items():
        filename = data["filename"]
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # 写入临时文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in data["channels"]:
                f.write(f"#EXTINF:-1,{ch['name']}\n{ch['url']}\n")
        
        # API 上传
        upload_to_github(filepath, filename)

    print("\n✨ Zubo 任务全部完成！")

if __name__ == "__main__":
    main()
