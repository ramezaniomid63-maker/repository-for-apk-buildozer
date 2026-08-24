import socket
import json
import urllib.request
import urllib.error

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.button import Button


# =========================================================
# تنظیمات
# =========================================================

DISCOVERY_PORT = 4210
DISCOVERY_MESSAGE = b"ESP32_DISCOVER"

HTTP_TIMEOUT = 2


# =========================================================
# Toggle Switch
# =========================================================

class ToggleSwitch(Widget):

    value = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.size_hint = (None, None)
        self.size = (80, 42)

        self.bind(pos=self.redraw)
        self.bind(size=self.redraw)
        self.bind(value=self.redraw)

        self.redraw()

    def redraw(self, *args):

        self.canvas.clear()

        with self.canvas:

            # Slot
            if self.value:
                Color(0.1, 0.7, 0.25, 1)
            else:
                Color(0.35, 0.35, 0.35, 1)

            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[21]
            )

            # دایره
            Color(1, 1, 1, 1)

            circle_size = 32

            if self.value:
                x = self.x + self.width - circle_size - 5
            else:
                x = self.x + 5

            y = self.y + 5

            Ellipse(
                pos=(x, y),
                size=(circle_size, circle_size)
            )


# =========================================================
# Relay Button
# =========================================================

class RelayWidget(BoxLayout):

    def __init__(self, relay_number, condition, status, command_callback, **kwargs):

        super().__init__(
            orientation="vertical",
            spacing=5,
            padding=5,
            **kwargs
        )

        self.relay_number = relay_number
        self.condition = condition
        self.status = status
        self.command_callback = command_callback

        self.size_hint_y = None
        self.height = 90

        # عنوان
        self.label = Label(
            text=f"Relay {relay_number}",
            size_hint_y=None,
            height=30
        )

        self.add_widget(self.label)

        # -------------------------
        # Toggle
        # -------------------------

        if self.condition == 1:

            self.switch = ToggleSwitch(
                value=bool(self.status)
            )

            self.switch.bind(
                on_touch_down=self.toggle_pressed
            )

            self.add_widget(self.switch)

        # -------------------------
        # Momentary
        # -------------------------

        else:

            self.button = Button(
                text="●",
                font_size=28,
                size_hint=(None, None),
                size=(60, 45),
                pos_hint={"center_x": 0.5}
            )

            self.button.bind(
                on_press=self.momentary_pressed
            )

            self.add_widget(self.button)

            self.update_status(self.status)

    # =====================================================
    # Toggle
    # =====================================================

    def toggle_pressed(self, widget, touch):

        if not widget.collide_point(*touch.pos):
            return False

        if touch.button != "left":
            return False

        # تغییر حالت
        new_value = not self.switch.value

        self.command_callback(
            self.relay_number,
            new_value
        )

        return True

    # =====================================================
    # Momentary
    # =====================================================

    def momentary_pressed(self, instance):

        # برای Momentary فقط ON ارسال می‌کنیم
        self.command_callback(
            self.relay_number,
            True
        )

    # =====================================================
    # Update
    # =====================================================

    def update_status(self, status):

        self.status = status

        if self.condition == 1:

            self.switch.value = bool(status)

        else:

            if status:
                self.button.background_color = (
                    0.2, 0.8, 0.3, 1
                )
            else:
                self.button.background_color = (
                    1, 1, 1, 1
                )


# =========================================================
# Main App
# =========================================================

class RelayApp(App):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        self.esp_ip = None
        self.esp_port = 80

        self.relay_status = []
        self.relay_conditions = []

        self.relay_widgets = []

        self.main_layout = BoxLayout(
            orientation="vertical"
        )

        self.status_label = Label(
            text="Searching for ESP32...",
            size_hint_y=None,
            height=50
        )

    # =====================================================
    # Build
    # =====================================================

    def build(self):

        self.main_layout.add_widget(
            self.status_label
        )

        Clock.schedule_once(
            self.start_discovery,
            0.5
        )

        return self.main_layout

    # =====================================================
    # UDP Discovery
    # =====================================================

    def start_discovery(self, *args):

        self.status_label.text = "Searching for ESP32..."

        Clock.schedule_once(
            self.discovery_thread,
            0
        )

    def discovery_thread(self, *args):

        # چون Kivy UI نباید با socket بلاک شود،
        # Discovery را در Thread انجام می‌دهیم.

        import threading

        threading.Thread(
            target=self.discover_esp32,
            daemon=True
        ).start()

    def discover_esp32(self):

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_BROADCAST,
            1
        )

        sock.settimeout(0.7)

        try:

            sock.bind(("", 0))

            sock.sendto(
                DISCOVERY_MESSAGE,
                ("10.161.182.255", DISCOVERY_PORT)
            )

            while True:

                try:

                    data, address = sock.recvfrom(1024)

                except socket.timeout:
                    break

                try:

                    response = json.loads(
                        data.decode()
                    )

                    if response.get("device") == "ESP32_RELAY":

                        ip = response.get("ip")
                        port = response.get("port", 80)

                        if ip:

                            Clock.schedule_once(
                                lambda dt,
                                ip=ip,
                                port=port:
                                self.esp_found(ip, port)
                            )

                            break

                except Exception:
                    continue

        finally:

            sock.close()

    # =====================================================
    # ESP32 Found
    # =====================================================

    def esp_found(self, ip, port):

        self.esp_ip = ip
        self.esp_port = port

        self.status_label.text = (
            f"ESP32 Found: {ip}"
        )

        # درخواست وضعیت اولیه
        self.send_command("00_00")

    # =====================================================
    # HTTP Command
    # =====================================================

    def send_command(self, command):

        if not self.esp_ip:
            return

        import threading

        threading.Thread(
            target=self.http_command,
            args=(command,),
            daemon=True
        ).start()

    def http_command(self, command):

        try:

            url = (
                f"http://{self.esp_ip}:"
                f"{self.esp_port}/command"
            )

            data = command.encode()

            request = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={
                    "Content-Type":
                    "text/plain"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=HTTP_TIMEOUT
            ) as response:

                result = response.read().decode()

            data = json.loads(result)

            Clock.schedule_once(
                lambda dt:
                self.process_status(data)
            )

        except Exception as e:

            print(
                "HTTP ERROR:",
                e
            )

            Clock.schedule_once(
                lambda dt:
                self.connection_error()
            )

    # =====================================================
    # JSON
    # =====================================================

    def process_status(self, data):

        try:

            statuses = data["relays"]

            # بار اول
            if "conditions" in data:

                self.relay_conditions = (
                    data["conditions"]
                )

                self.relay_status = statuses

                self.build_relays()

            else:

                self.relay_status = statuses

                self.update_relays()

            self.status_label.text = (
                f"Connected: {self.esp_ip}"
            )

        except Exception as e:

            print(
                "JSON ERROR:",
                e
            )

    # =====================================================
    # ساخت 24 دکمه
    # =====================================================

    def build_relays(self):

        # پاک کردن قبلی

        self.main_layout.clear_widgets()

        self.main_layout.add_widget(
            self.status_label
        )

        grid = GridLayout(
            cols=3,
            spacing=10,
            padding=10
        )

        self.relay_widgets = []

        for i in range(24):

            relay_number = i + 1

            condition = (
                self.relay_conditions[i]
            )

            status = (
                self.relay_status[i]
            )

            widget = RelayWidget(
                relay_number=relay_number,
                condition=condition,
                status=status,
                command_callback=self.relay_command
            )

            self.relay_widgets.append(
                widget
            )

            grid.add_widget(widget)

        self.main_layout.add_widget(grid)

    # =====================================================
    # آپدیت وضعیت دکمه‌ها
    # =====================================================

    def update_relays(self):

        for i, widget in enumerate(
            self.relay_widgets
        ):

            if i < len(self.relay_status):

                widget.update_status(
                    self.relay_status[i]
                )

    # =====================================================
    # Command
    # =====================================================

    def relay_command(
        self,
        relay_number,
        turn_on
    ):

        if turn_on:

            command = (
                f"{relay_number:02d}_01"
            )

        else:

            command = (
                f"{relay_number:02d}_00"
            )

        print(
            "SEND:",
            command
        )

        self.send_command(command)

    # =====================================================
    # Error
    # =====================================================

    def connection_error(self):

        self.status_label.text = (
            "Connection lost - searching..."
        )

        self.esp_ip = None

        Clock.schedule_once(
            self.start_discovery,
            1
        )


# =========================================================
# Run
# =========================================================

if __name__ == "__main__":
    RelayApp().run()
