import flet as ft
import serial
import serial.tools.list_ports
import threading
import time


class MockSerial:
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self._data_buffer = []
        self._should_stop = False
        self.current_speed = 400

    def write(self, data: bytes):
        decoded = data.decode('utf-8').strip()
        print(f"[MOCK Serial] Отправлено: {decoded}")

        if decoded.startswith('s'):
            try:
                self.current_speed = int(decoded[1:])
                print(f"[MOCK Serial] Скорость изменена на: {self.current_speed}ms")
            except ValueError:
                print("[MOCK Serial] Ошибка парсинга скорости")
        elif decoded == 'p':
            print("[MOCK Serial] Пауза переключена")
        elif decoded == 'r':
            print("[MOCK Serial] Игра перезапущена")

    def readline(self) -> bytes:
        time.sleep(0.5)
        return b"LEVEL:5\n"

    def close(self):
        self.is_open = False
        print("[MOCK Serial] Порт закрыт")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DinoGame:
    def __init__(self, page: ft.Page, use_mock: bool = True):
        self.page = page
        self.use_mock = use_mock
        self.page.title = "Dino Game"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.window_width = 400
        self.page.window_height = 400

        self.serial_conn = None
        self.connected = False
        self.current_speed = 400
        self.saved_speed = 400
        self.is_paused = False
        self.game_started = False

        # UI Elements
        self.ports_dropdown = ft.Dropdown(
            options=self.get_serial_ports(),
            label="Select COM Port",
            width=300,
            # Основные стили
            filled=True,
            fill_color="#eff7e4",
            border_color="#333d29",
            border_width=2,
            border_radius=10,
            focused_border_color="#4a5c3a",
            focused_border_width=2,
            # Текст и подсказка
            hint_text="Choose a port...",
            hint_style=ft.TextStyle(color="#666666"),
            text_style=ft.TextStyle(color="#333d29", size=14),
            # Стиль выбранного элемента
            # Иконка (можно изменить)
            suffix_icon=ft.Icons.ARROW_DROP_DOWN,
            suffix_style=ft.TextStyle(color="#333d29"),
        )

        self.connect_btn = ft.ElevatedButton(
            text="Connect",
            on_click=self.connect_serial,
            style=ft.ButtonStyle(
                color="#333d29",  # Текст
                bgcolor="#eff7e4",  # Фон
                overlay_color="#d1e8b0",  # При нажатии
                elevation=2,  # Тень
                padding=20,  # Внутренние отступы
                shape=ft.RoundedRectangleBorder(radius=10),  # Закругление
            ),
        )

        self.status_text = ft.Text("Status: Disconnected", color="red")

        self.jump_btn = ft.ElevatedButton(
            text="JUMP! (Space)",
            on_click=self.send_jump_command,
            disabled=True,
            width=200,
            height=100,
            style=ft.ButtonStyle(
                bgcolor="#98b548",
                color=ft.Colors.WHITE
            )
        )

        self.pause_btn = ft.ElevatedButton(
            text="PAUSE (P)",
            on_click=self.toggle_pause,
            disabled=True,
            width=200,
            height=50,
            style=ft.ButtonStyle(
                bgcolor="#f09134",
                color=ft.Colors.WHITE
            )
        )

        self.restart_btn = ft.ElevatedButton(
            text="RESTART",
            on_click=self.restart_game,
            disabled=True,
            width=200,
            height=50,
            style=ft.ButtonStyle(
                bgcolor="#6e0d25",
                color=ft.Colors.WHITE
            )
        )

        self.level_text = ft.Text("Level: 0", size=20,  color="#333d29")

        self.speed_slider = ft.Slider(
                                    min=100,  # Быстрее
                                    max=1000,  # Медленнее
                                    divisions=9,
                                    value=self.current_speed,
                                    on_change=self.speed_changed,
                                    active_color="#82c44f",
                                    inactive_color="#d1e8b0",
                                    thumb_color="#333d29",
                                    label=None,  # Убираем стандартную подпись
                                )

        self.settings_btn = ft.IconButton(
            icon=ft.Icons.SETTINGS,
            on_click=self.open_settings_dialog,
            disabled=True,
            icon_color = "#333d29",
            style=ft.ButtonStyle(
                overlay_color="#f0f5e4",  # Убирает эффект нажатия
            )
        )

        self.start_btn = ft.ElevatedButton(
            text="START",
            on_click=self.start_game,
            width=200,
            height=100,
            style=ft.ButtonStyle(
                bgcolor="#98b548",
                color=ft.Colors.WHITE,
                overlay_color="#677423",
            )
        )

        self.back_btn = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            icon_color="#82c44f",
            icon_size=24,
            on_click=self.go_back_to_main,
            tooltip="Back to main screen",
            style=ft.ButtonStyle(
                bgcolor="#f0ead2",  # Фон как у основного окна
                overlay_color="#d1e8b0",
                shape=ft.RoundedRectangleBorder(radius=8),

                padding=10,
            ),
        )

        self.settings_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Game Settings"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Speed settings", size=16, color="#333d29", weight=ft.FontWeight.BOLD),
                    # Добавленная надпись
                    ft.Row(
                        [
                            ft.Text("Fast", color="#333d29", size=14),
                            ft.Container(
                                content=self.speed_slider,
                                expand=True,
                                padding=ft.padding.symmetric(horizontal=10)
                            ),
                            ft.Text("Slow", color="#333d29", size=14),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"Current: {self._get_speed_label(self.current_speed)}",
                            color="#333d29",
                            size=12,
                            weight=ft.FontWeight.W_400
                        ),
                        padding=ft.padding.only(top=10)
                    )
                ]),
                bgcolor="#f0ead2",
                padding=20,
                border_radius=10,
            ),
            actions=[
                ft.TextButton(
                    "OK",
                    on_click=self.close_settings_dialog,
                    style=ft.ButtonStyle(
                        color="#82c44f",  # Зеленый текст
                        overlay_color="#f0ead2",  # Светло-зеленый при нажатии (с прозрачностью)
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=20, vertical=8),
                        mouse_cursor=ft.MouseCursor.CLICK,
                        animation_duration=0,
                    ),
                )
            ],
            on_dismiss=lambda e: print("Диалог закрыт")
        )

        self.page.overlay.append(self.settings_dialog)

        # Main screen
        self.main_screen = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [self.ports_dropdown, self.connect_btn, self.settings_btn],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10
                    ),
                    ft.Container(height=20),
                    self.status_text,
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    ft.Container(
                        self.start_btn,
                        alignment=ft.alignment.center
                    ),
                    ft.Container(height=20),
                    self.level_text
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.alignment.center,
            expand=True
        )

        # Game controller screen
        self.game_controller_screen = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [self.back_btn, ft.Text("Game Controller", size=20)],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=10
                    ),
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    ft.Container(
                        self.jump_btn,
                        alignment=ft.alignment.center
                    ),
                    ft.Container(
                        self.pause_btn,
                        alignment=ft.alignment.center
                    ),
                    ft.Container(
                        self.restart_btn,
                        alignment=ft.alignment.center
                    ),
                    ft.Container(height=20),
                    self.level_text
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.START,
            ),
            alignment=ft.alignment.center,
            expand=True
        )

        # Set initial screen
        self.page.add(self.main_screen)

        self.page.on_keyboard_event = self.on_keyboard

    def _get_speed_label(self, speed_value):
        """Преобразует числовое значение скорости в текстовый формат"""
        if speed_value <= 200:
            return "Very Fast"
        elif speed_value <= 400:
            return "Fast"
        elif speed_value <= 600:
            return "Medium"
        elif speed_value <= 800:
            return "Slow"
        else:
            return "Very Slow"

    def update_ui_connected(self, port_name):
        self.status_text.value = f"Connected: {port_name}"
        self.status_text.color = ft.Colors.GREEN
        self.start_btn.disabled = False
        self.settings_btn.disabled = False  # Включаем кнопку настроек при подключении
        self.connect_btn.text = "Disconnect"
        self.connect_btn.on_click = self.disconnect_serial
        self.page.update()

    def update_ui_disconnected(self, message):
        self.status_text.value = message
        self.status_text.color = ft.Colors.RED
        self.jump_btn.disabled = True
        self.pause_btn.disabled = True
        self.restart_btn.disabled = True
        self.start_btn.disabled = True
        self.settings_btn.disabled = True  # Отключаем кнопку настроек при отключении
        self.connect_btn.text = "Connect"
        self.connect_btn.on_click = self.connect_serial
        self.page.update()

    def connect_serial(self, e):
        if self.use_mock:
            print("[TEST] Using Mock Serial")
            self.serial_conn = MockSerial()
            self.connected = True
            self.update_ui_connected("Mock Mode")
        else:
            if not self.ports_dropdown.value:
                self.update_ui_disconnected("Please select a port")
                return

            try:
                self.serial_conn = serial.Serial(
                    port=self.ports_dropdown.value,
                    baudrate=9600,
                    timeout=1,
                    write_timeout=1
                )
                time.sleep(2)
                self.connected = True
                self.update_ui_connected(self.ports_dropdown.value)
                self.send_speed_command()

                self.reading_thread = threading.Thread(
                    target=self.read_serial_data,
                    daemon=True
                )
                self.reading_thread.start()

            except Exception as e:
                self.update_ui_disconnected(f"Connection failed: {str(e)}")
                if hasattr(self, 'serial_conn') and self.serial_conn:
                    self.serial_conn.close()
                self.connected = False

    def disconnect_serial(self, e):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.connected = False
        self.game_started = False
        self.update_ui_disconnected("Status: Disconnected")
        self.go_back_to_main(None)

    def speed_changed(self, e):
        """Обработчик изменения скорости игры"""
        self.current_speed = int(self.speed_slider.value)
        self.saved_speed = self.current_speed
        # Обновляем отображение текущей скорости
        if hasattr(self, 'settings_dialog') and self.settings_dialog.open:
            for control in self.settings_dialog.content.content.controls:
                if isinstance(control, ft.Container) and len(control.content.value) > 0:
                    if "Current:" in control.content.value:
                        control.content.value = f"Current: {self._get_speed_label(self.current_speed)}"
                        break
        self.page.update()
        if self.connected:
            self.send_speed_command()

    def read_serial_data(self):
        buffer = ""
        while self.connected and self.serial_conn and self.serial_conn.is_open:
            try:
                data = self.serial_conn.read(self.serial_conn.in_waiting or 1)
                if data:
                    decoded = data.decode('utf-8', errors='ignore')
                    buffer += decoded

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line.startswith("LEVEL:"):
                            level = line.split(":")[1]
                            self.level_text.value = f"Level: {level}"
                            self.level_text.color = "#333d29"
                            self.page.update()
                        elif line == "GAME_OVER":
                            self.level_text.value = "Game Over!"
                            self.page.update()
                        elif line == "PAUSED":
                            self.is_paused = True
                            self.pause_btn.text = "RESUME (P)"
                            self.page.update()
                        elif line == "RESUMED":
                            self.is_paused = False
                            self.pause_btn.text = "PAUSE (P)"
                            self.page.update()
                        elif line == "STATUS:GAME_RESET":  # Добавьте эту обработку
                            self.level_text.value = "Level: 0"
                            self.page.update()

            except serial.SerialException as e:
                print(f"Serial error: {e}")
                self.disconnect_serial(None)
                break
            except Exception as e:
                print(f"Error reading serial: {e}")
                time.sleep(0.1)

    def send_speed_command(self):
        if self.connected and self.serial_conn:
            try:
                command = f"s{self.current_speed}\n".encode('utf-8')
                self.serial_conn.write(command)
                self.serial_conn.flush()
                print(f"Speed set to: {self.current_speed}ms")
            except Exception as e:
                print(f"Error sending speed: {e}")
                self.disconnect_serial(None)

    def send_jump_command(self, e):
        if self.connected and self.serial_conn and self.game_started and not self.is_paused:
            try:
                self.serial_conn.write(b'j\n')
                self.serial_conn.flush()
            except Exception as e:
                print(f"Error sending jump command: {e}")
                self.disconnect_serial(None)

    def toggle_pause(self, e):
        if self.connected and self.serial_conn and self.game_started:
            try:
                self.serial_conn.write(b'p\n')
                self.serial_conn.flush()
                print("Pause toggled")
            except Exception as e:
                print(f"Error sending pause command: {e}")
                self.disconnect_serial(None)

    def restart_game(self, e):
        if self.connected and self.serial_conn:
            try:
                self.serial_conn.write(b'r\n')
                self.serial_conn.flush()
                print("Game restarted")

                self.game_started = True
                self.is_paused = False
                self.pause_btn.text = "PAUSE (P)"

                # Восстанавливаем сохраненную скорость после перезапуска
                self.current_speed = self.saved_speed
                self.speed_slider.value = self.saved_speed
                self.send_speed_command()

                # Обновляем интерфейс
                self.level_text.value = "Level: 0"

                self.page.update()
            except Exception as e:
                print(f"Error sending restart command: {e}")
                self.disconnect_serial(None)

    def open_settings_dialog(self, e):
        self.speed_slider.value = self.current_speed
        self.page.dialog = self.settings_dialog
        self.settings_dialog.open = True
        self.page.update()

    def close_settings_dialog(self, e):
        self.settings_dialog.open = False
        self.page.update()

    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [
            ft.dropdown.Option(
                port.device,
                style=ft.ButtonStyle(
                    color="#333d29",  # Цвет текста
                ),
            )
            for port in ports
        ]

    def on_keyboard(self, e: ft.KeyboardEvent):
        if e.key == " " and self.connected and self.game_started and not self.is_paused:
            self.send_jump_command(None)
        elif e.key.lower() == "p" and self.connected and self.game_started:
            self.toggle_pause(None)

    def start_game(self, e):
        if self.connected:
            self.game_started = True
            self.jump_btn.disabled = False
            self.pause_btn.disabled = False
            self.restart_btn.disabled = False

            # Устанавливаем сохраненную скорость при старте игры
            self.current_speed = self.saved_speed
            self.send_speed_command()

            self.page.controls.clear()
            self.page.add(self.game_controller_screen)
            self.page.update()

    def go_back_to_main(self, e):
        self.game_started = False
        self.jump_btn.disabled = True
        self.pause_btn.disabled = True
        self.restart_btn.disabled = True

        # Сохраняем текущую скорость перед возвратом
        self.saved_speed = self.current_speed

        self.page.controls.clear()
        self.page.add(self.main_screen)
        self.page.update()


def main(page: ft.Page):
    page.bgcolor = "#f0ead2"
    game = DinoGame(page, use_mock=True)


ft.app(target=main)