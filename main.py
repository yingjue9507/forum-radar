import flet as ft
import requests
import json
import time
import re
import datetime
import urllib3
import traceback
import threading
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

    # 构造参数：明确清空不需要的字段，防止干扰
    params = {
        "callback": callback_name,
        "orderby": "plid",
        "id": "67",
        "key_word": "",
        "key_msg_word": "",
        "page": str(page_num)
    }

    # 严格区分搜索类型
    if search_type == "user":
        params["key_word"] = clean_keyword
    else:
        params["key_msg_word"] = clean_keyword

    for attempt in range(3):
        try:
            # timeout 设置短一点，加快重试速度
            response = requests.get(FORUM_API_URL, headers=SEARCH_HEADERS, params=params, timeout=8, verify=False)
            if response.status_code == 200:
                match = re.search(r'jQuery.*?\((\{.*\})\)', response.text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    result_list = data.get('data') or data.get('list')
                    return result_list if result_list is not None else []
        except Exception:
            time.sleep(0.5)
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
            except:
                pass

            content = ""
            c_match = re.search(r'(【.*?】)', text)
            if c_match:
                content = c_match.group(1)
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
        page.title = "情报雷达 v10.3"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0

        # 数据初始化
        watchlist_data = []
        try:
            watchlist_data = page.client_storage.get("watchlist") or []
        except Exception:
            watchlist_data = []

        seen_ids = set()
        current_search_id = [0]
        # 缓存
        search_results_data = []
        scrape_results_data = []

        # --- 页面 1: 搜索组件 ---
        search_type_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option("content", "搜内容"), ft.dropdown.Option("user", "搜用户")],
            value="content", width=100, height=40, content_padding=5, bgcolor="white", text_size=14, border_radius=8
        )
        search_keyword = ft.TextField(
            hint_text="输入关键词...", height=40, expand=True, content_padding=10, bgcolor="white",
            on_submit=lambda e: trigger_search_thread(e), border_radius=8, text_size=14
        )

        btn_search = ft.ElevatedButton("搜索", on_click=lambda e: trigger_search_thread(e), bgcolor=ft.Colors.BLUE_600,
                                       color="white", height=40, width=80)

        search_list_view = ft.ListView(expand=True, spacing=5, padding=10)
        status_text = ft.Text("准备就绪", size=12, color="grey")
        result_count = ft.Text("", size=12, color="amber")
        # 进度条默认不可见
        progress_bar = ft.ProgressBar(visible=False, color="orange", bgcolor="#eeeeee", height=3)

        # --- 页面 2: 关注组件 (优化版) ---
        new_user_input = ft.TextField(
            hint_text="添加新用户", expand=True, height=40, content_padding=10, text_size=14,
            on_submit=lambda e: add_user(e)  # 允许回车添加
        )
        # 🔥 新增：关注列表筛选框
        watchlist_filter_input = ft.TextField(
            hint_text="🔍 快速查找名单...", height=35, content_padding=5, text_size=13,
            prefix_icon=ft.Icons.SEARCH, bgcolor="#f0f0f0", border_radius=8,
            on_change=lambda e: render_watchlist()  # 输入即筛选
        )

        watchlist_col = ft.ListView(expand=True, spacing=2, padding=10)  # 🔥 间距缩小到 2

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
            rows=[], column_spacing=10, heading_row_color=ft.Colors.BLUE_50, data_row_min_height=35,
        )

        copy_text_field = ft.TextField(
            label="📝 采集结果 (可复制)", multiline=True, min_lines=5, max_lines=10, text_size=12, bgcolor="white",
            hint_text="结果将显示在这里...",
        )

        btn_scrape = ft.ElevatedButton("一键采集", on_click=lambda e: trigger_scrape_thread(e),
                                       bgcolor=ft.Colors.BLUE_600, color="white", expand=True)

        # --- 🧵 多线程搜索逻辑 (极速响应版) ---

        def trigger_search_thread(e=None, manual_query=None, manual_type=None):
            # 1. 主线程 UI 立即响应 (0延迟)
            if "停止" in btn_search.text:
                current_search_id[0] += 1
                btn_search.text = "搜索"
                btn_search.bgcolor = ft.Colors.BLUE_600
                progress_bar.visible = False
                status_text.value = "🛑 已停止"
                page.update()
                return

            # 获取参数
            keyword = manual_query if manual_query else search_keyword.value
            current_type = manual_type if manual_type else search_type_dropdown.value

            if not keyword:
                page.show_snack_bar(ft.SnackBar(ft.Text("❌ 请输入关键词")))
                return

            # 🔥 立即变色，给用户反馈
            btn_search.text = "停止"
            btn_search.bgcolor = ft.Colors.ORANGE_600
            progress_bar.visible = True  # 显示进度条
            status_text.value = f"🚀 正在连接..."
            status_text.color = "blue"

            # 清空旧数据
            scrape_results_data.clear()
            search_list_view.controls.clear()
            seen_ids.clear()
            search_results_data.clear()
            page.update()  # 强制渲染

            # 2. 启动后台线程 (不卡顿)
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

                    status_text.value = f"📡 加载第 {current_page} 页..."
                    page.update()

                    items_list = fetch_json_infinite(keyword, current_page, current_search_type)

                    if items_list is None:
                        status_text.value = "⚠️ 网络波动，重试中..."
                        page.update()
                        time.sleep(1)
                        continue

                    if len(items_list) == 0:
                        empty_retry_count += 1
                        # 只有连续2次空才停止，防止单页真空
                        if empty_retry_count >= 2:
                            status_text.value = f"✅ 搜索完毕"
                            status_text.color = "green"
                            break
                        else:
                            current_page += 1
                            time.sleep(0.5)
                            continue
                    else:
                        empty_retry_count = 0

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

                        # 紧凑的卡片样式
                        new_controls.append(ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Row([ft.Icon(ft.Icons.VERIFIED if is_vip else ft.Icons.PERSON, size=14,
                                                    color="orange" if is_vip else "grey"),
                                            ft.Text(user, weight="bold", size=13,
                                                    color="orange" if is_vip else "black"),
                                            ft.Text(f"#{rec_id}", size=10, color="grey")]),
                                    ft.Text(ts, size=10, color="grey")
                                ], alignment="spaceBetween"),
                                ft.Container(height=2),
                                ft.Text(clean, size=13, selectable=True),
                            ]), padding=8, border_radius=6, bgcolor="yellow.50" if is_vip else "white",
                            border=ft.border.all(1, "orange" if is_vip else "#eeeeee")
                        ))
                        total_loaded += 1

                    search_list_view.controls.extend(new_controls)
                    result_count.value = f"已找到: {total_loaded} 条"
                    page.update()

                    current_page += 1

                    # 防封倒计时
                    for i in range(3, 0, -1):
                        if current_search_id[0] != my_session_id: return
                        status_text.value = f"⏳ 冷却 {i}s..."
                        page.update()
                        time.sleep(1)

            except Exception as e:
                status_text.value = f"出错: {str(e)[:20]}"
            finally:
                if current_search_id[0] == my_session_id:
                    btn_search.text = "搜索"
                    btn_search.bgcolor = ft.Colors.BLUE_600
                    progress_bar.visible = False
                    status_text.value = f"✅ 共 {total_loaded} 条"
                    status_text.color = "green"
                    page.update()

        # --- 采集逻辑 ---

        def trigger_scrape_thread(e):
            if btn_scrape.disabled: return
            btn_scrape.disabled = True;
            btn_scrape.text = "正在采集..."
            scrape_status.value = "🚀 正在解析网页...";
            scrape_status.color = "blue"
            log_box.controls.clear()
            page.update()
            threading.Thread(target=run_scrape_background, daemon=True).start()

        def run_scrape_background():
            scrape_results_data.clear()
            data, log_str = fetch_and_parse_data()
            for line in log_str.split('\n'):
                if line: log_box.controls.append(ft.Text(line, size=10))
            page.update()

            if data:
                scrape_status.value = "✅ 采集成功";
                scrape_status.color = "green"
                for row in data: scrape_results_data.append(row)
                update_scrape_ui()
            else:
                scrape_status.value = "❌ 采集失败";
                scrape_status.color = "red"

            btn_scrape.disabled = False;
            btn_scrape.text = "一键采集";
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
                text_lines.append(f"[{row[0]}] {row[1]}: {row[2]} ({row[3]})")
            data_table.rows = ft_rows
            copy_text_field.value = "\n".join(text_lines) if text_lines else ""
            page.update()

        # --- 布局构建 ---

        # 搜索页
        view_search = ft.Column([
            ft.Container(content=ft.Column([
                ft.Text("🔍 论坛情报雷达", size=20, weight="bold", color="white"), ft.Container(height=2),
                ft.Row([search_type_dropdown, search_keyword, btn_search], spacing=5),
                ft.Row([status_text, result_count], alignment="spaceBetween"),
                progress_bar
            ]), padding=15, bgcolor=ft.Colors.BLUE_800),
            ft.Container(content=search_list_view, expand=True, padding=5)
        ], spacing=0, expand=True, visible=True)

        # 关注页逻辑
        def render_watchlist(e=None):
            watchlist_col.controls.clear()
            filter_txt = watchlist_filter_input.value.strip().lower()  # 获取筛选词

            for u in watchlist_data:
                # 🔥 筛选逻辑
                if filter_txt and filter_txt not in u.lower():
                    continue

                watchlist_col.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Row([ft.Icon(ft.Icons.STAR, size=16, color="amber"), ft.Text(u, size=14, weight="bold")]),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", icon_size=18,
                                      on_click=lambda e, user=u: remove_user(user))
                    ], alignment="spaceBetween"),
                    padding=10, bgcolor="white", border=ft.border.all(1, "#eee"), border_radius=6,
                    on_click=lambda e, user=u: jump_to_search(user)
                ))
            page.update()

        def jump_to_search(name):
            nav_bar.selected_index = 0
            view_search.visible = True;
            view_watch.visible = False;
            view_scrape.visible = False
            search_type_dropdown.value = "user"
            clean_name = name.strip()
            search_keyword.value = clean_name
            page.update()  # 先切换页面
            # 🔥 立即调用搜索，不等待
            trigger_search_thread(manual_query=clean_name, manual_type="user")

        def add_user(e):
            name = new_user_input.value.strip()
            if name and name not in watchlist_data:
                # 1. 先更新内存数据和UI (极速响应)
                watchlist_data.insert(0, name)  # 插到最前面
                new_user_input.value = ""
                watchlist_filter_input.value = ""  # 清空筛选
                render_watchlist()
                page.update()

                # 2. 异步存入 storage (不阻塞UI)
                try:
                    page.client_storage.set("watchlist", watchlist_data)
                except:
                    pass

        def remove_user(name):
            if name in watchlist_data:
                watchlist_data.remove(name)
                render_watchlist()
                try:
                    page.client_storage.set("watchlist", watchlist_data)
                except:
                    pass

        # 关注页布局
        view_watch = ft.Column([
            ft.Container(content=ft.Row([new_user_input,
                                         ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color="blue", icon_size=35,
                                                       on_click=add_user)]), padding=10),
            ft.Container(content=watchlist_filter_input, padding=ft.padding.only(left=10, right=10, bottom=5)),  # 筛选框
            ft.Container(content=watchlist_col, expand=True)
        ], expand=True, visible=False)

        # 采集页布局
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
            view_search.visible = (idx == 0);
            view_watch.visible = (idx == 1);
            view_scrape.visible = (idx == 2)
            if idx == 1: render_watchlist()
            page.update()

        nav_bar = ft.NavigationBar(destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.SEARCH, label="搜索"),
            ft.NavigationBarDestination(icon=ft.Icons.STAR, label="关注"),
            ft.NavigationBarDestination(icon=ft.Icons.DATA_ARRAY, label="采集"),
        ], on_change=nav_change, height=60)

        page.add(ft.Column([view_search, view_watch, view_scrape], expand=True), nav_bar)

    except Exception as e:
        error_msg = traceback.format_exc()
        page.clean()
        page.add(ft.Column([
            ft.Text("❌ 程序启动错误", color="red", size=20),
            ft.Container(content=ft.Text(error_msg, color="white", size=10), bgcolor="black", padding=10, expand=True)
        ], expand=True))
        page.update()


if __name__ == "__main__":
    ft.app(target=main)
