from __future__ import annotations

from datetime import datetime, timezone
import random
import sys
from pathlib import Path


def _bootstrap_vendor_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    vendor_path = project_root / ".vendor"
    if vendor_path.exists():
        candidate = str(vendor_path)
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


_bootstrap_vendor_path()

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (  # noqa: E402
        QApplication,
        QComboBox,
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QSpinBox,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "PySide6 is not installed. Install it with: "
        "python3 -m pip install --target ./.vendor PySide6"
    ) from exc

from boxing_game.models import CareerState
from boxing_game.modules.amateur_circuit import (
    apply_fight_result,
    current_tier,
    generate_opponent,
    pro_readiness_status,
)
from boxing_game.modules.attribute_engine import training_gain
from boxing_game.modules.career_clock import advance_month
from boxing_game.modules.experience_engine import boxer_experience_profile, total_career_fights
from boxing_game.modules.fight_sim_engine import simulate_amateur_fight, simulate_pro_fight
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import (
    apply_pro_fight_result,
    ensure_rankings,
    format_purse_breakdown,
    generate_pro_opponent,
    offer_purse,
    pro_tier,
    rankings_snapshot,
    turn_pro,
)
from boxing_game.modules.rating_engine import boxer_overall_rating
from boxing_game.modules.savegame import (
    SaveMetadata,
    SavegameError,
    delete_state,
    duplicate_state,
    list_saves,
    list_save_metadata,
    load_state,
    rename_state,
    save_state,
)
from boxing_game.rules_registry import load_rule_set


class BoxingGameWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Boxing Career Manager")
        self.resize(1080, 760)

        self.rng = random.Random()
        self.state: CareerState | None = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.menu_page = self._build_menu_page()
        self.create_page = self._build_create_page()
        self.career_page = self._build_career_page()
        self.rankings_page = self._build_rankings_page()
        self.manage_saves_page = self._build_manage_saves_page()

        self.stack.addWidget(self.menu_page)
        self.stack.addWidget(self.create_page)
        self.stack.addWidget(self.career_page)
        self.stack.addWidget(self.rankings_page)
        self.stack.addWidget(self.manage_saves_page)
        self.stack.setCurrentWidget(self.menu_page)

    def _build_menu_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        title = QLabel("Text Boxing Career")
        title.setStyleSheet("font-size: 30px; font-weight: 700;")
        subtitle = QLabel("Phase 2 GUI: Amateur + Pro Career")
        subtitle.setStyleSheet("font-size: 15px; color: #4f5d75;")

        button_col = QVBoxLayout()
        button_col.setSpacing(12)

        new_button = QPushButton("New Career")
        new_button.clicked.connect(self._show_create_page)
        load_button = QPushButton("Load Career")
        load_button.clicked.connect(self._load_career)
        manage_button = QPushButton("Manage Saves")
        manage_button.clicked.connect(self._show_manage_saves_page)
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self.close)

        for button in (new_button, load_button, manage_button, quit_button):
            button.setMinimumHeight(44)
            button_col.addWidget(button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        layout.addLayout(button_col)
        layout.addStretch(1)
        return page

    def _build_create_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(18)

        title = QLabel("Create Boxer")
        title.setStyleSheet("font-size: 26px; font-weight: 700;")
        layout.addWidget(title)

        form_card = QFrame()
        form_card.setFrameShape(QFrame.Shape.StyledPanel)
        form_card.setStyleSheet("QFrame { padding: 8px; }")
        form_layout = QFormLayout(form_card)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(16)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter boxer name")

        self.stance_input = QComboBox()
        self.stance_input.addItems(["orthodox", "southpaw"])

        self.height_ft_input = QSpinBox()
        self.height_ft_input.setRange(4, 7)
        self.height_ft_input.setValue(5)

        self.height_in_input = QSpinBox()
        self.height_in_input.setRange(0, 11)
        self.height_in_input.setValue(10)

        self.weight_input = QSpinBox()
        self.weight_input.setRange(90, 300)
        self.weight_input.setValue(147)

        self.nationality_input = QLineEdit()
        self.nationality_input.setText("USA")

        form_layout.addRow("Name", self.name_input)
        form_layout.addRow("Stance", self.stance_input)
        form_layout.addRow("Height (ft)", self.height_ft_input)
        form_layout.addRow("Height (in)", self.height_in_input)
        form_layout.addRow("Weight (lbs)", self.weight_input)
        form_layout.addRow("Nationality", self.nationality_input)

        action_row = QHBoxLayout()
        create_button = QPushButton("Create Career")
        create_button.setMinimumHeight(42)
        create_button.clicked.connect(self._create_career)

        back_button = QPushButton("Back")
        back_button.setMinimumHeight(42)
        back_button.clicked.connect(self._show_menu_page)

        action_row.addWidget(create_button)
        action_row.addWidget(back_button)

        layout.addWidget(form_card)
        layout.addLayout(action_row)
        layout.addStretch(1)
        return page

    def _build_career_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)

        self.career_header = QLabel("Career")
        self.career_header.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.career_summary = QLabel("")
        self.career_summary.setWordWrap(True)
        self.career_summary.setStyleSheet("font-size: 14px; color: #2d3a50;")
        self.career_status = QLabel("")
        self.career_status.setWordWrap(True)
        self.career_status.setStyleSheet("font-size: 13px; color: #4f5d75;")

        root.addWidget(self.career_header)
        root.addWidget(self.career_summary)
        root.addWidget(self.career_status)

        content_row = QHBoxLayout()
        content_row.setSpacing(12)

        stats_and_train = QHBoxLayout()
        stats_and_train.setSpacing(8)

        self.stats_view = QPlainTextEdit()
        self.stats_view.setReadOnly(True)
        self.stats_view.setPlaceholderText("Stats")
        stats_and_train.addWidget(self.stats_view, 3)

        self.training_panel = QFrame()
        self.training_panel.setFrameShape(QFrame.Shape.StyledPanel)
        training_layout = QVBoxLayout(self.training_panel)
        training_layout.setContentsMargins(8, 8, 8, 8)
        training_layout.setSpacing(6)

        training_title = QLabel("Train Focus")
        training_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        training_hint = QLabel("Click a stat to train it for one month.")
        training_hint.setWordWrap(True)
        training_hint.setStyleSheet("font-size: 12px; color: #4f5d75;")

        training_layout.addWidget(training_title)
        training_layout.addWidget(training_hint)

        self.training_focus_buttons: dict[str, QPushButton] = {}
        focuses = [str(item) for item in load_rule_set("attribute_model")["training_focuses"]]
        for focus in focuses:
            button = QPushButton(focus.replace("_", " ").title())
            button.setMinimumHeight(32)
            button.clicked.connect(
                lambda _checked=False, selected_focus=focus: self._train_focus(selected_focus)
            )
            self.training_focus_buttons[focus] = button
            training_layout.addWidget(button)

        training_layout.addStretch(1)
        stats_and_train.addWidget(self.training_panel, 2)

        self.history_view = QPlainTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setPlaceholderText("Fight history")

        content_row.addLayout(stats_and_train, 2)
        content_row.addWidget(self.history_view, 1)
        root.addLayout(content_row, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.amateur_fight_button = QPushButton("Amateur Fight")
        self.amateur_fight_button.clicked.connect(self._take_amateur_fight)
        self.turn_pro_button = QPushButton("Turn Pro")
        self.turn_pro_button.clicked.connect(self._turn_pro)
        self.pro_fight_button = QPushButton("Pro Fight")
        self.pro_fight_button.clicked.connect(self._take_pro_fight)
        rankings_button = QPushButton("Rankings")
        rankings_button.clicked.connect(self._show_rankings_page)
        rest_button = QPushButton("Rest Month")
        rest_button.clicked.connect(self._rest_month)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_career)
        back_button = QPushButton("Main Menu")
        back_button.clicked.connect(self._show_menu_page)

        for button in (
            self.amateur_fight_button,
            self.turn_pro_button,
            self.pro_fight_button,
            rankings_button,
            rest_button,
            save_button,
            back_button,
        ):
            button.setMinimumHeight(40)
            button_row.addWidget(button)

        root.addLayout(button_row)

        self.event_log = QPlainTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(500)
        self.event_log.setPlaceholderText("Event log")
        root.addWidget(self.event_log, 1)

        return page

    def _build_rankings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        self.rankings_header = QLabel("Rankings")
        self.rankings_header.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.rankings_subtitle = QLabel("")
        self.rankings_subtitle.setWordWrap(True)
        self.rankings_subtitle.setStyleSheet("font-size: 13px; color: #4f5d75;")

        layout.addWidget(self.rankings_header)
        layout.addWidget(self.rankings_subtitle)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.rankings_org_combo = QComboBox()
        self.rankings_org_combo.addItems(["WBC", "WBA", "IBF", "WBO"])
        self.rankings_org_combo.currentTextChanged.connect(self._refresh_rankings_page)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._refresh_rankings_page)

        back_button = QPushButton("Back to Career")
        back_button.clicked.connect(self._show_career_page)

        controls.addWidget(QLabel("Organization"))
        controls.addWidget(self.rankings_org_combo)
        controls.addWidget(refresh_button)
        controls.addStretch(1)
        controls.addWidget(back_button)
        layout.addLayout(controls)

        self.rankings_view = QPlainTextEdit()
        self.rankings_view.setReadOnly(True)
        self.rankings_view.setPlaceholderText("Rankings will appear here.")
        layout.addWidget(self.rankings_view, 1)
        return page

    def _build_manage_saves_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        self.manage_saves_header = QLabel("Manage Saves")
        self.manage_saves_header.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.manage_saves_subtitle = QLabel("")
        self.manage_saves_subtitle.setWordWrap(True)
        self.manage_saves_subtitle.setStyleSheet("font-size: 13px; color: #4f5d75;")

        layout.addWidget(self.manage_saves_header)
        layout.addWidget(self.manage_saves_subtitle)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Save Slot"))
        self.manage_saves_slot_combo = QComboBox()
        self.manage_saves_slot_combo.currentTextChanged.connect(self._refresh_manage_save_details)
        controls.addWidget(self.manage_saves_slot_combo, 1)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._refresh_manage_saves_page)
        controls.addWidget(refresh_button)

        back_button = QPushButton("Back to Menu")
        back_button.clicked.connect(self._show_menu_page)
        controls.addWidget(back_button)
        layout.addLayout(controls)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.manage_load_button = QPushButton("Load")
        self.manage_load_button.clicked.connect(self._load_selected_save_from_manage)
        self.manage_rename_button = QPushButton("Rename")
        self.manage_rename_button.clicked.connect(self._rename_selected_save_from_manage)
        self.manage_duplicate_button = QPushButton("Duplicate")
        self.manage_duplicate_button.clicked.connect(self._duplicate_selected_save_from_manage)
        self.manage_delete_button = QPushButton("Delete")
        self.manage_delete_button.clicked.connect(self._delete_selected_save_from_manage)

        for button in (
            self.manage_load_button,
            self.manage_rename_button,
            self.manage_duplicate_button,
            self.manage_delete_button,
        ):
            button.setMinimumHeight(40)
            action_row.addWidget(button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.manage_saves_details_view = QPlainTextEdit()
        self.manage_saves_details_view.setReadOnly(True)
        self.manage_saves_details_view.setPlaceholderText("Save metadata will appear here.")
        layout.addWidget(self.manage_saves_details_view, 1)

        self._manage_save_by_slot: dict[str, SaveMetadata] = {}
        return page

    def _show_menu_page(self) -> None:
        self.stack.setCurrentWidget(self.menu_page)

    def _show_create_page(self) -> None:
        self.stack.setCurrentWidget(self.create_page)

    def _show_career_page(self) -> None:
        if self.state is None:
            return
        self._refresh_career_view()
        self.stack.setCurrentWidget(self.career_page)

    def _show_rankings_page(self) -> None:
        if self.state is None:
            return
        self._refresh_rankings_page()
        self.stack.setCurrentWidget(self.rankings_page)

    def _show_manage_saves_page(self) -> None:
        self._refresh_manage_saves_page()
        self.stack.setCurrentWidget(self.manage_saves_page)

    def _set_state(self, state: CareerState) -> None:
        self.state = state
        self._refresh_career_view()
        self.stack.setCurrentWidget(self.career_page)

    def _advance_month(self, months: int = 1) -> None:
        if self.state is None:
            return
        for event in advance_month(self.state, months=months):
            self._append_log(event)

    def _append_log(self, message: str) -> None:
        self.event_log.appendPlainText(message)

    def _format_saved_at(self, saved_at: str) -> str:
        if not saved_at:
            return "Unknown"
        try:
            parsed = datetime.fromisoformat(saved_at)
        except ValueError:
            return saved_at
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local_dt = parsed.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    def _selected_manage_slot(self) -> str:
        return self.manage_saves_slot_combo.currentText().strip()

    def _refresh_manage_saves_page(self, preferred_slot: str | None = None) -> None:
        previous_slot = self._selected_manage_slot()
        metadata = list_save_metadata()
        self._manage_save_by_slot = {item.slot: item for item in metadata}

        self.manage_saves_slot_combo.blockSignals(True)
        self.manage_saves_slot_combo.clear()
        for item in metadata:
            self.manage_saves_slot_combo.addItem(item.slot)

        chosen = preferred_slot.strip() if preferred_slot else ""
        if not chosen:
            chosen = previous_slot
        if chosen and chosen in self._manage_save_by_slot:
            idx = self.manage_saves_slot_combo.findText(chosen)
            if idx >= 0:
                self.manage_saves_slot_combo.setCurrentIndex(idx)
        self.manage_saves_slot_combo.blockSignals(False)

        count = len(metadata)
        self.manage_saves_subtitle.setText(f"Total save slots: {count}")
        self._refresh_manage_save_details()

    def _refresh_manage_save_details(self, *_: object) -> None:
        slot = self._selected_manage_slot()
        meta = self._manage_save_by_slot.get(slot)
        if meta is None:
            self.manage_load_button.setEnabled(False)
            self.manage_rename_button.setEnabled(False)
            self.manage_duplicate_button.setEnabled(False)
            self.manage_delete_button.setEnabled(False)
            self.manage_saves_details_view.setPlainText("No saves available.")
            return

        self.manage_load_button.setEnabled(meta.is_valid)
        self.manage_rename_button.setEnabled(True)
        self.manage_duplicate_button.setEnabled(True)
        self.manage_delete_button.setEnabled(True)

        stage = "Pro" if meta.is_pro else "Amateur"
        if meta.is_pro is None:
            stage = "Unknown"
        lines = [
            f"Slot: {meta.slot}",
            f"Last Played: {self._format_saved_at(meta.saved_at)}",
            f"Version: {meta.version if meta.version is not None else 'Unknown'}",
            f"Boxer: {meta.boxer_name or 'Unknown'}",
            f"Age: {meta.age if meta.age is not None else 'Unknown'}",
            f"Division: {meta.division or 'Unknown'}",
            f"Career Calendar: Month {meta.month if meta.month is not None else '?'}"
            f", Year {meta.year if meta.year is not None else '?'}",
            f"Stage: {stage}",
            f"Path: {meta.path}",
        ]
        if not meta.is_valid:
            lines.extend(["", f"Save Error: {meta.error or 'Unknown metadata error'}"])
        self.manage_saves_details_view.setPlainText("\n".join(lines))

    def _load_selected_save_from_manage(self) -> None:
        slot = self._selected_manage_slot()
        if not slot:
            return
        try:
            state = load_state(slot)
        except SavegameError as exc:
            QMessageBox.critical(self, "Load Failed", str(exc))
            return

        if state.pro_career.is_active:
            ensure_rankings(state)

        self._set_state(state)
        self.event_log.clear()
        self._append_log(f"Loaded save slot: {slot}")

    def _rename_selected_save_from_manage(self) -> None:
        slot = self._selected_manage_slot()
        if not slot:
            return

        suggested = f"{slot}_renamed"
        new_slot, ok = QInputDialog.getText(
            self,
            "Rename Save",
            "New slot name:",
            text=suggested,
        )
        if not ok:
            return

        target = new_slot.strip()
        if not target:
            QMessageBox.information(self, "Rename Save", "New slot name is required.")
            return

        try:
            rename_state(slot, target)
        except SavegameError as exc:
            QMessageBox.critical(self, "Rename Failed", str(exc))
            return

        QMessageBox.information(self, "Rename Save", f"Renamed '{slot}' to '{target}'.")
        self._append_log(f"Renamed save slot: {slot} -> {target}")
        self._refresh_manage_saves_page(preferred_slot=target)

    def _duplicate_selected_save_from_manage(self) -> None:
        slot = self._selected_manage_slot()
        if not slot:
            return

        suggested = f"{slot}_copy"
        new_slot, ok = QInputDialog.getText(
            self,
            "Duplicate Save",
            "Duplicate into slot:",
            text=suggested,
        )
        if not ok:
            return

        target = new_slot.strip()
        if not target:
            QMessageBox.information(self, "Duplicate Save", "Destination slot name is required.")
            return

        try:
            duplicate_state(slot, target)
        except SavegameError as exc:
            QMessageBox.critical(self, "Duplicate Failed", str(exc))
            return

        QMessageBox.information(self, "Duplicate Save", f"Created duplicate slot '{target}'.")
        self._append_log(f"Duplicated save slot: {slot} -> {target}")
        self._refresh_manage_saves_page(preferred_slot=target)

    def _delete_selected_save_from_manage(self) -> None:
        slot = self._selected_manage_slot()
        if not slot:
            return

        confirm = QMessageBox.question(
            self,
            "Delete Save",
            f"Delete save slot '{slot}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_state(slot)
        except SavegameError as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))
            return
        QMessageBox.information(self, "Delete Save", f"Deleted save slot: {slot}")
        self._append_log(f"Deleted save slot: {slot}")
        self._refresh_manage_saves_page()

    def _refresh_rankings_page(self, *_: object) -> None:
        if self.state is None:
            return

        boxer = self.state.boxer
        self.rankings_header.setText(f"Rankings | {boxer.profile.name}")

        if not self.state.pro_career.is_active:
            readiness = pro_readiness_status(self.state)
            self.rankings_subtitle.setText("Turn pro to unlock sanctioning-body rankings.")
            self.rankings_view.setPlainText(
                (
                    "Not ranked yet.\n\n"
                    "Pro gate:\n"
                    f"Age {readiness.current_age}/{readiness.min_age}\n"
                    f"Fights {readiness.current_fights}/{readiness.min_fights}\n"
                    f"Points {readiness.current_points}/{readiness.min_points}\n"
                )
            )
            return

        ensure_rankings(self.state)
        org_name = self.rankings_org_combo.currentText().strip().upper()
        entries = rankings_snapshot(self.state, org_name, top_n=15)

        self.rankings_subtitle.setText(
            f"Division: {boxer.division} | Focus Organization: {self.state.pro_career.organization_focus}"
        )

        lines = [f"{org_name} Rankings", ""]
        for entry in entries:
            rank_label = f"#{entry.rank}" if entry.rank > 0 else "NR"
            marker = " <= YOU" if entry.is_player else ""
            lines.append(
                (
                    f"{rank_label:>4} | OVR {entry.rating:>2} | "
                    f"{entry.name} | {entry.wins}-{entry.losses}-{entry.draws}{marker}"
                )
            )
        self.rankings_view.setPlainText("\n".join(lines))

    def _create_career(self) -> None:
        name = self.name_input.text().strip()
        stance = self.stance_input.currentText().strip().lower()
        height_ft = int(self.height_ft_input.value())
        height_in = int(self.height_in_input.value())
        weight_lbs = int(self.weight_input.value())
        nationality = self.nationality_input.text().strip() or "USA"

        if not name:
            QMessageBox.warning(self, "Invalid Input", "Name is required.")
            return

        try:
            boxer = create_boxer(
                name=name,
                stance=stance,
                height_ft=height_ft,
                height_in=height_in,
                weight_lbs=weight_lbs,
                nationality=nationality,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Create Career Failed", str(exc))
            return

        state = CareerState(boxer=boxer)
        state.amateur_progress.tier = "novice"
        self._set_state(state)
        self.event_log.clear()
        self._append_log(
            f"Career started for {boxer.profile.name} at age {boxer.profile.age} in {boxer.division}."
        )

    def _load_career(self) -> None:
        while True:
            slots = list_saves()
            if not slots:
                QMessageBox.information(self, "Load Career", "No saves found.")
                return

            slot, ok = QInputDialog.getItem(
                self,
                "Load Career",
                "Choose save slot:",
                slots,
                0,
                False,
            )
            if not ok or not slot:
                return

            action, action_ok = QInputDialog.getItem(
                self,
                "Save Action",
                f"Choose action for '{slot}':",
                ["Load", "Delete"],
                0,
                False,
            )
            if not action_ok or not action:
                return

            if action == "Load":
                try:
                    state = load_state(slot)
                except SavegameError as exc:
                    QMessageBox.critical(self, "Load Failed", str(exc))
                    return

                if state.pro_career.is_active:
                    ensure_rankings(state)

                self._set_state(state)
                self.event_log.clear()
                self._append_log(f"Loaded save slot: {slot}")
                return

            confirm = QMessageBox.question(
                self,
                "Delete Save",
                f"Delete save slot '{slot}'? This cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                continue

            try:
                delete_state(slot)
            except SavegameError as exc:
                QMessageBox.critical(self, "Delete Failed", str(exc))
                return
            QMessageBox.information(self, "Delete Save", f"Deleted save slot: {slot}")
            self._append_log(f"Deleted save slot: {slot}")

    def _save_career(self) -> None:
        if self.state is None:
            return

        default_slot = self.state.boxer.profile.name.lower().replace(" ", "_")
        slot, ok = QInputDialog.getText(
            self,
            "Save Career",
            "Save slot (letters, numbers, - or _):",
            text=default_slot,
        )
        if not ok:
            return

        normalized = slot.strip() or default_slot
        try:
            path = save_state(self.state, normalized)
        except SavegameError as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return

        self._append_log(f"Saved career to {path.name}")
        QMessageBox.information(self, "Save Career", f"Saved to {path}")

    def _train_focus(self, focus: str) -> None:
        if self.state is None:
            return

        focuses = {str(item) for item in load_rule_set("attribute_model")["training_focuses"]}
        if focus not in focuses:
            QMessageBox.information(self, "Training", f"Unknown training focus: {focus}")
            return

        self.state.boxer.stats = training_gain(self.state.boxer.stats, focus)
        self.state.boxer.fatigue = min(12, self.state.boxer.fatigue + 1)
        self._advance_month(1)
        self._refresh_career_view()
        self._append_log(f"Training month complete. Focus: {focus}.")

    def _rest_month(self) -> None:
        if self.state is None:
            return
        self.state.boxer.fatigue = max(0, self.state.boxer.fatigue - 3)
        self._advance_month(1)
        self._refresh_career_view()
        self._append_log("Rest month complete. Fatigue reduced.")

    def _take_amateur_fight(self) -> None:
        if self.state is None:
            return
        if self.state.pro_career.is_active:
            QMessageBox.information(self, "Amateur Fight", "Amateur bouts are unavailable after turning pro.")
            return

        tier = current_tier(self.state)
        opponent = generate_opponent(self.state, rng=self.rng)

        prompt = (
            f"Opponent: {opponent.name}\n"
            f"Tier: {tier['name']} | Rating: {opponent.rating}\n"
            f"Record: {opponent.record.wins}-{opponent.record.losses}-{opponent.record.draws} (KO {opponent.record.kos})\n"
            f"Height/Weight: {opponent.height_ft}'{opponent.height_in}\" / {opponent.weight_lbs} lbs\n\n"
            "Accept fight?"
        )

        decision = QMessageBox.question(
            self,
            "Amateur Fight Offer",
            prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if decision != QMessageBox.StandardButton.Yes:
            self._append_log("Fight offer declined.")
            return

        result = simulate_amateur_fight(
            self.state.boxer,
            opponent,
            rounds=int(tier["rounds"]),
            rng=self.rng,
        )
        xp_before = self.state.boxer.experience_points
        apply_fight_result(self.state, opponent, result)
        xp_gain = self.state.boxer.experience_points - xp_before
        experience = boxer_experience_profile(
            self.state.boxer,
            pro_record=self.state.pro_career.record,
        )
        self._advance_month(1)
        self._refresh_career_view()

        scorecard_lines = "\n".join(result.scorecards) if result.scorecards else "No scorecards (stoppage)."
        round_lines = "\n".join(result.round_log)
        outcome = (
            f"Winner: {result.winner}\n"
            f"Method: {result.method}\n"
            f"Rounds Completed: {result.rounds_completed}\n\n"
            f"Experience Gained: +{xp_gain} XP ({experience.title})\n\n"
            f"Scorecards:\n{scorecard_lines}\n\n"
            f"Round Log:\n{round_lines}"
        )

        QMessageBox.information(self, "Fight Result", outcome)
        self._append_log(
            (
                f"Fight complete vs {opponent.name}: {result.method} ({result.winner}) | "
                f"+{xp_gain} XP ({experience.title})"
            )
        )

    def _turn_pro(self) -> None:
        if self.state is None:
            return

        try:
            details = turn_pro(self.state, rng=self.rng)
        except ValueError as exc:
            QMessageBox.information(self, "Turn Pro", str(exc))
            return

        self._refresh_career_view()
        QMessageBox.information(
            self,
            "Turned Pro",
            (
                f"Promoter: {details['promoter']}\n"
                f"Focus Organization: {details['organization_focus']}\n"
                f"Signing Bonus: ${int(details['signing_bonus']):,}"
            ),
        )
        self._append_log(
            (
                f"Turned pro under {details['promoter']} | "
                f"Focus: {details['organization_focus']} | Bonus ${int(details['signing_bonus']):,}"
            )
        )

    def _take_pro_fight(self) -> None:
        if self.state is None:
            return
        if not self.state.pro_career.is_active:
            QMessageBox.information(self, "Pro Fight", "Turn pro first.")
            return

        tier = pro_tier(self.state)
        opponent = generate_pro_opponent(self.state, rng=self.rng)
        purse = offer_purse(self.state, opponent, rng=self.rng)

        prompt = (
            f"Opponent: {opponent.name}\n"
            f"Tier: {tier['name']} | Rating: {opponent.rating}\n"
            f"Record: {opponent.record.wins}-{opponent.record.losses}-{opponent.record.draws} (KO {opponent.record.kos})\n"
            f"Height/Weight: {opponent.height_ft}'{opponent.height_in}\" / {opponent.weight_lbs} lbs\n\n"
            f"Purse: {format_purse_breakdown(purse)}\n"
            f"Total Expenses: ${purse['total_expenses']:,.2f}\n"
            "Accept pro fight?"
        )

        decision = QMessageBox.question(
            self,
            "Pro Fight Offer",
            prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if decision != QMessageBox.StandardButton.Yes:
            self._append_log("Pro fight offer declined.")
            return

        result = simulate_pro_fight(
            self.state.boxer,
            opponent,
            rounds=int(tier["rounds"]),
            rng=self.rng,
        )
        xp_before = self.state.boxer.experience_points
        new_rank = apply_pro_fight_result(self.state, opponent, result, purse)
        xp_gain = self.state.boxer.experience_points - xp_before
        experience = boxer_experience_profile(
            self.state.boxer,
            pro_record=self.state.pro_career.record,
        )
        self._advance_month(1)
        self._refresh_career_view()

        rank_label = f"#{new_rank}" if new_rank is not None else "Unranked"
        scorecard_lines = "\n".join(result.scorecards) if result.scorecards else "No scorecards (stoppage)."
        round_lines = "\n".join(result.round_log)
        outcome = (
            f"Winner: {result.winner}\n"
            f"Method: {result.method}\n"
            f"Rounds Completed: {result.rounds_completed}\n"
            f"{self.state.pro_career.organization_focus} Rank: {rank_label}\n"
            f"Gross Purse: ${purse['gross']:,.2f}\n"
            f"Total Expenses: ${purse['total_expenses']:,.2f}\n"
            f"Net Purse Added: ${purse['net']:,.2f}\n\n"
            f"Experience Gained: +{xp_gain} XP ({experience.title})\n\n"
            f"Scorecards:\n{scorecard_lines}\n\n"
            f"Round Log:\n{round_lines}"
        )

        QMessageBox.information(self, "Pro Fight Result", outcome)
        self._append_log(
            (
                f"Pro fight vs {opponent.name}: {result.method} ({result.winner}) | "
                f"Net ${purse['net']:,.2f} | Rank {rank_label} | +{xp_gain} XP ({experience.title})"
            )
        )

    def _refresh_career_view(self) -> None:
        if self.state is None:
            return

        boxer = self.state.boxer
        is_pro = self.state.pro_career.is_active
        stage = "pro" if is_pro else "amateur"
        overall_rating = boxer_overall_rating(
            boxer,
            stage=stage,
            pro_record=self.state.pro_career.record,
        )
        experience = boxer_experience_profile(
            boxer,
            pro_record=self.state.pro_career.record,
        )
        fights_total = total_career_fights(boxer, pro_record=self.state.pro_career.record)
        amateur_record = boxer.record
        pro_record = self.state.pro_career.record

        if is_pro:
            tier = pro_tier(self.state)
            tier_label = f"pro-{tier['name']}"
            main_record = (
                f"{pro_record.wins}-{pro_record.losses}-{pro_record.draws} (KO {pro_record.kos})"
            )
        else:
            tier = current_tier(self.state)
            tier_label = tier["name"]
            main_record = (
                f"{amateur_record.wins}-{amateur_record.losses}-{amateur_record.draws} "
                f"(KO {amateur_record.kos})"
            )

        readiness = pro_readiness_status(self.state)
        pro_ready_flag = "Yes" if readiness.is_ready else "No"
        self.amateur_fight_button.setEnabled(not is_pro)
        self.turn_pro_button.setEnabled((not is_pro) and readiness.is_ready)
        self.pro_fight_button.setEnabled(is_pro)

        self.career_header.setText(
            (
                f"{boxer.profile.name} | Age {boxer.profile.age} | "
                f"Month {self.state.month}, Year {self.state.year}"
            )
        )
        self.career_summary.setText(
            f"Division: {boxer.division} | Tier: {tier_label} | Active Record: {main_record}"
        )
        self.career_status.setText(
            (
                f"Amateur Points: {boxer.amateur_points} | Popularity: {boxer.popularity} | "
                f"Fatigue: {boxer.fatigue} | Experience: {experience.points} XP ({experience.title}) | "
                f"Pro Ready: {pro_ready_flag} | "
                f"Gate Age {readiness.current_age}/{readiness.min_age}, "
                f"Fights {readiness.current_fights}/{readiness.min_fights}, "
                f"Points {readiness.current_points}/{readiness.min_points}"
            )
        )

        stats_lines = [
            f"Career Stage: {'Pro' if is_pro else 'Amateur'}",
            f"Age: {boxer.profile.age}",
            f"Stance: {boxer.profile.stance}",
            (
                "Height/Weight: "
                f"{boxer.profile.height_ft}'{boxer.profile.height_in}\" / {boxer.profile.weight_lbs} lbs"
            ),
            f"Reach: {boxer.profile.reach_in} in",
            f"Overall Rating: {overall_rating}",
            (
                f"Experience: {experience.points} XP | "
                f"Level {experience.level} ({experience.title}) | "
                f"Fight Bonus +{experience.fight_bonus:.2f}"
            ),
            (
                "Next Level At: "
                f"{experience.next_level_points} XP"
                if experience.next_level_points is not None
                else "Next Level At: MAX"
            ),
            f"Career Fights: {fights_total}",
            "",
            (
                "Amateur Record: "
                f"{amateur_record.wins}-{amateur_record.losses}-{amateur_record.draws} "
                f"(KO {amateur_record.kos})"
            ),
            (
                "Pro Record: "
                f"{pro_record.wins}-{pro_record.losses}-{pro_record.draws} "
                f"(KO {pro_record.kos})"
            ),
            "",
            (
                f"Pro Balance: ${self.state.pro_career.purse_balance:,.2f} | "
                f"Total Earnings: ${self.state.pro_career.total_earnings:,.2f}"
            ),
            f"Promoter: {self.state.pro_career.promoter or 'N/A'}",
            f"Focus Org: {self.state.pro_career.organization_focus}",
            "Rankings:",
        ]
        if self.state.pro_career.rankings:
            for org_name, rank in self.state.pro_career.rankings.items():
                rank_label = f"#{rank}" if rank is not None else "Unranked"
                stats_lines.append(f"  {org_name}: {rank_label}")
        else:
            stats_lines.append("  N/A")

        stats_lines.extend([
            "",
            "Stats:",
        ])
        for key, value in boxer.stats.to_dict().items():
            stats_lines.append(f"  {key}: {value}")
        self.stats_view.setPlainText("\n".join(stats_lines))

        if not self.state.history:
            self.history_view.setPlainText("No fights yet.")
            return

        history_lines = []
        for entry in self.state.history[-12:]:
            purse_label = f" | purse ${entry.purse:,.2f}" if entry.stage == "pro" else ""
            history_lines.append(
                (
                    f"[{entry.stage}] vs {entry.opponent_name} (rating {entry.opponent_rating}) | "
                    f"{entry.result.method} | winner: {entry.result.winner}{purse_label}"
                )
            )
        self.history_view.setPlainText("\n".join(history_lines))


def run_gui() -> int:
    app = QApplication(sys.argv)
    window = BoxingGameWindow()
    window.show()
    return app.exec()


def main() -> None:
    raise SystemExit(run_gui())


if __name__ == "__main__":
    main()
