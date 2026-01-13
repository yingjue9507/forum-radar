import flet as ft
import requests
import json
import time
import re
import datetime
import urllib3
import traceback # 引入这个库用于显示详细错误信息

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= 🔧 1. 基础配置 =================
API_URL = "https://com1.j3roe3vnnk4e92-udhle6.work/com/record.html"

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Referer": "https://qnxyl.2ldkc1pdg6fx5arh.work/",
    "Origin": "https://qnxyl.2ldkc1pdg6fx5arh.work"
}


# ================= 🔧 2. 爬虫逻辑 =================
def fetch_json_from_api(keyword, page, search_type="content"):
    # 构造请求参数
    params = {
        "callback": "jQuery_callback", "orderby": "saytime", "id": "67",
        "key_word": keyword if search_type == "user" else "",
        "key_msg_word": keyword if search_type == "content" else "",
        "classid": "0", "page": page,
        "_": int(time.time() * 1000)
    }
    try:
        # proxies=None 强制不走系统代理，防止 10054 报错
        response = requests.get(
            API_URL, headers=HEADERS, params=params, timeout=10,
            verify=False, proxies={"http": None, "https": None}
        )
        if response.status_code == 200:
            match = re.search(r'jQuery_callback\((.*)\)', response.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                if 'data' in data: return data
                if 'list' in data: return {'data': data['list'], 'total': 0, 'page_total': 1}
                return data
    except Exception as e:
        print(f"Err: {e}")
    return None


def format_timestamp(ts):
    try:
        if not ts: return ""
        dt = datetime.datetime.fromtimestamp(int(ts))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)


# ================= 📱 3. APP 界面逻辑 =================
def main(page: ft.Page):
    # 🛡️ 全局错误捕获开始：防止白屏
    try:
        # ⚠️⚠️⚠️ 关键修复：以下代码必须注释掉或删除 ⚠️⚠️⚠️
        # 手机系统会强制全屏，设置这些属性会导致权限错误崩溃
        # page.window.width = 390
        # page.window.height = 844
        # page.window.always_on_top = True 

        page.title = "论坛情报雷达"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0

        # === 存储逻辑 (适配安卓 client_storage) ===
        def get_watchlist():
            return page.client_storage.get("my_watchlist") or []

        def save_watchlist_to_storage(data):
            page.client_storage.set("my_watchlist", data)

        # === 界面组件初始化 ===
        search_type_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option("content", "搜内容"),
                ft.dropdown.Option("user", "搜用户"),
            ],
            value="content", width=110, text_size=13, height=45, content_padding=10,
            bgcolor=ft.Colors.WHITE, border_radius=8,
        )
        search_keyword = ft.TextField(hint_text="输入关键词...", height=45, text_size=14, expand=True,
                                    bgcolor=ft.Colors.WHITE, border_radius=8)
        search_list_view = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True)
        watchlist_view = ft.ListView(expand=True, spacing=10, padding=20)
        status_text = ft.Text("准备就绪", size=12, color=ft.Colors.WHITE70)
        progress_bar = ft.ProgressBar(width=400, color="amber", bgcolor="#263238", visible=False)

        # 底部导航
        nav_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationDestination(icon=ft.Icons.SEARCH, label="实时搜索"),
                ft.NavigationDestination(icon=ft.Icons.STAR, label="关注管理"),
            ],
            selected_index=0
        )

        view_search = ft.Container(visible=True, expand=True)
        view_watchlist = ft.Container(visible=False, expand=True)
        is_running = False

        # === 核心功能：添加结果卡片 ===
        def add_result_card(user, content, time_str):
            current_list = get_watchlist()
            is_vip = user in current_list

            # VIP 高亮样式
            card_bg = ft.Colors.AMBER_50 if is_vip else ft.Colors.WHITE
            border_color = ft.Colors.AMBER if is_vip else "#E0E0E0"
            user_color = ft.Colors.ORANGE_800 if is_vip else ft.Colors.BLACK87
            icon_name = ft.Icons.STAR if is_vip else ft.Icons.ACCOUNT_CIRCLE
            icon_color = ft.Colors.ORANGE if is_vip else ft.Colors.BLUE_GREY

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Icon(icon_name, size=20, color=icon_color),
                            ft.Text(user, weight=ft.FontWeight.BOLD, size=15, color=user_color),
                            ft.Container(content=ft.Text("已关注", size=10, color="white"), bgcolor=ft.Colors.ORANGE,
                                        padding=3, border_radius=4, visible=is_vip)
                        ]),
                        ft.Text(time_str, size=11, color=ft.Colors.GREY_600),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=1, color=ft.Colors.TRANSPARENT),
                    ft.Text(content, size=14, color=ft.Colors.BLACK87, selectable=True),
                ]),
                padding=15, border=ft.border.all(1 if not is_vip else 2, border_color), border_radius=10, bgcolor=card_bg,
                margin=ft.margin.only(bottom=10, left=10, right=10),
                shadow=ft.BoxShadow(spread_radius=1, blur_radius=3, color=ft.Colors.BLUE_GREY_50, offset=ft.Offset(0, 1))
            )
            search_list_view.controls.append(card)

        # === 核心功能：开始搜索 ===
        def start_search(e=None):
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
            progress_bar.visible = True
            mode_text = "用户" if mode == "user" else "内容"
            status_text.value = f"正在搜索{mode_text}: {keyword} ..."
            page.update()

            try:
                current_page = 1
                total_pages = 1
                while current_page <= total_pages:
                    if not is_running: break
                    status_text.value = f"正在请求第 {current_page} 页..."
                    page.update()

                    json_data = fetch_json_from_api(keyword, current_page, search_type=mode)
                    if not json_data: break

                    if current_page == 1:
                        total_pages = int(json_data.get('page_total', 1))
                        total_records = int(json_data.get('total', 0))
                        status_text.value = f"找到 {total_records} 条{mode_text}数据，开始加载..."

                    items = json_data.get('data', [])
                    if not items: break

                    # 强制按时间倒序排列 (最新的在最前)
                    try:
                        items.sort(key=lambda x: int(x.get('saytime', 0) or x.get('time', 0)), reverse=True)
                    except:
                        pass

                    for item in items:
                        user = item.get('nickname') or item.get('username') or '未知'
                        raw = item.get('saycontent') or item.get('content') or ''
                        clean = re.sub(r'<[^>]+>', '', str(raw)).strip()
                        ts = item.get('saytime') or item.get('time') or 0
                        add_result_card(user, clean, format_timestamp(ts))

                    page.update()
                    current_page += 1
                    time.sleep(0.2)
                status_text.value = f"✅ 加载完成"
            except Exception as err:
                status_text.value = f"❌ 错误: {err}"
            finally:
                is_running = False
                btn_search.text = "搜索"
                btn_search.bgcolor = ft.Colors.BLUE_600
                progress_bar.visible = False
                page.update()

        def stop_search(e):
            nonlocal is_running
            if is_running:
                is_running = False
                status_text.value = "🛑 已手动停止"
                page.update()
            else:
                start_search(e)

        btn_search = ft.ElevatedButton("搜索", on_click=stop_search, color="white", bgcolor=ft.Colors.BLUE_600)

        # === 关注列表逻辑 ===
        new_user_input = ft.TextField(hint_text="输入大神昵称", expand=True, height=40, content_padding=10)

        def jump_to_user_search(user_name):
            """跳转并自动搜索用户"""
            nav_bar.selected_index = 0
            view_search.visible = True
            view_watchlist.visible = False
            search_type_dropdown.value = "user"
            search_keyword.value = user_name
            page.update()
            start_search()

        def render_watchlist():
            """渲染关注列表"""
            watchlist_view.controls.clear()
            current_list = get_watchlist()
            for user in current_list:
                watchlist_view.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Row([ft.Icon(ft.Icons.STAR, color=ft.Colors.AMBER), ft.Text(user, size=16, weight="bold")]),
                            ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.GREY_400, tooltip="取消关注",
                                        on_click=lambda e, u=user: remove_user(u))
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=15, border=ft.border.all(1, "#EEEEEE"), border_radius=8, bgcolor=ft.Colors.WHITE, ink=True,
                        # 点击整个卡片跳转
                        on_click=lambda e, u=user: jump_to_user_search(u)
                    )
                )
            page.update()

        def add_user(e):
            name = new_user_input.value.strip()
            current_list = get_watchlist()
            if name and name not in current_list:
                current_list.append(name)
                save_watchlist_to_storage(current_list)
                new_user_input.value = ""
                render_watchlist()

        def remove_user(name):
            current_list = get_watchlist()
            if name in current_list:
                current_list.remove(name)
                save_watchlist_to_storage(current_list)
                render_watchlist()

        # === 布局组装 ===
        view_search.content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("🔍 论坛情报雷达", size=20, weight="bold", color="white"),
                    ft.Row([search_type_dropdown, search_keyword, btn_search], spacing=5),
                    status_text, progress_bar
                ]), padding=20, bgcolor=ft.Colors.BLUE_800,
                border_radius=ft.border_radius.only(bottom_left=20, bottom_right=20)
            ), search_list_view
        ])

        view_watchlist.content = ft.Column([
            ft.Container(
                content=ft.Row([new_user_input, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.BLUE, icon_size=40,
                                                            on_click=add_user)]),
                padding=20, bgcolor=ft.Colors.GREY_100
            ), watchlist_view
        ])

        def nav_change(e):
            index = e.control.selected_index
            view_search.visible = (index == 0)
            view_watchlist.visible = (index == 1)
            if index == 1: render_watchlist()
            page.update()

        nav_bar.on_change = nav_change
        render_watchlist()
        page.add(ft.Column([view_search, view_watchlist], expand=True), nav_bar)

    # 🛡️ 错误捕获处理
    except Exception as e:
        error_info = traceback.format_exc()
        page.clean()
        page.add(
            ft.Column([
                ft.Text("⚠️ 启动发生严重错误", size=24, color="red", weight="bold"),
                ft.Container(
                    content=ft.Text(error_info, color="yellow", size=12, selectable=True),
                    bgcolor="black", padding=10, border_radius=5
                )
            ], scroll=ft.ScrollMode.ALWAYS)
        )

if __name__ == "__main__":
    ft.app(target=main)
