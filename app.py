# app.py
import sys
import threading

from PyQt6 import QtWidgets, QtGui, QtCore

from bot_code import run_bot, config, save_config, BOT_VERSION


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Discord Ticket Bot Panel")
        self.resize(960, 600)
        self.setWindowIcon(QtGui.QIcon())  # можно подставить свой .ico

        self.bot_thread = None
        self.bot_running = False

        self.init_ui()

    def init_ui(self):
        # Градиентный фон и общие стили
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4b0082,
                    stop:0.5 #2b0b45,
                    stop:1 #050509
                );
            }
            QWidget#Card {
                background-color: rgba(15, 15, 25, 0.96);
                border-radius: 22px;
            }
            QLabel#Title {
                color: white;
                font-size: 22px;
                font-weight: 600;
            }
            QLabel#Subtitle {
                color: #a5b4fc;
                font-size: 13px;
            }
            QTextEdit, QLineEdit {
                background-color: #111827;
                color: #e5e7eb;
                border-radius: 10px;
                border: 1px solid #374151;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border-radius: 14px;
                padding: 8px 16px;
                border: none;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #8b5cf6;
            }
            QPushButton#Danger {
                background-color: #ef4444;
            }
            QPushButton#Danger:hover {
                background-color: #f97373;
            }
            QLabel {
                color: #d1d5db;
            }
        """)

        central = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(16)

        # Верхняя надпись
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Панель управления Discord ботом", objectName="Title")
        subtitle = QtWidgets.QLabel(
            f"Версия бота: {BOT_VERSION}  •  Управление тикет-системой и настройками",
            objectName="Subtitle"
        )
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        header_box = QtWidgets.QVBoxLayout()
        header_box.addWidget(title)
        header_box.addWidget(subtitle)

        header_layout.addLayout(header_box)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Карточка с содержимым
        card = QtWidgets.QWidget(objectName="Card")
        card_layout = QtWidgets.QGridLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setHorizontalSpacing(24)
        card_layout.setVerticalSpacing(18)

        # Левая часть – управление ботом
        left_box = QtWidgets.QVBoxLayout()
        left_label = QtWidgets.QLabel("Статус бота")
        left_label.setStyleSheet("font-weight: 600; font-size: 15px;")

        self.status_label = QtWidgets.QLabel("Бот не запущен.")
        self.status_label.setStyleSheet("color: #f97373;")

        self.run_btn = QtWidgets.QPushButton("Запустить бота")
        self.run_btn.clicked.connect(self.start_bot)

        self.stop_info = QtWidgets.QLabel(
            "Остановить бота можно командой !kill_bot в Discord (только владелец)."
        )
        self.stop_info.setWordWrap(True)
        self.stop_info.setStyleSheet("font-size: 11px; color: #9ca3af;")

        left_box.addWidget(left_label)
        left_box.addWidget(self.status_label)
        left_box.addSpacing(10)
        left_box.addWidget(self.run_btn)
        left_box.addSpacing(10)
        left_box.addWidget(self.stop_info)
        left_box.addStretch()

        # Правая часть – настройки welcome_message
        right_box = QtWidgets.QVBoxLayout()
        right_label = QtWidgets.QLabel("Приветственное сообщение")
        right_label.setStyleSheet("font-weight: 600; font-size: 15px;")

        self.welcome_edit = QtWidgets.QTextEdit()
        self.welcome_edit.setPlaceholderText("Добро пожаловать на сервер! ...")
        self.welcome_edit.setText(config.get("welcome_message", "Добро пожаловать на сервер!"))

        save_welcome_btn = QtWidgets.QPushButton("Сохранить приветствие")
        save_welcome_btn.clicked.connect(self.save_welcome)

        help_label = QtWidgets.QLabel(
            "Это сообщение бот отправляет в канал приветствий при заходе нового участника.\n"
            "Конфигурация сохраняется в config.json."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-size: 11px; color: #9ca3af;")

        right_box.addWidget(right_label)
        right_box.addWidget(self.welcome_edit)
        right_box.addWidget(save_welcome_btn)
        right_box.addWidget(help_label)
        right_box.addStretch()

        # Раскладываем в сетку
        card_layout.addLayout(left_box, 0, 0)
        card_layout.addLayout(right_box, 0, 1)

        main_layout.addWidget(card)
        main_layout.addStretch()

        self.setCentralWidget(central)

    def start_bot(self):
        if self.bot_running:
            return
        self.bot_running = True

        self.status_label.setText("Бот запускается...")
        self.status_label.setStyleSheet("color: #fbbf24;")  # жёлтый

        def run():
            try:
                run_bot()
            except Exception as e:
                print(f"Ошибка запуска бота: {e}")
            finally:
                # если бот завершится – обновим статус
                self.bot_running = False
                self.status_label.setText("Бот остановлен.")
                self.status_label.setStyleSheet("color: #f97373;")
                self.run_btn.setEnabled(True)
                self.run_btn.setText("Запустить бота")

        self.bot_thread = threading.Thread(target=run, daemon=True)
        self.bot_thread.start()

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Бот запущен")
        self.status_label.setText("Бот запущен и работает.")
        self.status_label.setStyleSheet("color: #4ade80;")  # зелёный

    def save_welcome(self):
        text = self.welcome_edit.toPlainText().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Приветственное сообщение не может быть пустым.")
            return
        config["welcome_message"] = text
        save_config(config)
        QtWidgets.QMessageBox.information(self, "Сохранено", "Приветственное сообщение обновлено.")


def main():
    app = QtWidgets.QApplication(sys.argv)

    # Немного отключаем standard-минмальные стили
    app.setStyle("Fusion")

    w = MainWindow()
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()