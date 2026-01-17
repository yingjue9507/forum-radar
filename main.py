import flet as ft
import requests
import json
import time
import re
import datetime
import urllib3
import traceback
import threading  # 🔥 核心引入：多线程
from bs4 import BeautifulSoup

# ================= 🔧 0. 全局配置 =================

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- API 配置 ---
FORUM_API_URL = "https://com1.j3roe3vnnk4e92-udhle6.work/com/record.html"
TARGET_URL = "https://160.124.142.10:50415/index.html"

# 伪装 Header
SEARCH_HEADERS = {
    "Host": "com1.j3roe3vnnk4e92-udhle6.work",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Referer": "https://qnxyl.2ldkc1pdg6fx5arh.work/",
    "Origin": "https://qnxyl.2ldkc1pdg6fx5arh.work",
    "Accept": "*/*",
    "Sec-Ch-Ua": '"Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?1",
    "Sec-Ch-Ua-Platform": '"Android"',
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Dest": "script"
}

SCRAPE_HEADERS = {
    "Host": "160.124.142.10:50415",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Referer": "https://160.124.142.10:50415/",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
}

# ================= 🛠️ 1. 辅助函数 =================

def format_timestamp(ts):
    try:
        if not ts: return ""
        ts_int = int(ts)
        if ts_int > 10000000000: ts_int = ts_int / 1000
        dt = datetime.datetime.fromtimestamp(ts_int)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)

# ================= 🌐 2. 核心逻辑 =================

def fetch_json_infinite(keyword, page_num, search_type="content"):
    callback_name = f"jQuery{int(time.time() * 1000)}_{int(time.time() * 1000)}"
    clean_keyword = keyword.strip()
    
    params = {
        "callback": callback_name, "orderby": "plid", "id": "67",
        "key_word": "", "key_msg_word": "", "page": str(page_num)
    }
    if search_type == "user": params["key_word"] = clean_keyword
    else: params["key_msg_word"] = clean_keyword

    for attempt in range(3):
        try:
            response = requests.get(FORUM_API_URL, headers=SEARCH_HEADERS, params=params, timeout=10, verify=False)
            if response.status_code == 200:
                match = re.search(r'jQuery.*?\((\{.*\})\)', response.text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    result_list = data.get('data') or data.get('list')
                    return result_list if result_list is not None else []
        except Exception:
            time.sleep(1)
    return None

def fetch_and_parse_data():
    all_data = []
    logs = []
    try:
        logs.append(f"正在连接目标...")
        response = requests.get(TARGET_URL, headers=SCRAPE_HEADERS, verify=False, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code != 200: return [], f"状态码: {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        all_lis = soup.find_all("li")
        logs.append(f"🔍 发现 {len(all_lis)} 行数据")
        
        processed_hashes = set()
        for li in all_lis:
            text = li.get_text(strip=True)
            if not text: continue
            p_match = re.search(r'(\d+)\s*[期:：]', text)
            if not p_match: continue
            period = f"{p_match.group(1)}期"
            
            section_name = "其他版块"
            try:
                parent_ul = li.find_parent("ul")
                if parent_ul:
                    prev = parent_ul.find_previous(class_=re.compile(r'(tit|head|caption|pb-tit|ptyx-tit)'))
                    if prev: section_name = prev.get_text(strip=True)
            except: pass
            
            content = ""
            c_match = re.search(r'(【.*?】)', text)
            if c_match: content = c_match.group(1)
            else:
                parts = re.split(r'[:：]', text, 1)
                if len(parts) > 1: content = parts[1].strip()
            
            status = "准" if "准" in text else ("错" if "错" in text else ("更新中" if "更新" in text else ""))
            row_hash = f"{section_name}_{period}_{content}"
            if row_hash in processed_hashes: continue
            processed_hashes.add(row_hash)
            all_data.append([section_name, period, content, status])
        logs.append(f"✅ 成功提取 {len(all_data)} 条")
    except Exception as e:
        return [], f"❌ 解析错误: {str(e)}"
    return all_data, "\n".join(logs)

# ================= 📱 3. 主界面 APP =================

def main(page: ft.Page):
    try:
        page.title = "情报雷达 v10.2"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0

        # 防崩检查
        watchlist_data = []
        try:
            watchlist_data = page.client_storage.get("watchlist") or []
        except Exception:
            watchlist_data = []

        seen_ids = set()
        current_search_id = [0]
        # 缓存数据
        search_results_data = []
        scrape_results_data = [] 

        # --- 页面 1: 搜索组件 ---
        search_type_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option("content", "搜内容"), ft.dropdown.Option("user", "搜用户")],
            value="content", width=110, height=45, content_padding=10, bgcolor="white", text_size=14, border_radius=8
        )
        search_keyword = ft.TextField(
            hint_text="输入关键词...", height=45, expand=True, content_padding=10, bgcolor="white",
            on_submit=lambda e: trigger_search_thread(e), border_radius=8
        )
        
        # 🔥 优化：搜索按钮的状态控制
        btn_search = ft.ElevatedButton("开始搜索", on_click=lambda e: trigger_search_thread(e), bgcolor=ft.Colors.BLUE_600, color="white", height=40, expand=True)
        
        search_list_view = ft.ListView(expand=True, spacing=5, padding=10)
        status_text = ft.Text("准备就绪", size=12, color="grey")
        result_count = ft.Text("", size=12, color="amber")
        progress_bar = ft.ProgressBar(visible=False, color="blue", bgcolor="#E0E0E0")
        
        # --- 页面 2: 关注组件 ---
        new_user_input = ft.TextField(hint_text="输入昵称", expand=True, height=45)
        watchlist_col = ft.ListView(expand=True, spacing=10, padding=20)
        
        # --- 页面 3: 采集组件 ---
        scrape_status = ft.Text("准备就绪", color="grey")
        log_box = ft.ListView(height=80, spacing=2, padding=10, auto_scroll=True)
        
        data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("版块")), 
                ft.DataColumn(ft.Text("内容")), 
                ft.DataColumn(ft.Text("状态")),
                ft.DataColumn(ft.Text("删"))
            ],
            rows=[], column_spacing=10, heading_row_color=ft.Colors.BLUE_50, data_row_min_height=40,
        )

        copy_text_field = ft.TextField(
            label="📝 手动复制/编辑区",
            multiline=True, min_lines=5, max_lines=10, text_size=12, bgcolor="white",
            hint_text="采集数据将显示在这里...",
        )

        btn_scrape = ft.ElevatedButton("一键采集", on_click=lambda e: trigger_scrape_thread(e), bgcolor=ft.Colors.BLUE_600, color="white", expand=True)
        
        # --- 🧵 多线程逻辑: 搜索 ---
        
        def trigger_search_thread(e=None, manual_query=None, manual_type=None):
            # 1. 立即更新UI状态 (主线程执行)
            if "停止" in btn_search.text:
                # 停止逻辑
                current_search_id[0] += 1
                btn_search.text = "开始搜索"
                btn_search.bgcolor = ft.Colors.BLUE_600
                progress_bar.visible = False
                status_text.value = "🛑 已停止"
                status_text.color = "red"
                page.update()
                return

            keyword = manual_query if manual_query else search_keyword.value
            current_type = manual_type if manual_type else search_type_dropdown.value
            
            if not keyword:
                page.show_snack_bar(ft.SnackBar(ft.Text("❌ 请输入关键词")))
                return

            # UI 变色响应
            btn_search.text = "停止搜索"
            btn_search.bgcolor = ft.Colors.ORANGE_600 # 🔥 变色显示正在搜索
            progress_bar.visible = True
            status_text.value = f"🚀 初始化..."
            status_text.color = "blue"
            
            # 清空旧数据
            scrape_results_data.clear()
            search_list_view.controls.clear()
            seen_ids.clear()
            search_results_data.clear()
            page.update()
            
            # 2. 启动后台线程
            t = threading.Thread(
                target=run_search_background,
                args=(keyword, current_type, current_search_id[0] + 1),
                daemon=True
            )
            current_search_id[0] += 1
            t.start()

        def run_search_background(keyword, current_search_type, my_session_id):
            total_loaded = 0
            current_page = 1
            empty_retry_count = 0

            try:
                while True:
                    if current_search_id[0] != my_session_id: return

                    # 更新状态
                    status_text.value = f"📡 请求第 {current_page} 页..."
                    page.update()

                    items_list = fetch_json_infinite(keyword, current_page, current_search_type)
                    
                    if items_list is None:
                        status_text.value = "⚠️ 网络波动，重试中..."
                        page.update()
                        time.sleep(1)
                        continue

                    if len(items_list) == 0:
                        empty_retry_count += 1
                        if empty_retry_count >= 2:
                            status_text.value = f"✅ 所有数据加载完毕"
                            status_text.color = "green"
                            break
                        else:
                            current_page += 1
                            time.sleep(1)
                            continue
                    else:
                        empty_retry_count = 0

                    # 渲染数据 (批量添加提升性能)
                    new_controls = []
                    for item in items_list:
                        rec_id = str(item.get('id') or '')
                        if rec_id in seen_ids: continue
                        seen_ids.add(rec_id)

                        user = item.get('nickname') or item.get('username') or '未知'
                        raw = item.get('saycontent') or item.get('content') or ''
                        clean = re.sub(r'<[^>]+>', '', str(raw)).strip()
                        ts = format_timestamp(item.get('saytime') or item.get('time'))
                        is_vip = user in watchlist_data
                        search_results_data.append([rec_id, user, ts, clean])
                        
                        new_controls.append(ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Row([ft.Icon(ft.Icons.VERIFIED if is_vip else ft.Icons.PERSON, size=16, color="orange" if is_vip else "grey"),
                                            ft.Text(user, weight="bold", color="orange" if is_vip else "black"),
                                            ft.Text(f"#{rec_id}", size=10, color="grey")]),
                                    ft.Text(ts, size=11, color="grey")
                                ], alignment="spaceBetween"),
                                ft.Container(height=5), ft.Text(clean, size=14, selectable=True),
                            ]), padding=10, border_radius=8, bgcolor="yellow.50" if is_vip else "white", border=ft.border.all(1, "orange" if is_vip else "#eeeeee")
                        ))
                        total_loaded += 1
                    
                    # 提交UI更新
                    search_list_view.controls.extend(new_controls)
                    result_count.value = f"已找到: {total_loaded} 条"
                    page.update()

                    current_page += 1
                    
                    # 🔥 防封倒计时 (在后台线程执行，不会卡顿UI)
                    for i in range(3, 0, -1):
                        if current_search_id[0] != my_session_id: return
                        status_text.value = f"⏳ 冷却中 {i}s..."
                        page.update()
                        time.sleep(1)

            except Exception as e:
                status_text.value = f"出错: {str(e)[:20]}"
            finally:
                if current_search_id[0] == my_session_id:
                    btn_search.text = "开始搜索"
                    btn_search.bgcolor = ft.Colors.BLUE_600
                    progress_bar.visible = False
                    status_text.value = f"✅ 完成: {total_loaded}条"
                    status_text.color = "green"
                    page.update()

        # --- 🧵 多线程逻辑: 采集 ---

        def trigger_scrape_thread(e):
            if btn_scrape.disabled: return
            btn_scrape.disabled = True
            btn_scrape.text = "正在采集..."
            scrape_status.value = "🚀 连接服务器..."
            scrape_status.color = "blue"
            log_box.controls.clear()
            page.update()

            t = threading.Thread(target=run_scrape_background, daemon=True)
            t.start()

        def run_scrape_background():
            scrape_results_data.clear()
            search_results_data.clear()
            
            data, log_str = fetch_and_parse_data()
            
            # 更新日志
            for line in log_str.split('\n'):
                if line: log_box.controls.append(ft.Text(line, size=10))
            page.update()

            if data:
                scrape_status.value = "✅ 采集成功"
                scrape_status.color = "green"
                for row in data:
                    scrape_results_data.append(row)
                update_scrape_ui()
            else: 
                scrape_status.value = "❌ 采集失败"
                scrape_status.color = "red"
                
            btn_scrape.disabled = False
            btn_scrape.text = "一键采集"
            page.update()

        def delete_scrape_item(e, row_data):
            if row_data in scrape_results_data:
                scrape_results_data.remove(row_data)
                update_scrape_ui()
                page.show_snack_bar(ft.SnackBar(ft.Text("🗑️ 已移除"), duration=500))

        def update_scrape_ui():
            ft_rows = []
            text_lines = []
            for row in scrape_results_data:
                color = ft.Colors.GREEN if "准" in row[3] else (ft.Colors.RED if "错" in row[3] else ft.Colors.BLACK)
                ft_rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(row[0], size=10)),
                    ft.DataCell(ft.Text(row[2], size=12, width=150)),
                    ft.DataCell(ft.Text(row[3], size=12, color=color)),
                    ft.DataCell(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", icon_size=20, 
                                              on_click=lambda e, r=row: delete_scrape_item(e, r)))
                ]))
                line = f"[{row[0]}] {row[1]}: {row[2]} ({row[3]})"
                text_lines.append(line)
            data_table.rows = ft_rows
            copy_text_field.value = "\n".join(text_lines) if text_lines else ""
            page.update()

        # --- 布局 ---
        view_search = ft.Column([
            ft.Container(content=ft.Column([
                ft.Text("🔍 论坛情报雷达", size=20, weight="bold", color="white"), ft.Container(height=5),
                ft.Row([search_type_dropdown, search_keyword], spacing=10),
                ft.Row([btn_search], spacing=10),
                ft.Row([status_text, result_count], alignment="spaceBetween"), progress_bar
            ]), padding=15, bgcolor=ft.Colors.BLUE_800),
            ft.Container(content=search_list_view, expand=True, padding=5)
        ], spacing=0, expand=True, visible=True)

        def render_watchlist():
            watchlist_col.controls.clear()
            for u in watchlist_data:
                watchlist_col.controls.append(ft.Container(
                    content=ft.Row([ft.Row([ft.Icon(ft.Icons.STAR, color="amber"), ft.Text(u, size=16, weight="bold")]),
                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=lambda e, user=u: remove_user(user))], alignment="spaceBetween"),
                    padding=15, bgcolor="white", border=ft.border.all(1, "#eee"), border_radius=8,
                    on_click=lambda e, user=u: jump_to_search(user)
                ))
            page.update()

        def jump_to_search(name):
            nav_bar.selected_index = 0
            view_search.visible = True; view_watch.visible = False; view_scrape.visible = False
            search_type_dropdown.value = "user"; clean_name = name.strip(); search_keyword.value = clean_name; page.update()
            # 跳转也使用线程逻辑
            trigger_search_thread(manual_query=clean_name, manual_type="user")

        def add_user(e):
            name = new_user_input.value.strip()
            if name and name not in watchlist_data:
                watchlist_data.append(name); page.client_storage.set("watchlist", watchlist_data); new_user_input.value = ""; render_watchlist()
        def remove_user(name):
            if name in watchlist_data:
                watchlist_data.remove(name); page.client_storage.set("watchlist", watchlist_data); render_watchlist()

        view_watch = ft.Column([
            ft.Container(content=ft.Row([new_user_input, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color="blue", icon_size=40, on_click=add_user)]), padding=20),
            ft.Text("  点击卡片可快速搜索", size=12, color="grey"),
            ft.Container(content=watchlist_col, expand=True)
        ], expand=True, visible=False)

        view_scrape = ft.Column([
            ft.Container(content=ft.Column([
                ft.Text("📊 采集与手动整理", size=20, weight="bold", color="white"),
                ft.Row([btn_scrape]), scrape_status,
            ]), padding=15, bgcolor=ft.Colors.BLUE_800),
            ft.Container(content=log_box, height=80, border=ft.border.all(1, "#eee")),
            ft.Container(content=copy_text_field, padding=5),
            ft.Container(content=ft.ListView([data_table], expand=True), expand=True, padding=5)
        ], expand=True, visible=False)

        def nav_change(e):
            idx = e.control.selected_index
            view_search.visible = (idx == 0); view_watch.visible = (idx == 1); view_scrape.visible = (idx == 2)
            if idx == 1: render_watchlist()
            page.update()

        nav_bar = ft.NavigationBar(destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.SEARCH, label="搜索"),
            ft.NavigationBarDestination(icon=ft.Icons.STAR, label="关注"),
            ft.NavigationBarDestination(icon=ft.Icons.DATA_ARRAY, label="采集"),
        ], on_change=nav_change)

        page.add(ft.Column([view_search, view_watch, view_scrape], expand=True), nav_bar)

    except Exception as e:
        error_msg = traceback.format_exc()
        page.clean()
        page.add(
            ft.Column([
                ft.Text("❌ 程序启动错误！", color="red", size=20, weight="bold"),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Text(error_msg, color="white", size=12, font_family="monospace", selectable=True),
                    bgcolor="black", padding=10, border_radius=5, expand=True
                )
            ], expand=True)
        )
        page.update()

if __name__ == "__main__":
    ft.app(target=main)
