import os
import requests
import base64
import time
from urllib.parse import urlparse

# ================= 配置区 =================
SOURCE_URL = "https://spider.rer.de5.net/sub?57hmNXHI=txt"
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
    print(f"📥 正在获取源数据: {SOURCE_URL}")
    try:
        res = requests.get(SOURCE_URL, timeout=15)
        lines = res.text.split('\n')
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return

    ip_groups = {}
    for line in lines:
        line = line.strip()
        if "," not in line or "#genre#" in line: continue
        try:
            name, url = line.split(',', 1)
            host = urlparse(url).netloc
            if not host: continue
            
            if host not in ip_groups:
                ip = host.split(':')[0]
                port = host.split(':')[1] if ':' in host else "80"
                print(f"🔍 查询 IP: {ip} ... ", end="", flush=True)
                loc = get_ip_location(ip)
                print(f"结果: {loc}")
                ip_groups[host] = {"file": f"{loc}_{ip.replace('.', '_')}_{port}.m3u", "content": "#EXTM3U\n"}
            
            ip_groups[host]["content"] += f'#EXTINF:-1 group-title="Hotel_{host}",{name}\n{url.strip()}\n'
        except: continue

    if not ip_groups:
        print("⚠️ 未解析到有效数据")
        return

    print(f"🚀 开始通过 API 同步到 GitHub 库 (目标文件夹: {REMOTE_FOLDER})...")
    for host, data in ip_groups.items():
        upload_to_github(data["file"], data["content"])

if __name__ == "__main__":
    run()
