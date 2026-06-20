"""
SmartLift Mobile App (Kivy)
----------------------------
Connects to the SmartLift Flask backend and displays:
  - Elevator status (occupants, weight, overloaded warning)
  - Waiting count for each floor

Auto-refreshes every few seconds. No manual refresh button needed.

The server IP is no longer hardcoded — on first launch you'll see a
small "Connect" screen where you type in your Flask server's IP
address. It's saved on the device (via Kivy's JsonStore) so you only
need to enter it once, unless you want to change it later.

Run this on your computer with:
    pip install kivy requests
    python main.py
"""

import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.storage.jsonstore import JsonStore
from kivy.app import App as KivyApp
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_PORT = 5000
REFRESH_INTERVAL_SECONDS = 1    # how often the app polls the server
REQUEST_TIMEOUT_SECONDS = 4     # how long to wait before giving up on a request
CONNECT_TIMEOUT_SECONDS = 6     # slightly longer timeout for the initial connect test

FLOOR_NUMBERS = [1, 2, 3]

# ---------------------------------------------------------------------------
# Colors — blue and white theme
# ---------------------------------------------------------------------------

COLOR_WHITE = (1, 1, 1, 1)
COLOR_BG = (0.95, 0.96, 0.98, 1)        # very light blue-gray background
COLOR_BLUE = (0.09, 0.37, 0.65, 1)       # primary blue (titles, badges)
COLOR_BLUE_LIGHT = (0.90, 0.95, 1, 1)    # light blue fill (badges, info boxes)
COLOR_TEXT_DARK = (0.13, 0.13, 0.13, 1)
COLOR_TEXT_GRAY = (0.45, 0.45, 0.45, 1)
COLOR_GREEN = (0.18, 0.55, 0.25, 1)
COLOR_RED = (0.75, 0.18, 0.18, 1)
COLOR_RED_LIGHT = (0.99, 0.92, 0.92, 1)
COLOR_AMBER = (0.70, 0.50, 0.05, 1)
COLOR_AMBER_LIGHT = (1, 0.97, 0.88, 1)


# ---------------------------------------------------------------------------
# Persisted settings (saved on-device so the IP doesn't need retyping
# every time the app opens)
# ---------------------------------------------------------------------------

def _store_path():
    """Puts the settings file in the app's writable data directory on
    Android, or next to the script when running on desktop."""
    try:
        app = KivyApp.get_running_app()
        if app is not None and app.user_data_dir:
            return os.path.join(app.user_data_dir, "smartlift_settings.json")
    except Exception:
        pass
    return "smartlift_settings.json"


def load_saved_ip():
    try:
        store = JsonStore(_store_path())
        if store.exists("server"):
            return store.get("server").get("ip", "")
    except Exception:
        pass
    return ""


def save_ip(ip):
    try:
        store = JsonStore(_store_path())
        store.put("server", ip=ip)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Shared widgets
# ---------------------------------------------------------------------------

class RoundedCard(BoxLayout):
    """A simple white card with rounded corners, used as the background
    container for status cards and rows."""

    def __init__(self, bg_color=COLOR_WHITE, radius=14, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        with self.canvas.before:
            Color(*bg_color)
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[radius]
            )
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class RoundedButton(Button):
    """A flat, rounded button matching the blue/white theme, since the
    default Kivy button looks out of place against these cards."""

    def __init__(self, bg_color=COLOR_BLUE, text_color=COLOR_WHITE, radius=12, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)  # transparent, we draw our own
        self.color = text_color
        self.bold = True
        self._rb_color = bg_color
        self._rb_radius = radius
        with self.canvas.before:
            Color(*bg_color)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size


# ---------------------------------------------------------------------------
# Connection / "login" screen
# ---------------------------------------------------------------------------

class ConnectScreen(Screen):
    """First screen the user sees. Lets them type in the Flask server's
    IP address, tests the connection, and saves it for next time."""

    def __init__(self, on_connected, **kwargs):
        super().__init__(**kwargs)
        self.on_connected = on_connected

        root = BoxLayout(orientation="vertical", padding=28, spacing=16)
        with root.canvas.before:
            Color(*COLOR_BG)
            self._bg_rect = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=self._update_bg, size=self._update_bg)
        self._root_layout = root

        # spacer to push the card toward the vertical middle
        root.add_widget(Widget(size_hint_y=0.3))

        title = Label(
            text="SmartLift",
            color=COLOR_BLUE,
            font_size=26,
            bold=True,
            size_hint_y=None,
            height=40,
        )
        root.add_widget(title)

        subtitle = Label(
            text="Enter your Flask server's IP address to connect",
            color=COLOR_TEXT_GRAY,
            font_size=13,
            size_hint_y=None,
            height=24,
        )
        root.add_widget(subtitle)

        card = RoundedCard(orientation="vertical", padding=18, spacing=12,
                            size_hint_y=None, height=170)

        ip_label = Label(text="Server IP address", color=COLOR_TEXT_GRAY, font_size=12,
                          halign="left", size_hint_y=None, height=16)
        ip_label.bind(size=ip_label.setter("text_size"))
        card.add_widget(ip_label)

        self.ip_input = TextInput(
            text=load_saved_ip(),
            hint_text="e.g. 10.165.149.150",
            multiline=False,
            size_hint_y=None,
            height=44,
            padding=[12, 10, 12, 10],
            background_normal="",
            background_active="",
            background_color=COLOR_BLUE_LIGHT,
            foreground_color=COLOR_TEXT_DARK,
            cursor_color=COLOR_BLUE,
        )
        card.add_widget(self.ip_input)

        self.connect_button = RoundedButton(text="Connect", size_hint_y=None, height=46)
        self.connect_button.bind(on_release=lambda *a: self.try_connect())
        card.add_widget(self.connect_button)

        root.add_widget(card)

        self.status_label = Label(
            text="",
            color=COLOR_RED,
            font_size=12,
            size_hint_y=None,
            height=20,
        )
        root.add_widget(self.status_label)

        root.add_widget(Widget())  # bottom spacer
        self.add_widget(root)

    def _update_bg(self, *args):
        self._bg_rect.pos = self._root_layout.pos
        self._bg_rect.size = self._root_layout.size

    def try_connect(self):
        ip = self.ip_input.text.strip()
        if not ip:
            self.status_label.text = "Please enter a server IP address."
            return

        self.connect_button.text = "Connecting..."
        self.connect_button.disabled = True
        self.status_label.text = ""

        # Run the network check on a slight delay so the button text
        # actually updates on screen before the (blocking) request fires.
        Clock.schedule_once(lambda dt: self._do_connect_check(ip), 0.05)

    def _do_connect_check(self, ip):
        url = f"http://{ip}:{SERVER_PORT}/api/health"
        try:
            response = requests.get(url, timeout=CONNECT_TIMEOUT_SECONDS)
            response.raise_for_status()
            save_ip(ip)
            self.connect_button.text = "Connect"
            self.connect_button.disabled = False
            self.on_connected(ip)
        except requests.exceptions.RequestException:
            self.connect_button.text = "Connect"
            self.connect_button.disabled = False
            self.status_label.text = (
                "Couldn't reach that server. Check the IP and that "
                "both devices are on the same network."
            )


# ---------------------------------------------------------------------------
# Main dashboard widgets
# ---------------------------------------------------------------------------

class FloorRow(RoundedCard):
    """One row in the floor list: a numbered badge, floor label,
    and the current waiting count."""

    def __init__(self, floor_number, **kwargs):
        super().__init__(orientation="horizontal", padding=16, spacing=10,
                          size_hint_y=None, height=56, **kwargs)
        self.floor_number = floor_number

        badge = Label(
            text=str(floor_number),
            color=COLOR_BLUE,
            bold=True,
            size_hint=(None, None),
            size=(32, 32),
        )
        with badge.canvas.before:
            Color(*COLOR_BLUE_LIGHT)
            self._badge_bg = RoundedRectangle(pos=badge.pos, size=badge.size, radius=[16])
        badge.bind(pos=self._update_badge, size=self._update_badge)
        self._badge_widget = badge

        floor_label = Label(
            text=f"Floor {floor_number}",
            color=COLOR_TEXT_DARK,
            halign="left",
            valign="middle",
        )
        floor_label.bind(size=floor_label.setter("text_size"))

        self.count_label = Label(
            text="--",
            color=COLOR_TEXT_DARK,
            bold=True,
            halign="right",
            valign="middle",
            size_hint_x=None,
            width=50,
        )
        self.count_label.bind(size=self.count_label.setter("text_size"))

        self.add_widget(badge)
        self.add_widget(floor_label)
        self.add_widget(self.count_label)

    def _update_badge(self, *args):
        self._badge_bg.pos = self._badge_widget.pos
        self._badge_bg.size = self._badge_widget.size

    def set_count(self, count):
        self.count_label.text = str(count)


class ElevatorCard(RoundedCard):
    """Top card showing elevator occupancy, weight, and overload status."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=18, spacing=10,
                          size_hint_y=None, height=180, **kwargs)

        section_label = Label(
            text="Elevator status",
            color=COLOR_TEXT_GRAY,
            font_size=13,
            halign="left",
            size_hint_y=None,
            height=18,
        )
        section_label.bind(size=section_label.setter("text_size"))

        self.status_label = Label(
            text="Available",
            color=COLOR_GREEN,
            font_size=18,
            bold=True,
            halign="left",
            size_hint_y=None,
            height=26,
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))

        stats_row = GridLayout(cols=2, spacing=12, size_hint_y=None, height=70)

        self.occupants_value = Label(text="--", color=COLOR_TEXT_DARK,
                                      font_size=22, bold=True, halign="left", valign="top")
        self.occupants_value.bind(size=self.occupants_value.setter("text_size"))
        occupants_box = BoxLayout(orientation="vertical")
        occ_label = Label(text="Occupants", color=COLOR_TEXT_GRAY, font_size=12,
                           halign="left", size_hint_y=None, height=16)
        occ_label.bind(size=occ_label.setter("text_size"))
        occupants_box.add_widget(occ_label)
        occupants_box.add_widget(self.occupants_value)

        self.weight_value = Label(text="--", color=COLOR_TEXT_DARK,
                                   font_size=22, bold=True, halign="left", valign="top")
        self.weight_value.bind(size=self.weight_value.setter("text_size"))
        weight_box = BoxLayout(orientation="vertical")
        weight_label = Label(text="Weight", color=COLOR_TEXT_GRAY, font_size=12,
                              halign="left", size_hint_y=None, height=16)
        weight_label.bind(size=weight_label.setter("text_size"))
        weight_box.add_widget(weight_label)
        weight_box.add_widget(self.weight_value)

        stats_row.add_widget(occupants_box)
        stats_row.add_widget(weight_box)

        self.add_widget(section_label)
        self.add_widget(self.status_label)
        self.add_widget(stats_row)

    def update_data(self, occupant_count, weight_kg, max_capacity_kg, overloaded, capacity_status=None):
        self.occupants_value.text = str(occupant_count)
        self.weight_value.text = f"{weight_kg:.0f} / {max_capacity_kg:.0f} kg"

        if capacity_status is None:
            capacity_status = "overload" if overloaded else "available"

        if capacity_status == "overload":
            self.status_label.text = "Overload"
            self.status_label.color = COLOR_RED
            self.bg_color = COLOR_RED_LIGHT
        elif capacity_status == "full":
            self.status_label.text = "Full"
            self.status_label.color = COLOR_AMBER
            self.bg_color = COLOR_AMBER_LIGHT
        else:
            self.status_label.text = "Available"
            self.status_label.color = COLOR_GREEN
            self.bg_color = COLOR_WHITE

        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])


class LegendCard(RoundedCard):
    """Small reference card explaining what each status color means."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=16, spacing=8,
                          size_hint_y=None, height=130, **kwargs)

        title = Label(
            text="Status guide",
            color=COLOR_TEXT_GRAY,
            font_size=12,
            bold=True,
            halign="left",
            size_hint_y=None,
            height=16,
        )
        title.bind(size=title.setter("text_size"))
        self.add_widget(title)

        rows = [
            ("Available — safe to board", COLOR_GREEN),
            ("Full — 90% or more of capacity", COLOR_AMBER),
            ("Overload — exceeds capacity", COLOR_RED),
        ]
        for label_text, color in rows:
            row = BoxLayout(orientation="horizontal", spacing=10,
                             size_hint_y=None, height=24)
            dot = Label(text="\u25cf", color=color, size_hint=(None, None), size=(20, 24))
            text = Label(text=label_text, color=COLOR_TEXT_DARK, font_size=13,
                         halign="left", valign="middle")
            text.bind(size=text.setter("text_size"))
            row.add_widget(dot)
            row.add_widget(text)
            self.add_widget(row)


class DashboardScreen(Screen):
    """Main dashboard: header, elevator card, floor list, legend, and
    a small 'last updated' caption. Polls the server on a timer."""

    def __init__(self, on_change_server, **kwargs):
        super().__init__(**kwargs)
        self.on_change_server = on_change_server
        self.server_ip = ""
        self._refresh_event = None

        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        with root.canvas.before:
            Color(*COLOR_BG)
            self._bg_rect = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=self._update_bg, size=self._update_bg)
        self._root_layout = root

        header_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=32)
        title = Label(
            text="SmartLift",
            color=COLOR_BLUE,
            font_size=20,
            bold=True,
            halign="left",
            valign="middle",
        )
        title.bind(size=title.setter("text_size"))
        header_row.add_widget(title)

        change_server_btn = Button(
            text="Change server",
            size_hint=(None, None),
            size=(120, 30),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=COLOR_BLUE,
            font_size=12,
        )
        change_server_btn.bind(on_release=lambda *a: self.on_change_server())
        header_row.add_widget(change_server_btn)
        root.add_widget(header_row)

        self.elevator_card = ElevatorCard()
        root.add_widget(self.elevator_card)

        floors_label = Label(
            text="People waiting per floor",
            color=COLOR_TEXT_GRAY,
            font_size=13,
            halign="left",
            size_hint_y=None,
            height=20,
        )
        floors_label.bind(size=floors_label.setter("text_size"))
        root.add_widget(floors_label)

        self.floor_rows = {}
        floor_list = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        floor_list.bind(minimum_height=floor_list.setter("height"))
        for floor_number in FLOOR_NUMBERS:
            row = FloorRow(floor_number)
            self.floor_rows[floor_number] = row
            floor_list.add_widget(row)
        root.add_widget(floor_list)

        self.status_caption = Label(
            text="Connecting...",
            color=COLOR_TEXT_GRAY,
            font_size=11,
            halign="left",
            size_hint_y=None,
            height=18,
        )
        self.status_caption.bind(size=self.status_caption.setter("text_size"))
        root.add_widget(self.status_caption)

        root.add_widget(LegendCard())
        root.add_widget(Widget())

        self.add_widget(root)

    def _update_bg(self, *args):
        self._bg_rect.pos = self._root_layout.pos
        self._bg_rect.size = self._root_layout.size

    def start_polling(self, server_ip):
        self.server_ip = server_ip
        self.stop_polling()
        Clock.schedule_once(lambda dt: self.refresh_status(), 0)
        self._refresh_event = Clock.schedule_interval(
            lambda dt: self.refresh_status(), REFRESH_INTERVAL_SECONDS
        )

    def stop_polling(self):
        if self._refresh_event is not None:
            self._refresh_event.cancel()
            self._refresh_event = None

    def refresh_status(self):
        if not self.server_ip:
            return
        url = f"http://{self.server_ip}:{SERVER_PORT}/api/status"
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
            self.apply_status(data)
        except requests.exceptions.RequestException:
            self.show_connection_error()

    def apply_status(self, data):
        elevator = data.get("elevator", {})
        self.elevator_card.update_data(
            occupant_count=elevator.get("occupant_count", 0),
            weight_kg=elevator.get("weight_kg", 0.0),
            max_capacity_kg=elevator.get("max_capacity_kg", 0.0),
            overloaded=elevator.get("overloaded", False),
            capacity_status=elevator.get("capacity_status"),
        )

        floors = data.get("floors", {})
        for floor_number, row in self.floor_rows.items():
            floor_data = floors.get(str(floor_number), {})
            row.set_count(floor_data.get("waiting_count", 0))

        self.status_caption.text = f"Up to date — {self.server_ip}"
        self.status_caption.color = COLOR_TEXT_GRAY

    def show_connection_error(self):
        self.status_caption.text = "Couldn't reach the server — retrying..."
        self.status_caption.color = COLOR_RED


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class SmartLiftApp(App):
    def build(self):
        Window.clearcolor = COLOR_BG
        self._set_android_status_bar_color()

        self.sm = ScreenManager(transition=FadeTransition(duration=0.2))

        self.connect_screen = ConnectScreen(
            on_connected=self.handle_connected, name="connect"
        )
        self.dashboard_screen = DashboardScreen(
            on_change_server=self.handle_change_server, name="dashboard"
        )

        self.sm.add_widget(self.connect_screen)
        self.sm.add_widget(self.dashboard_screen)

        self.sm.current = "connect"

        return self.sm

    def handle_connected(self, server_ip):
        self.dashboard_screen.start_polling(server_ip)
        self.sm.current = "dashboard"

    def handle_change_server(self):
        self.dashboard_screen.stop_polling()
        self.sm.current = "connect"

    def _set_android_status_bar_color(self):
        """Colors the Android status bar to match the app background,
        instead of leaving it the default solid black. Safe no-op when
        not running on Android (e.g. desktop testing)."""
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            WindowManager = autoclass('android.view.WindowManager$LayoutParams')
            AndroidColor = autoclass('android.graphics.Color')

            activity = PythonActivity.mActivity
            window = activity.getWindow()
            window.clearFlags(WindowManager.FLAG_TRANSLUCENT_STATUS)
            window.addFlags(WindowManager.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS)

            bg = COLOR_BG
            android_color = AndroidColor.argb(
                255, int(bg[0] * 255), int(bg[1] * 255), int(bg[2] * 255)
            )
            window.setStatusBarColor(android_color)
        except Exception:
            pass  # not on Android — nothing to do


if __name__ == "__main__":
    SmartLiftApp().run()
