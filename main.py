import flet as ft
import requests
import json
import time
import re
import datetime
import urllib3
import traceback
import os

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= 🔧 1. 核心配置与网络层 =================
API_URL = "https://com1.j3roe3vnnk4e92-udhle6.work/com/record.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Referer": "https://qnxyl.2ldkc1pdg6fx5arh.work/",
    "Origin": "https://qnxyl.2ldkc1pdg6fx5arh.work",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "script",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}


def fetch_json_infinite(keyword, last_id="", search_type="content"):
    """网络请求：锁定Page=1，利用lastid无限滚动"""
    params = {
        "callback": "jQuery_callback",
        "orderby": "0",
        "id": "67",
        "page": "1",
        "lastid": last_id,
        "last_top": "0",
        "key_word": keyword if search_type == "user" else "",
        "key_msg_word": keyword if search_type == "content" else "",
        "classid": "0",
        "id2": "",
        "_": int(time.time() * 1000)
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(
                API_URL, headers=HEADERS, params=params, timeout=10,
                verify=False, proxies={"http": None, "https": None}
            )

            if response.status_code == 200:
                text = response.text
                match = re.search(r'jQuery.*?\((\{.*\})\)', text, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    try:
                        data = json.loads(json_str)
                    except:
                        return None

                    if 'data' in data: return data['data']
                    if 'list' in data: return data['list']
                    return []
        except Exception as e:
            time.sleep(1)
    return None


def format_timestamp(ts):
    try:
        if not ts: return ""
        ts_int = int(ts)
        if ts_int > 10000000000: ts_int = ts_int / 1000
        dt = datetime.datetime.fromtimestamp(ts_int)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)


# ================= 💾 2. 永久存储模块 =================
DATA_FILENAME = "radar_watchlist_v2.json"


def load_watchlist_from_file():
    try:
        if os.path.exists(DATA_FILENAME):
            with open(DATA_FILENAME, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list): return data
    except:
        pass
    return []


def save_watchlist_to_file(data):
    try:
        with open(DATA_FILENAME, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


# ================= 📱 3. APP 界面逻辑 =================
def main(page: ft.Page):
    try:
        page.title = "论坛情报雷达 v2.4 (完全体)"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0

        watchlist_data = load_watchlist_from_file()

        # === 控件定义 ===
        search_type_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option("content", "搜内容"),
                ft.dropdown.Option("user", "搜用户"),
            ],
            value="content", width=100, text_size=13, height=40, content_padding=10,
            bgcolor=ft.Colors.WHITE, border_radius=8,
        )

        search_keyword = ft.TextField(
            hint_text="输入关键词",
            height=40, text_size=14, expand=True,
            bgcolor=ft.Colors.WHITE, border_radius=8,
            content_padding=10
        )

        search_list_view = ft.ListView(expand=True, spacing=0, padding=10)
        status_text = ft.Text("准备就绪", size=12, color=ft.Colors.WHITE70)
        result_count_text = ft.Text("", size=12, color=ft.Colors.AMBER)
        progress_bar = ft.ProgressBar(width=None, color="amber", bgcolor="#263238", visible=False)

        nav_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.SEARCH, label="搜索"),
                ft.NavigationBarDestination(icon=ft.Icons.STAR, label="关注管理"),
            ],
            selected_index=0,
            height=60
        )

        view_search = ft.Container(visible=True, expand=True)
        view_watchlist = ft.Container(visible=False, expand=True)
        is_running = False
        seen_ids = set()

        # === 核心逻辑1：执行搜索 ===
        def run_search_logic(e=None):
            nonlocal is_running
            if is_running: return

            keyword = search_keyword.value
            mode = search_type_dropdown.value

            if not keyword:
                page.snack_bar = ft.SnackBar(ft.Text("❌ 请先输入关键词"))
                page.snack_bar.open = True
                page.update()
                return

            is_running = True
            btn_search.text = "停止"
            btn_search.bgcolor = ft.Colors.RED_400

            search_list_view.controls.clear()
            seen_ids.clear()

            progress_bar.visible = True
            result_count_text.value = ""
            status_text.value = "开始搜索..."
            page.update()

            total_loaded = 0
            batch_count = 1
            last_id = ""

            try:
                empty_count = 0
                while True:
                    if not is_running: break

                    status_text.value = f"加载第 {batch_count} 批 (LastID: {last_id})..."
                    page.update()

                    items_list = fetch_json_infinite(keyword, last_id, mode)

                    if items_list is None:
                        status_text.value = "网络请求失败，停止。"
                        break

                    if len(items_list) == 0:
                        empty_count += 1
                        if empty_count >= 2:
                            status_text.value = "✅ 数据源已枯竭"
                            break
                        time.sleep(0.5)
                        continue
                    else:
                        empty_count = 0

                    new_items_count = 0
                    for item in items_list:
                        rec_id = str(item.get('id') or '')
                        if rec_id in seen_ids: continue
                        seen_ids.add(rec_id)

                        user = item.get('nickname') or item.get('username') or '未知'
                        raw = item.get('saycontent') or item.get('content') or ''
                        clean = re.sub(r'<[^>]+>', '', str(raw)).strip()
                        ts = item.get('saytime') or item.get('time') or 0

                        # 渲染卡片
                        is_vip = user in watchlist_data
                        card_bg = ft.Colors.YELLOW_50 if is_vip else ft.Colors.WHITE
                        border_color = ft.Colors.ORANGE if is_vip else "#EEEEEE"

                        card = ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Row([
                                        ft.Icon(ft.Icons.VERIFIED_USER if is_vip else ft.Icons.ACCOUNT_CIRCLE,
                                                size=16, color=ft.Colors.ORANGE if is_vip else ft.Colors.GREY),
                                        ft.Text(user, weight=ft.FontWeight.BOLD, size=14,
                                                color=ft.Colors.ORANGE_900 if is_vip else ft.Colors.BLACK87),
                                    ]),
                                    ft.Text(format_timestamp(ts), size=11, color=ft.Colors.GREY),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Container(height=5),
                                ft.Text(clean, size=14, color=ft.Colors.BLACK87, selectable=True),
                                ft.Container(height=5),
                                ft.Row([ft.Text(f"ID: {rec_id}", size=10, color=ft.Colors.GREY_300)],
                                       alignment=ft.MainAxisAlignment.END)
                            ]),
                            padding=12, border=ft.border.all(1, border_color), border_radius=8, bgcolor=card_bg,
                            margin=ft.margin.only(bottom=8)
                        )
                        search_list_view.controls.append(card)

                        total_loaded += 1
                        new_items_count += 1
                        last_id = rec_id

                    result_count_text.value = f"已找到: {total_loaded} 条"
                    if total_loaded % 10 == 0: page.update()

                    if new_items_count == 0 and len(items_list) > 0:
                        force_next_id = str(items_list[-1].get('id'))
                        if force_next_id == last_id: break
                        last_id = force_next_id

                    batch_count += 1
                    time.sleep(0.3)

            except Exception as err:
                status_text.value = f"Error: {str(err)}"
                traceback.print_exc()
            finally:
                is_running = False
                btn_search.text = "搜索"
                btn_search.bgcolor = ft.Colors.BLUE_600
                progress_bar.visible = False
                status_text.value = f"✅ 完成，共 {total_loaded} 条"
                page.update()

        def stop_search(e):
            nonlocal is_running
            if is_running:
                is_running = False
                status_text.value = "🛑 已停止"
                page.update()
            else:
                run_search_logic(e)

        btn_search = ft.ElevatedButton("搜索", on_click=stop_search, color="white", bgcolor=ft.Colors.BLUE_600)

        # === 核心逻辑2：跳转搜索 ===
        def jump_to_user_search(user_name):
            """跳转并搜索指定用户"""
            # 1. 切换界面
            nav_bar.selected_index = 0
            view_search.visible = True
            view_watchlist.visible = False

            # 2. 填充搜索参数
            search_type_dropdown.value = "user"  # 切换到搜用户模式
            search_keyword.value = user_name  # 填入名字

            # 3. 刷新并触发搜索
            page.update()
            # 如果当前没有在运行，则开始搜索
            if not is_running:
                run_search_logic()

        # === 关注列表渲染 ===
        watchlist_view = ft.ListView(expand=True, spacing=10, padding=20)
        new_user_input = ft.TextField(hint_text="输入昵称添加", expand=True, height=40, content_padding=10)

        def render_watchlist():
            watchlist_view.controls.clear()
            if not watchlist_data:
                watchlist_view.controls.append(ft.Text("暂无关注，去添加几个吧！", color="grey"))

            for user in watchlist_data:
                # 这是一个整体可点击的卡片
                watchlist_view.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Row([
                                ft.Icon(ft.Icons.STAR, color=ft.Colors.AMBER),
                                ft.Text(user, size=16, weight="bold")
                            ]),
                            # 删除按钮如果不希望触发跳转，可以保留，但因为在Container里，
                            # 点击删除也可能触发Container点击，最好把删除做成独立点击事件
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red",
                                          on_click=lambda e, u=user: remove_user(u))
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                        padding=15,
                        bgcolor="white",
                        border_radius=8,
                        border=ft.border.all(1, "#eeeeee"),
                        ink=True,  # 点击水波纹效果
                        # 🔥 关键：绑定点击事件到跳转函数
                        on_click=lambda e, u=user: jump_to_user_search(u)
                    )
                )
            page.update()

        def add_user(e):
            name = new_user_input.value.strip()
            if name and name not in watchlist_data:
                watchlist_data.append(name)
                save_watchlist_to_file(watchlist_data)
                new_user_input.value = ""
                render_watchlist()

        def remove_user(name):
            if name in watchlist_data:
                watchlist_data.remove(name)
                save_watchlist_to_file(watchlist_data)
                render_watchlist()

        # === 布局组装 ===
        view_search.content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("🔍 论坛情报雷达 v2.4", size=20, weight="bold", color="white"),
                    ft.Row([search_type_dropdown, search_keyword, btn_search], spacing=5),
                    ft.Row([status_text, result_count_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    progress_bar
                ]),
                padding=15, bgcolor=ft.Colors.BLUE_800,
                border_radius=ft.border_radius.only(bottom_left=15, bottom_right=15)
            ),
            search_list_view
        ], spacing=0)

        view_watchlist.content = ft.Column([
            ft.Container(content=ft.Row([new_user_input,
                                         ft.IconButton(ft.Icons.ADD_CIRCLE, icon_size=40, icon_color=ft.Colors.BLUE,
                                                       on_click=add_user)]), padding=20),
            ft.Text("  点击卡片可快速搜索", size=12, color="grey"),
            watchlist_view
        ])

        def nav_change(e):
            idx = e.control.selected_index
            view_search.visible = (idx == 0)
            view_watchlist.visible = (idx == 1)
            if idx == 1: render_watchlist()
            page.update()

        nav_bar.on_change = nav_change

        render_watchlist()
        page.add(ft.Column([view_search, view_watchlist], expand=True), nav_bar)

    except Exception as e:
        page.add(ft.Text(f"Error: {e}"))


if __name__ == "__main__":
    ft.app(target=main)
