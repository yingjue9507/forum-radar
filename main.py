import flet as ft
import requests
import json
import time
import re
import datetime
import urllib3
import os
import csv
from bs4 import BeautifulSoup

# ================= 🔧 0. 全局配置 =================

CSV_FILENAME = "Lotto_Monitor_Data.csv"
WATCHLIST_FILENAME = "radar_watchlist_v2.json"

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. 论坛搜索 API ---
FORUM_API_URL = "https://com1.j3roe3vnnk4e92-udhle6.work/com/record.html"

SEARCH_HEADERS = {
    "Host": "com1.j3roe3vnnk4e92-udhle6.work",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Referer": "https://qnxyl.2ldkc1pdg6fx5arh.work/",
    "Origin": "https://qnxyl.2ldkc1pdg6fx5arh.work",
    "Accept": "*/*",
    "Sec-Ch-Ua": '"Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Dest": "script"
}

# --- 2. 采集目标配置 ---
TARGET_URL = "https://160.124.142.10:50415/index.html"

SCRAPE_HEADERS = {
    "Host": "160.124.142.10:50415",
    "Sec-Ch-Ua": '"Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "iframe",
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


def get_period_number(period_str):
    try:
        match = re.search(r'(\d+)', str(period_str))
        return int(match.group(1)) if match else 0
    except:
        return 0


# ================= 🌐 2. 核心逻辑模块 =================

# --- 2.1 论坛搜索 ---
def fetch_json_infinite(keyword, page_num, search_type="content"):
    callback_name = f"jQuery{int(time.time() * 1000)}_{int(time.time() * 1000)}"
    params = {
        "callback": callback_name,
        "orderby": "plid",
        "id": "67",
        "key_word": "",
        "key_msg_word": "",
        "page": str(page_num)
    }

    if search_type == "user":
        params["key_word"] = keyword.strip()
    else:
        params["key_msg_word"] = keyword.strip()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(FORUM_API_URL, headers=SEARCH_HEADERS, params=params, timeout=10, verify=False)
            if response.status_code == 200:
                match = re.search(r'jQuery.*?\((\{.*\})\)', response.text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    result_list = data.get('data') or data.get('list')
                    return result_list if result_list is not None else []
        except Exception as e:
            print(f"请求异常 (Page {page_num}): {e}")
            time.sleep(1)
    return None


# --- 2.2 协议抓取 ---
def fetch_and_parse_data():
    all_data = []
    logs = []
    try:
        logs.append(f"正在连接: {TARGET_URL} ...")
        response = requests.get(
            TARGET_URL, headers=SCRAPE_HEADERS, verify=False, timeout=15,
            proxies={"http": None, "https": None}
        )
        response.encoding = 'utf-8'
        logs.append(f"服务器响应: {response.status_code}")

        if response.status_code != 200:
            return [], "\n".join(logs) + f"\n❌ 状态码异常: {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')
        all_lis = soup.find_all("li")
        logs.append(f"🔍 页面共发现 {len(all_lis)} 行数据，开始筛选...")

        count_valid = 0
        processed_hashes = set()

        for li in all_lis:
            text = li.get_text(strip=True)
            if not text: continue

            p_match = re.search(r'(\d+)\s*[期:：]', text)
            if not p_match: continue

            period_num = p_match.group(1)
            period = f"{period_num}期"

            section_name = "其他版块"
            try:
                parent_ul = li.find_parent("ul")
                if parent_ul:
                    prev = parent_ul.find_previous(class_=re.compile(r'(tit|head|caption|pb-tit|ptyx-tit)'))
                    if prev: section_name = prev.get_text(strip=True)
            except:
                pass

            if section_name == "其他版块":
                try:
                    grand_parent = li.find_parent("div", class_="bg") or li.find_parent("div", class_="ptyx")
                    if grand_parent:
                        tit_div = grand_parent.find(class_=re.compile(r'tit|head'))
                        if tit_div: section_name = tit_div.get_text(strip=True)
                except:
                    pass

            content = ""
            c_match = re.search(r'(【.*?】)', text)
            if c_match:
                content = c_match.group(1)
            else:
                parts = re.split(r'[:：]', text, 1)
                if len(parts) > 1: content = parts[1].strip()

            status = ""
            if "准" in text:
                status = "准"
            elif "错" in text:
                status = "错"
            elif "更新" in text:
                status = "更新中"

            row_hash = f"{section_name}_{period}_{content}"
            if row_hash in processed_hashes: continue
            processed_hashes.add(row_hash)

            all_data.append([section_name, period, content, status])
            count_valid += 1

        logs.append(f"✅ 成功提取 {count_valid} 条记录")

    except Exception as e:
        return [], f"❌ 解析错误: {str(e)}"
    return all_data, "\n".join(logs)


# --- 2.3 CSV 存储 (原有采集用) ---
def merge_and_save_csv(new_data_list):
    data_map = {}
    if os.path.exists(CSV_FILENAME):
        try:
            with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    for row in reader:
                        if len(row) >= 4:
                            key = f"{row[0]}_{row[1]}"
                            data_map[key] = row
        except:
            pass

    added = 0
    updated = 0
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for item in new_data_list:
        sec_name, period, content, status = item[0], item[1], item[2], item[3]
        unique_key = f"{sec_name}_{period}"
        new_row = [sec_name, period, content, status, now_str]

        if unique_key in data_map:
            old_row = data_map[unique_key]
            if old_row[2] != content or old_row[3] != status:
                data_map[unique_key] = new_row
                updated += 1
        else:
            data_map[unique_key] = new_row
            added += 1

    final_rows = list(data_map.values())
    final_rows.sort(key=lambda x: (x[0], -get_period_number(x[1])))

    try:
        with open(CSV_FILENAME, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['版块名称', '期数', '内容', '状态', '更新时间'])
            writer.writerows(final_rows)
        return True, f"新增 {added} 条，更新 {updated} 条"
    except Exception as e:
        return False, f"保存失败: {str(e)}"


# --- 2.4 关注列表 ---
def load_watchlist():
    if os.path.exists(WATCHLIST_FILENAME):
        try:
            with open(WATCHLIST_FILENAME, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []


def save_watchlist(data):
    try:
        with open(WATCHLIST_FILENAME, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


# ================= 📱 3. 主界面 APP =================

def main(page: ft.Page):
    page.title = "情报雷达 v9.3 (导出增强版)"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    watchlist_data = load_watchlist()
    seen_ids = set()
    current_search_id = [0]

    # 🌟 新增：用于缓存搜索结果数据以便导出
    search_results_data = []

    # ================= 页面 1: 搜索 =================
    search_type_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option("content", "搜内容"), ft.dropdown.Option("user", "搜用户")],
        value="content", width=100, height=40, content_padding=10, bgcolor="white", text_size=13
    )
    search_keyword = ft.TextField(hint_text="输入关键词", height=40, expand=True, content_padding=10, bgcolor="white")
    search_list_view = ft.ListView(expand=True, spacing=0, padding=10)
    status_text = ft.Text("准备就绪", size=12, color="white70")
    result_count = ft.Text("", size=12, color="amber")
    progress_bar = ft.ProgressBar(visible=False, color="amber", bgcolor="#263238")

    def run_search_logic(e=None):
        my_session_id = current_search_id[0] + 1
        current_search_id[0] = my_session_id

        keyword = search_keyword.value
        if not keyword:
            page.show_snack_bar(ft.SnackBar(ft.Text("❌ 请输入关键词")))
            return

        btn_search.text = "停止"
        btn_search.bgcolor = ft.Colors.RED_400
        btn_export.visible = False  # 搜索时隐藏导出按钮，防止数据不完整导出

        search_list_view.controls.clear()
        seen_ids.clear()
        search_results_data.clear()  # 清空旧数据

        progress_bar.visible = True
        status_text.value = "🔍 搜索中..."
        result_count.value = ""
        page.update()

        total_loaded = 0
        current_page = 1
        empty_retry_count = 0

        try:
            while True:
                if current_search_id[0] != my_session_id: return

                status_text.value = f"正在加载第 {current_page} 页..."
                page.update()

                items_list = fetch_json_infinite(keyword, current_page, search_type_dropdown.value)

                if items_list is None:
                    status_text.value = "⚠️ 网络请求失败，正在重试..."
                    time.sleep(1)
                    continue

                if len(items_list) == 0:
                    empty_retry_count += 1
                    if empty_retry_count >= 2:
                        status_text.value = f"✅ 所有数据加载完毕"
                        break
                    else:
                        current_page += 1
                        time.sleep(1)
                        continue
                else:
                    empty_retry_count = 0

                for item in items_list:
                    rec_id = str(item.get('id') or '')
                    if rec_id in seen_ids: continue
                    seen_ids.add(rec_id)

                    user = item.get('nickname') or item.get('username') or '未知'
                    raw = item.get('saycontent') or item.get('content') or ''
                    clean = re.sub(r'<[^>]+>', '', str(raw)).strip()
                    ts = item.get('saytime') or item.get('time')
                    ts_fmt = format_timestamp(ts)
                    is_vip = user in watchlist_data

                    # 🌟 核心：将数据存入缓存列表
                    search_results_data.append([rec_id, user, ts_fmt, clean])

                    card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Icon(ft.Icons.VERIFIED if is_vip else ft.Icons.PERSON, size=16,
                                            color="orange" if is_vip else "grey"),
                                    ft.Text(user, weight="bold", color="orange" if is_vip else "black"),
                                    ft.Text(f"#{rec_id}", size=10, color="grey")
                                ]),
                                ft.Text(ts_fmt, size=11, color="grey")
                            ], alignment="spaceBetween"),
                            ft.Container(height=5),
                            ft.Text(clean, size=14, selectable=True),
                        ]),
                        padding=10, border_radius=8, bgcolor="yellow.50" if is_vip else "white",
                        border=ft.border.all(1, "orange" if is_vip else "#eeeeee"),
                        margin=ft.margin.only(bottom=5)
                    )
                    search_list_view.controls.append(card)
                    total_loaded += 1

                result_count.value = f"已找到: {total_loaded} 条 (第 {current_page} 页)"
                if total_loaded % 5 == 0: page.update()

                current_page += 1

                # 防封延迟
                status_text.value = f"⏳ 防封冷却中... (等待 3 秒)"
                page.update()
                time.sleep(2)

        except Exception as e:
            status_text.value = f"Err: {e}"
            print(f"Error logic: {e}")
        finally:
            if current_search_id[0] == my_session_id:
                btn_search.text = "搜索"
                btn_search.bgcolor = ft.Colors.BLUE_600
                progress_bar.visible = False
                status_text.value = f"✅ 完成，共抓取 {total_loaded} 条"

                # 🌟 搜索完成后，如果有数据，显示导出按钮
                if len(search_results_data) > 0:
                    btn_export.visible = True
                    btn_export.text = f"导出CSV ({len(search_results_data)}条)"

                page.update()

    def stop_search(e):
        current_search_id[0] += 1
        btn_search.text = "搜索"
        btn_search.bgcolor = ft.Colors.BLUE_600
        progress_bar.visible = False
        status_text.value = "🛑 已停止"
        # 即使停止，如果有已抓取的数据，也允许导出
        if len(search_results_data) > 0:
            btn_export.visible = True
            btn_export.text = f"导出CSV ({len(search_results_data)}条)"
        page.update()

    def start_search_click(e):
        if btn_search.text == "停止":
            stop_search(e)
        else:
            run_search_logic(e)

    # 🌟 新增：导出搜索结果到 CSV
    def export_search_data(e):
        if not search_results_data:
            page.show_snack_bar(ft.SnackBar(ft.Text("❌ 没有可导出的数据")))
            return

        # 生成带时间戳的文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SearchResult_{timestamp}.csv"

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "用户", "时间", "内容"])  # 表头
                writer.writerows(search_results_data)  # 数据内容

            page.show_snack_bar(ft.SnackBar(ft.Text(f"✅ 导出成功: {filename}"), bgcolor="green"))
        except Exception as ex:
            page.show_snack_bar(ft.SnackBar(ft.Text(f"❌ 导出失败: {str(ex)}"), bgcolor="red"))

    btn_search = ft.ElevatedButton("搜索", on_click=start_search_click, bgcolor=ft.Colors.BLUE_600, color="white")

    # 🌟 新增：导出按钮（初始隐藏）
    btn_export = ft.ElevatedButton("导出CSV", on_click=export_search_data, bgcolor=ft.Colors.GREEN_600, color="white",
                                   visible=False)

    view_search = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("🔍 论坛情报雷达", size=20, weight="bold", color="white"),
                    ft.Row([search_type_dropdown, search_keyword, btn_search, btn_export]),  # 🌟 将导出按钮加入布局
                    ft.Row([status_text, result_count], alignment="spaceBetween"),
                    progress_bar
                ]),
                padding=15, bgcolor=ft.Colors.BLUE_800
            ),
            search_list_view
        ]),
        visible=True
    )

    # ================= 页面 2: 关注管理 =================
    new_user_input = ft.TextField(hint_text="输入昵称", expand=True, height=40)
    watchlist_col = ft.ListView(expand=True, spacing=10, padding=20)

    def render_watchlist():
        watchlist_col.controls.clear()
        for u in watchlist_data:
            watchlist_col.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Row([ft.Icon(ft.Icons.STAR, color="amber"), ft.Text(u, size=16, weight="bold")]),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red",
                                      on_click=lambda e, user=u: remove_user(user))
                    ], alignment="spaceBetween"),
                    padding=15, bgcolor="white", border=ft.border.all(1, "#eee"), border_radius=8,
                    on_click=lambda e, user=u: jump_to_search(user)
                )
            )
        page.update()

    def jump_to_search(name):
        nav_bar.selected_index = 0
        view_search.visible = True
        view_watch.visible = False
        view_scrape.visible = False
        search_type_dropdown.value = "user"
        search_keyword.value = name.strip()
        page.update()
        run_search_logic()

    def add_user(e):
        name = new_user_input.value.strip()
        if name and name not in watchlist_data:
            watchlist_data.append(name)
            save_watchlist(watchlist_data)
            new_user_input.value = ""
            render_watchlist()

    def remove_user(name):
        if name in watchlist_data:
            watchlist_data.remove(name)
            save_watchlist(watchlist_data)
            render_watchlist()

    view_watch = ft.Container(
        content=ft.Column([
            ft.Container(content=ft.Row([new_user_input,
                                         ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color="blue", icon_size=40,
                                                       on_click=add_user)]), padding=20),
            ft.Text("  点击卡片可快速搜索", size=12, color="grey"),
            watchlist_col
        ]),
        visible=False
    )

    # ================= 页面 3: 安卓协议采集 =================
    scrape_status = ft.Text("准备就绪", color="grey")
    log_box = ft.ListView(height=100, spacing=2, padding=10, auto_scroll=True)

    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("版块")),
            ft.DataColumn(ft.Text("内容")),
            ft.DataColumn(ft.Text("状态")),
            ft.DataColumn(ft.Text("删")),
        ],
        rows=[],
        column_spacing=10,
        heading_row_color=ft.Colors.BLUE_50,
        data_row_min_height=40,
    )

    def add_log(msg, color="black"):
        log_box.controls.append(ft.Text(f"[{datetime.datetime.now().strftime('%H:%M')}] {msg}", color=color, size=12))
        page.update()

    def delete_row(sec_name, period):
        if not os.path.exists(CSV_FILENAME): return
        new_rows = []
        deleted = False
        try:
            with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 2 and row[0] == sec_name and row[1] == period:
                        deleted = True
                        continue
                    new_rows.append(row)

            if deleted:
                with open(CSV_FILENAME, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if header: writer.writerow(header)
                    writer.writerows(new_rows)
                page.show_snack_bar(ft.SnackBar(ft.Text(f"🗑️ 已删除 {period}"), duration=1000))
                load_table_data()
        except:
            pass

    def load_table_data():
        if not os.path.exists(CSV_FILENAME): return
        ft_rows = []
        try:
            with open(CSV_FILENAME, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 4:
                        color = ft.Colors.GREEN if "准" in row[3] else (
                            ft.Colors.RED if "错" in row[3] else ft.Colors.BLACK)
                        ft_rows.append(ft.DataRow(cells=[
                            ft.DataCell(ft.Column([
                                ft.Text(row[0], size=10, weight="bold"),
                                ft.Text(row[1], size=10, color="grey")
                            ], alignment="center", spacing=0)),
                            ft.DataCell(ft.Text(row[2], size=12, width=120, no_wrap=False)),
                            ft.DataCell(ft.Text(row[3], size=12, color=color)),
                            ft.DataCell(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", icon_size=20,
                                                      on_click=lambda e, s=row[0], p=row[1]: delete_row(s, p))),
                        ]))
            data_table.rows = ft_rows
            page.update()
        except:
            pass

    def start_scrape(e):
        btn_scrape.disabled = True
        btn_scrape.text = "抓取中..."
        scrape_status.value = "🚀 正在请求..."
        scrape_status.color = ft.Colors.BLUE
        log_box.controls.clear()
        page.update()

        data, log_str = fetch_and_parse_data()
        for line in log_str.split('\n'):
            if line: add_log(line, "grey")

        if data:
            success, msg = merge_and_save_csv(data)
            if success:
                scrape_status.value = "✅ 成功"
                scrape_status.color = ft.Colors.GREEN
                add_log(msg, "green")
                load_table_data()
            else:
                scrape_status.value = "❌ 失败"
                add_log(msg, "red")
        else:
            scrape_status.value = "❌ 无数据"
            scrape_status.color = ft.Colors.RED

        btn_scrape.disabled = False
        btn_scrape.text = "一键采集"
        page.update()

    load_table_data()
    btn_scrape = ft.ElevatedButton("一键采集", on_click=start_scrape, bgcolor=ft.Colors.BLUE_600, color="white",
                                   width=150)

    view_scrape = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("📊 采集与归档 (v9.3)", size=20, weight="bold", color="white"),
                    ft.Text(f"Target: {TARGET_URL}", size=10, color="white70", no_wrap=True),
                ]),
                padding=15, bgcolor=ft.Colors.BLUE_800
            ),
            ft.Container(
                content=ft.Row([btn_scrape, scrape_status], alignment="spaceBetween"),
                padding=10
            ),
            ft.Container(
                content=log_box,
                height=100, border=ft.border.all(1, "#eee"), border_radius=5, margin=10
            ),
            ft.Container(
                content=ft.ListView(
                    controls=[
                        ft.Row([data_table], scroll=ft.ScrollMode.AUTO)
                    ],
                    expand=True, spacing=10
                ),
                expand=True, padding=5
            )
        ]),
        visible=False,
        expand=True
    )

    def nav_change(e):
        idx = e.control.selected_index
        view_search.visible = (idx == 0)
        view_watch.visible = (idx == 1)
        view_scrape.visible = (idx == 2)
        if idx == 1: render_watchlist()
        if idx == 2: load_table_data()
        page.update()

    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.SEARCH, label="搜索"),
            ft.NavigationBarDestination(icon=ft.Icons.STAR, label="关注"),
            ft.NavigationBarDestination(icon=ft.Icons.DATA_ARRAY, label="采集"),
        ],
        on_change=nav_change
    )

    page.add(ft.Column([view_search, view_watch, view_scrape], expand=True), nav_bar)


if __name__ == "__main__":
    ft.app(target=main)
