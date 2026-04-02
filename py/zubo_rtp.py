import os
import re

# 配置路径
SOURCE_DIR = "zubo"
RTP_TARGET_DIR = "py/rtp"
LOG_FILE = "py/rtp/mapping_log.txt"

def get_sort_key(line):
    """
    智能排序与分类逻辑：
    返回元组: (是否为SD, 核心名列表, 原始全名)
    """
    channel_name = line.split(',')[0].upper()
    
    # 1. 优先级判断：如果是 SD/标清，第一项设为 1，否则为 0。这样排序时 SD 会在最后。
    is_sd = 1 if re.search(r'(SD|标清)', channel_name) else 0
    
    # 2. 提取核心名用于自然排序 (CCTV1 < CCTV10)
    core_name = re.sub(r'(HD|SD|4K|8K|高清|标清|超清|超高|频道)$', '', channel_name).strip()
    parts = [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', core_name)]
    
    return (is_sd, parts, channel_name)

def extract_and_classify():
    if not os.path.exists(RTP_TARGET_DIR):
        os.makedirs(RTP_TARGET_DIR, exist_ok=True)

    rtp_data_storage = {} # { isp: { rtp_url: [name1, name2] } }
    
    if not os.path.exists(SOURCE_DIR):
        return

    for filename in os.listdir(SOURCE_DIR):
        if not filename.endswith(".m3u"): continue
        file_path = os.path.join(SOURCE_DIR, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except: continue

        pattern = re.compile(r'#EXTINF:-1.*?group-title="(.*?)",(.*?)\n.*?/rtp/(.*)')
        matches = pattern.findall(content)

        for group_info, channel_name, rtp_addr in matches:
            isp_name = group_info.split()[-1] if group_info.split() else "未知运营商"
            clean_name = channel_name.strip().replace("-", "")
            clean_rtp = f"rtp://{rtp_addr.strip()}"
            
            if isp_name not in rtp_data_storage:
                rtp_data_storage[isp_name] = {}
            
            # --- 核心改进：以 RTP 地址为 Key 收集频道名 ---
            if clean_rtp not in rtp_data_storage[isp_name]:
                rtp_data_storage[isp_name][clean_rtp] = []
            rtp_data_storage[isp_name][clean_rtp].append(clean_name)

    # --- 写入与高级去重阶段 ---
    print("💾 正在执行同源去重与 SD 沉底排序...")
    for isp_name, rtp_map in rtp_data_storage.items():
        processed_entries = []
        
        for rtp_url, names in rtp_map.items():
            # 同源去重逻辑：如果一个地址对应多个名字（全纪实、全纪实HD）
            if len(names) > 1:
                # 优先保留不带 HD/高清 后缀的最短名字，使名字规范化
                # 例如：['全纪实', '全纪实HD'] -> 保留 '全纪实'
                best_name = sorted(names, key=lambda x: len(re.sub(r'(HD|高清|标清|SD)', '', x)))[0]
                # 再次清理一次 best_name，去掉可能残留的后缀
                best_name = re.sub(r'(HD|高清)$', '', best_name, flags=re.IGNORECASE).strip()
            else:
                best_name = names[0]
            
            processed_entries.append(f"{best_name},{rtp_url}")

        # 应用自定义排序：自然排序 + SD 沉底
        sorted_entries = sorted(processed_entries, key=get_sort_key)
        
        target_file = os.path.join(RTP_TARGET_DIR, f"{isp_name}.txt")
        with open(target_file, 'w', encoding='utf-8') as tf:
            for line in sorted_entries:
                tf.write(line + "\n")

    print(f"✅ 处理完成！同源 HD 已合并，SD 频道已移至文件末尾。")

if __name__ == "__main__":
    extract_and_classify()
