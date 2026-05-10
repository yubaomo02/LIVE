import os
import requests
import base64
import time
from urllib.parse import urlparse

# ================= 配置区 =================
SOURCE_URLS = [
    "https://boyu.ccwu.cc/sub1",
    "https://iptv-spider-production.up.railway.app/sub?rGzNKN5g=txt"
]
GITHUB_REPO = "yubaomo02/LIVE"
GITHUB_BRANCH = "main"

# 🔑 核心改进：从环境变量读取 Token，安全第一
# 请确保你在 Settings -> Secrets 中创建了名为 LIVE_TOKEN 的密钥
GITHUB_TOKEN = os.getenv("LIVE_TOKEN")

# 存放位置（仓库里的路径）
REMOTE_FOLDER = "hotel"

# IP 属地 API
IP_API = "http://ip-api.com/json/{}?fields=status,regionName,city&lang=zh-CN"
# ==========================================

def get_ip_location(ip):
    try:
        # 增加一秒延迟，遵守 API 使用规范，防止被 429 封禁
        time.sleep(1) 
        r = requests.get(IP_API.format(ip), timeout=5)
        data = r.json()
        if data.get('status') == 'success':
            reg = data.get('regionName', '').replace('省', '').replace('市', '')
            cit = data.get('city', '').replace('省', '').replace('市', '')
            return reg if reg == cit else f"{reg}{cit}"
    except: pass
    return "未知属地"

def upload_to_github(filename, content):
    """使用 GitHub API 直接上传/更新文件"""
    if not GITHUB_TOKEN:
        print("❌ 错误: 未能在环境变量中找到 LIVE_TOKEN")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{REMOTE_FOLDER}/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. 获取文件的 sha (用于更新现有文件)
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get('sha')

    # 2. 构造上传数据
    # 内容必须是 base64 编码
    base64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": f"🤖 自动更新节点: {filename}",
        "content": base64_content,
        "branch": GITHUB_BRANCH
    }
    if sha:
        data["sha"] = sha

    # 3. 发送 PUT 请求
    put_r = requests.put(url, headers=headers, json=data)
    if put_r.status_code in [200, 201]:
        print(f"✅ GitHub 同步成功: {filename}")
    else:
        print(f"❌ GitHub 同步失败 ({filename}): {put_r.status_code}")

def run():
    ip_groups = {}
    
    for url in SOURCE_URLS:
        print(f"📥 正在获取源数据: {url}")
        try:
            res = requests.get(url, timeout=15)
            res.encoding = 'utf-8' 
            lines = res.text.split('\n')
        except Exception as e:
            print(f"❌ 获取失败 ({url}): {e}")
            continue 

        for line in lines:
            line = line.strip()
            if "," not in line or "#genre#" in line: continue
            try:
                name, stream_url = line.split(',', 1)
                host = urlparse(stream_url).netloc
                if not host: continue
                
                # --- 核心改进：跳过逻辑 ---
                # 如果当前 host (IP+端口) 已经在 ip_groups 中，
                # 说明在之前的链接（第一个链接）已经查询过并处理了该 IP。
                if host in ip_groups:
                    continue # 直接跳过，不解析也不追加
                # ------------------------

                # 如果走到这一步，说明是一个全新的 IP
                ip = host.split(':')[0]
                port = host.split(':')[1] if ':' in host else "80"
                
                print(f"🔍 发现新 IP: {ip} ... ", end="", flush=True)
                loc = get_ip_location(ip)
                print(f"结果: {loc}")
                
                ip_groups[host] = {
                    "file": f"{loc}_{ip.replace('.', '_')}_{port}.m3u", 
                    "content": "#EXTM3U\n"
                }
                
                # 写入第一个发现的频道信息
                channel_info = f'#EXTINF:-1 group-title="Hotel_{host}",{name}\n{stream_url.strip()}\n'
                ip_groups[host]["content"] += channel_info
                    
            except: continue

    if not ip_groups:
        print("⚠️ 未解析到任何新数据")
        return

    print(f"🚀 开始同步到 GitHub (共 {len(ip_groups)} 个新 IP 节点)...")
    for host, data in ip_groups.items():
        upload_to_github(data["file"], data["content"])

if __name__ == "__main__":
    run()
