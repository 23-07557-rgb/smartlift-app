"""
SmartLift Mobile App (Kivy)
----------------------------
Connects to the SmartLift Flask backend and displays:
  - Elevator status (occupants, weight, overloaded warning)
  - Waiting count for each floor

Auto-refreshes every few seconds. No manual refresh button needed.

Run this on your computer with:
    pip install kivy requests
    python main.py

Before running, set SERVER_IP below to your Flask server's local IP
(the one shown when you run app.py, e.g. 10.165.149.150).
"""

import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window

# ---------------------------------------------------------------------------
# Configuration — change this to match your Flask server
# ---------------------------------------------------------------------------

SERVER_IP = "10.165.149.150"     # your computer's local IP running Flask
SERVER_PORT = 5000
STATUS_URL = f"http://{SERVER_IP}:{SERVER_PORT}/api/status"

REFRESH_INTERVAL_SECONDS = 1    # how often the app polls the server
REQUEST_TIMEOUT_SECONDS = 4     # how long to wait before giving up on a request

FLOOR_NUMBERS = [1, 2, 3]

# ---------------------------------------------------------------------------
# Colors — blue and white theme, matching the app mockup
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


class RoundedCard(BoxLayout):
    """A simple white card with rounded corners and a light border,
    used as the background container for the elevator status and
    each floor row."""

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
    """Top card showing elevator occupancy, weight, and overload status.
    Switches color scheme between normal (blue/white) and overloaded (red)."""

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

        # Fall back to the old two-state logic if an older server response
        # doesn't include capacity_status.
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

        # repaint the background with the new color
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])


class SmartLiftRoot(BoxLayout):
    """Top-level layout: header, elevator card, floor list, and a
    small 'last updated' caption."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=16, spacing=12, **kwargs)

        with self.canvas.before:
            Color(*COLOR_BG)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._update_bg, size=self._update_bg)

        title = Label(
            text="SmartLift",
            color=COLOR_BLUE,
            font_size=20,
            bold=True,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=32,
        )
        title.bind(size=title.setter("text_size"))
        self.add_widget(title)

        self.elevator_card = ElevatorCard()
        self.add_widget(self.elevator_card)

        floors_label = Label(
            text="People waiting per floor",
            color=COLOR_TEXT_GRAY,
            font_size=13,
            halign="left",
            size_hint_y=None,
            height=20,
        )
        floors_label.bind(size=floors_label.setter("text_size"))
        self.add_widget(floors_label)

        self.floor_rows = {}
        floor_list = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        floor_list.bind(minimum_height=floor_list.setter("height"))
        for floor_number in FLOOR_NUMBERS:
            row = FloorRow(floor_number)
            self.floor_rows[floor_number] = row
            floor_list.add_widget(row)
        self.add_widget(floor_list)

        self.status_caption = Label(
            text="Connecting...",
            color=COLOR_TEXT_GRAY,
            font_size=11,
            halign="left",
            size_hint_y=None,
            height=18,
        )
        self.status_caption.bind(size=self.status_caption.setter("text_size"))
        self.add_widget(self.status_caption)

        # spacer so content sticks to the top instead of stretching
        self.add_widget(Widget())

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

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
            # JSON keys come back as strings, so look up with str()
            floor_data = floors.get(str(floor_number), {})
            row.set_count(floor_data.get("waiting_count", 0))

        self.status_caption.text = "Up to date"
        self.status_caption.color = COLOR_TEXT_GRAY

    def show_connection_error(self):
        self.status_caption.text = "Couldn't reach the server — retrying..."
        self.status_caption.color = COLOR_RED


class SmartLiftApp(App):
    def build(self):
        Window.clearcolor = COLOR_BG
        self.root_widget = SmartLiftRoot()
        # Fetch immediately on launch, then keep refreshing on a timer.
        Clock.schedule_once(lambda dt: self.refresh_status(), 0)
        Clock.schedule_interval(lambda dt: self.refresh_status(), REFRESH_INTERVAL_SECONDS)
        return self.root_widget

    def refresh_status(self):
        try:
            response = requests.get(STATUS_URL, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
            self.root_widget.apply_status(data)
        except requests.exceptions.RequestException:
            self.root_widget.show_connection_error()


if __name__ == "__main__":
    SmartLiftApp().run()
