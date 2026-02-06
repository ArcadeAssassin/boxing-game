from __future__ import annotations

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
    pro_ready,
)
from boxing_game.modules.attribute_engine import training_gain
from boxing_game.modules.career_clock import advance_month
from boxing_game.modules.fight_sim_engine import simulate_amateur_fight, simulate_pro_fight
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import (
    apply_pro_fight_result,
    ensure_rankings,
    format_purse_breakdown,
    generate_pro_opponent,
    offer_purse,
    pro_tier,
    turn_pro,
)
from boxing_game.modules.savegame import SavegameError, list_saves, load_state, save_state
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

        self.stack.addWidget(self.menu_page)
        self.stack.addWidget(self.create_page)
        self.stack.addWidget(self.career_page)
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
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self.close)

        for button in (new_button, load_button, quit_button):
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

        self.stats_view = QPlainTextEdit()
        self.stats_view.setReadOnly(True)
        self.stats_view.setPlaceholderText("Stats")

        self.history_view = QPlainTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setPlaceholderText("Fight history")

        content_row.addWidget(self.stats_view, 1)
        content_row.addWidget(self.history_view, 1)
        root.addLayout(content_row, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        train_button = QPushButton("Train")
        train_button.clicked.connect(self._train)
        self.amateur_fight_button = QPushButton("Amateur Fight")
        self.amateur_fight_button.clicked.connect(self._take_amateur_fight)
        self.turn_pro_button = QPushButton("Turn Pro")
        self.turn_pro_button.clicked.connect(self._turn_pro)
        self.pro_fight_button = QPushButton("Pro Fight")
        self.pro_fight_button.clicked.connect(self._take_pro_fight)
        rest_button = QPushButton("Rest Month")
        rest_button.clicked.connect(self._rest_month)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_career)
        back_button = QPushButton("Main Menu")
        back_button.clicked.connect(self._show_menu_page)

        for button in (
            train_button,
            self.amateur_fight_button,
            self.turn_pro_button,
            self.pro_fight_button,
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

    def _show_menu_page(self) -> None:
        self.stack.setCurrentWidget(self.menu_page)

    def _show_create_page(self) -> None:
        self.stack.setCurrentWidget(self.create_page)

    def _show_career_page(self) -> None:
        if self.state is None:
            return
        self._refresh_career_view()
        self.stack.setCurrentWidget(self.career_page)

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

    def _train(self) -> None:
        if self.state is None:
            return

        focuses = list(load_rule_set("attribute_model")["training_focuses"])
        focus, ok = QInputDialog.getItem(
            self,
            "Training",
            "Choose focus:",
            focuses,
            0,
            False,
        )
        if not ok or not focus:
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
        apply_fight_result(self.state, opponent, result)
        self._advance_month(1)
        self._refresh_career_view()

        scorecard_lines = "\n".join(result.scorecards) if result.scorecards else "No scorecards (stoppage)."
        round_lines = "\n".join(result.round_log)
        outcome = (
            f"Winner: {result.winner}\n"
            f"Method: {result.method}\n"
            f"Rounds Completed: {result.rounds_completed}\n\n"
            f"Scorecards:\n{scorecard_lines}\n\n"
            f"Round Log:\n{round_lines}"
        )

        QMessageBox.information(self, "Fight Result", outcome)
        self._append_log(f"Fight complete vs {opponent.name}: {result.method} ({result.winner}).")

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
        new_rank = apply_pro_fight_result(self.state, opponent, result, purse)
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
            f"Scorecards:\n{scorecard_lines}\n\n"
            f"Round Log:\n{round_lines}"
        )

        QMessageBox.information(self, "Pro Fight Result", outcome)
        self._append_log(
            (
                f"Pro fight vs {opponent.name}: {result.method} ({result.winner}) | "
                f"Net ${purse['net']:,.2f} | Rank {rank_label}"
            )
        )

    def _refresh_career_view(self) -> None:
        if self.state is None:
            return

        boxer = self.state.boxer
        is_pro = self.state.pro_career.is_active
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

        pro_ready_flag = "Yes" if pro_ready(self.state) else "No"
        self.amateur_fight_button.setEnabled(not is_pro)
        self.turn_pro_button.setEnabled((not is_pro) and pro_ready(self.state))
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
                f"Fatigue: {boxer.fatigue} | Pro Ready: {pro_ready_flag}"
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
