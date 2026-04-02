import os
import re

# 配置路径
SOURCE_DIR = "zubo"
RTP_TARGET_DIR = "py/rtp"

def get_sort_key(line):
    """
    智能排序逻辑：(是否为SD, 核心名自然排序, 原始全名)
    """
    if ',' not in line: return (1, [], line)
    channel_name = line.split(',')[0].upper()
    
    # SD 优先级：带有标清/SD 的排在后面 (1)，高清排在前面 (0)
    is_sd = 1 if re.search(r'(SD|标清)', channel_name) else 0
    
    # 提取数字进行自然排序 (CCTV1 < CCTV10)
    core_name = re.sub(r'(HD|SD|4K|8K|高清|标清|超清|超高|频道)$', '', channel_name).strip()
    parts = [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', core_name)]
    
    return (is_sd, parts, channel_name)

def extract_and_classify():
    if not os.path.exists(RTP_TARGET_DIR):
        os.makedirs(RTP_TARGET_DIR, exist_ok=True)

    # 存储结构：{ "北京联通": { "rtp://...": ["CCTV1", "CCTV1HD"] } }
    rtp_data_storage = {} 
    
    if not os.path.exists(SOURCE_DIR):
        print(f"❌ 找不到源目录: {SOURCE_DIR}")
        return

    for filename in os.listdir(SOURCE_DIR):
        if not filename.endswith(".m3u"): continue
        file_path = os.path.join(SOURCE_DIR, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except: continue

    # 匹配模式：增加对 group-title 完整内容的提取
    pattern = re.compile(r'#EXTINF:-1.*?group-title="(.*?)",(.*?)\n.*?/rtp/(.*)')
    matches = pattern.findall(content)

    for group_info, channel_name, rtp_addr in matches:
        # --- 改进：提取省份 + 运营商 ---
        # 去掉 group-title 中的多余空格，并替换为空白字符，合并为 "北京联通"
        full_isp = group_info.strip().replace(" ", "") 
        if not full_isp: 
            full_isp = "未知地区"

        clean_name = channel_name.strip().replace("-", "")
        clean_rtp = f"rtp://{rtp_addr.strip()}"
        
        if full_isp not in rtp_data_storage:
            rtp_data_storage[full_isp] = {}
        
        if clean_rtp not in rtp_data_storage[full_isp]:
            rtp_data_storage[full_isp][clean_rtp] = []
        rtp_data_storage[full_isp][clean_rtp].append(clean_name)

    print(f"💾 正在分类生成文件，目标目录: {RTP_TARGET_DIR}")

    for isp_name, rtp_map in rtp_data_storage.items():
        processed_entries = []
        
        for rtp_url, names in rtp_map.items():
            # 同源去重：优先选择名字最短的（通常是不带 HD 后缀的基准名）
            best_name = sorted(names, key=lambda x: len(re.sub(r'(HD|高清|标清|SD)', '', x)))[0]
            # 统一去掉末尾的 HD/高清，使列表整洁
            best_name = re.sub(r'(HD|高清)$', '', best_name, flags=re.IGNORECASE).strip()
            
            processed_entries.append(f"{best_name},{rtp_url}")

        # 应用高级排序
        sorted_entries = sorted(processed_entries, key=get_sort_key)
        
        # --- 改进：生成文件名 ---
        # 确保文件名合法，去掉可能导致系统报错的字符
        safe_filename = re.sub(r'[\\/:*?"<>|]', '', isp_name)
        target_file = os.path.join(RTP_TARGET_DIR, f"{safe_filename}.txt")
        
        with open(target_file, 'w', encoding='utf-8') as tf:
            for line in sorted_entries:
                tf.write(line + "\n")

    print(f"✅ 处理完成！已按【地区运营商】分类生成 {len(rtp_data_storage)} 个文件。")

if __name__ == "__main__":
    extract_and_classify()
