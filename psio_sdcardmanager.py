#!/usr/bin/env python3
#
#  PSX-SDCard Manager!
#
#  Copyright (C) 2024 Rafa Monteiro
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# System imports
import logging
import sys
from json import load, dumps
from os.path import join, dirname, abspath
from sys import argv

from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, QProgressBar, QTreeView, QCheckBox, QFrame,
                             QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QScrollBar, QHeaderView, QLineEdit)
from pathlib2 import Path

# Local imports
from psio_sdcardmanager.cue2cu2 import set_cu2_error_log_path
from psio_sdcardmanager.gamehandler import GameHandler

CURRENT_REVISION = 0.1
PROGRESS_STATUS = 'Status:'
logger = logging.getLogger(__name__)
covers_path = None

# Get the directory paths based on the scripts location
script_root_dir = Path(abspath(dirname(argv[0])))
covers_path = join(dirname(script_root_dir), 'covers')
error_log_file = join(dirname(script_root_dir), 'errors.txt')

CONFIG_FILE_PATH = join(script_root_dir, 'config')

# Set the error log path for all of the scripts
set_cu2_error_log_path(error_log_file)


# *************************************************
# Run the GUI
# *************************************************


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.treeview_game_list = QTreeView()
        self.checkbox_add_art = QCheckBox('Add Cover Art').setEnabled(False)
        self.checkbox_auto_rename = QCheckBox('Auto Rename').setEnabled(False)
        self.checkbox_create_multi_disc = QCheckBox('Create Multi-Disc').setEnabled(False)
        self.checkbox_limit_name = QCheckBox('Fix Invalid Name').setEnabled(False)
        self.checkbox_generate_cu2 = QCheckBox('CU2 For All').setEnabled(False)
        self.checkbox_merge_bin = QCheckBox('Merge Bin Files').setEnabled(False)
        self.setWindowTitle(f'PSIO SDCARD Manager v{CURRENT_REVISION}')
        self.setGeometry(100, 100, 800, 710)
        # self.setFixedSize(800, 710)  # Disable resizing
        # Button Declaration
        self.button_src_browse = QPushButton('Browse')
        self.button_src_scan = QPushButton('Scan')
        self.button_start = QPushButton('Start').setEnabled(False)
        self.game_handler = GameHandler()
        self.game_list = []
        self.initUI()

    def initUI(self):
        self.create_menu()
        self.create_widgets()

    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('File')

        file_menu.addSeparator()
        file_menu.addAction('Exit', self.close)

        help_menu = menubar.addMenu('Help')
        help_menu.addAction('About')

    def create_widgets(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Browse frame
        browse_frame = QFrame()
        browse_frame.setFrameShape(QFrame.Shape.Panel)
        main_layout.addWidget(browse_frame)

        browse_layout = QHBoxLayout()
        browse_frame.setLayout(browse_layout)

        global src_path
        src_path = QLineEdit()  # QLineEdit to display and edit the path
        browse_layout.addWidget(src_path)

        self.button_src_browse.clicked.connect(self.browse_button_clicked)
        browse_layout.addWidget(self.button_src_browse)

        # Indeterminate progress bar
        progress_bar_indeterminate = QProgressBar()
        progress_bar_indeterminate.setRange(0, 0)  # Indeterminate mode
        main_layout.addWidget(progress_bar_indeterminate)

        # Scan button
        self.button_src_scan.clicked.connect(self._scan_button_clicked)
        self.button_src_scan.setEnabled(False)  # Set initial state
        main_layout.addWidget(self.button_src_scan)

        # Game list frame and treeview
        game_list_frame = QFrame()
        game_list_frame.setFrameShape(QFrame.Shape.Panel)
        main_layout.addWidget(game_list_frame)

        game_list_layout = QVBoxLayout()
        game_list_frame.setLayout(game_list_layout)

        self.treeview_game_list = QTreeView()
        game_list_layout.addWidget(self.treeview_game_list)

        # Example headers, replace with your logic
        model = QStandardItemModel()
        headers = ['ID', 'Name', 'Disc Number', 'Bin Files', 'Name Valid', 'CU2', 'BMP']
        model.setHorizontalHeaderLabels(headers)

        self.treeview_game_list.setModel(model)
        self.treeview_game_list.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        scrollbar_game_list = QScrollBar()
        game_list_layout.addWidget(scrollbar_game_list)

        # Tools frame and checkboxes
        tools_frame = QFrame()
        tools_frame.setFrameShape(QFrame.Shape.Panel)
        main_layout.addWidget(tools_frame)

        tools_layout = QHBoxLayout()
        tools_frame.setLayout(tools_layout)

        self.checkbox_merge_bin = QCheckBox('Merge Bin Files')
        self.checkbox_merge_bin.stateChanged.connect(self.checkbox_changed)
        tools_layout.addWidget(self.checkbox_merge_bin)

        self.checkbox_generate_cu2 = QCheckBox('CU2 For All')
        self.checkbox_generate_cu2.stateChanged.connect(self.checkbox_changed)
        tools_layout.addWidget(self.checkbox_generate_cu2)

        self.checkbox_limit_name = QCheckBox('Fix Invalid Name')
        self.checkbox_limit_name.stateChanged.connect(self.checkbox_changed)
        tools_layout.addWidget(self.checkbox_limit_name)

        self.checkbox_auto_rename = QCheckBox('Auto Rename')
        self.checkbox_auto_rename.stateChanged.connect(self.checkbox_changed)
        tools_layout.addWidget(self.checkbox_auto_rename)

        self.checkbox_add_art = QCheckBox('Add Cover Art')
        self.checkbox_add_art.stateChanged.connect(self.checkbox_changed)
        tools_layout.addWidget(self.checkbox_add_art)

        self.checkbox_create_multi_disc = QCheckBox('Create Multi-Disc')
        self.checkbox_create_multi_disc.stateChanged.connect(self.checkbox_changed)
        tools_layout.addWidget(self.checkbox_create_multi_disc)

        # Progress frame and start button
        progress_frame = QFrame()
        progress_frame.setFrameShape(QFrame.Shape.Panel)
        main_layout.addWidget(progress_frame)

        progress_layout = QVBoxLayout()
        progress_frame.setLayout(progress_layout)

        progress_bar = QProgressBar()
        progress_layout.addWidget(progress_bar)

        self.button_start = QPushButton('Start')
        self.button_start.clicked.connect(self._start_button_clicked)
        self.button_start.setEnabled(False)  # Set initial state
        progress_layout.addWidget(self.button_start)

        label_progress = QLabel('Progress Status')
        progress_layout.addWidget(label_progress)

        # Ensure database existence
        # QCoreApplication.instance().aboutToQuit.connect(ensure_database_exists)

        self.show()

        # *****************************************************************************************************************  # Browse button click event

    # *****************************************************************************************************************

    # *************************************************
    # GUI FUNCTIONS:
    # *************************************************
    def browse_button_clicked(self):
        # Open the filedialog
        selected_path = QFileDialog.getExistingDirectory(None, 'Select Game Directory', '/')

        # Update the QLineEdit
        src_path.setText(selected_path)

        # Update the state of the scan button
        if src_path.text() is not None and src_path.text() != '':
            self.button_src_scan.setEnabled(True)
        else:
            self.button_src_scan.setEnabled(False)

    # *****************************************************************************************************************
    # Function to update the progress bar
    def _update_progress_bar(value):
        # progress_bar['value'] = value
        if window is not None:
            window.update()

    # *****************************************************************************************************************

    # Function to update the intermediate progress bar
    def _update_progress_bar_2(value):
        # progress_bar_indeterminate['value'] = value
        if window is not None:
            window.update_idletasks()

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to update the main ui window
    def _update_window(self):
        if window is not None:
            window.update_idletasks()  # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Scan button click event
    def _scan_button_clicked(self):
        self.button_src_scan.setEnabled(False)
        self.game_list = self.game_handler.parse_game_list(src_path.text())
        self._display_game_list(self.game_list)
        if self.checkbox_generate_cu2.isChecked() or self.checkbox_merge_bin.isChecked() or self.checkbox_add_art.isChecked() or self.checkbox_limit_name.isChecked() or self.checkbox_auto_rename.isChecked():
            self.button_start.setEnabled(True)

    def _display_game_list(self, game_list):
        bools = ('No', 'Yes')
        self.treeview_game_list.model().removeRows(0,
                                                   self.treeview_game_list.model().rowCount())  # Clear existing rows if any

        for game in game_list:
            game_id = QStandardItem(str(game.id))
            game_name = QStandardItem(game.cue_sheet.game_name)
            disc_number = QStandardItem(str(game.disc_number))
            number_of_bins = QStandardItem(str(len(game.cue_sheet.bin_files)))
            name_valid = QStandardItem(str(""))
            cu2_present = QStandardItem(bools[game.cu2_present])
            bmp_present = QStandardItem(bools[game.cover_art_present])

            row = [game_id, game_name, disc_number, number_of_bins, name_valid, cu2_present, bmp_present]
            self.treeview_game_list.model().appendRow(row)

    # Start button click event
    def _start_button_clicked(self):
        if not src_path.text() == '':
            self.button_start.setEnabled(False)
            self.game_handler.process_games(self.checkbox_merge_bin.isChecked(), self.checkbox_generate_cu2.isChecked(),
                                            self.checkbox_auto_rename.isChecked(), self.checkbox_limit_name.isChecked(),
                                            self.checkbox_add_art.isChecked(), self.game_list)
            self.button_start.setEnabled(True)

    # Checkbox change event
    def checkbox_changed(self):
        if not self.checkbox_generate_cu2.isChecked() and not self.checkbox_merge_bin.isChecked() and not self.checkbox_add_art.isChecked() and not self.checkbox_limit_name.isChecked() and not self.checkbox_auto_rename.isChecked():
            self.button_start.setEnabled(False)

        if src_path.text() is not None and src_path.text() != '':
            if self.checkbox_generate_cu2.isChecked() or self.checkbox_merge_bin.isChecked() or self.checkbox_add_art.isChecked() or self.checkbox_limit_name.isChecked() or self.checkbox_auto_rename.isChecked():
                # if game_list:
                self.button_start.setEnabled(True)

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    def _get_stored_theme(self):
        data = None
        with open(CONFIG_FILE_PATH) as config_file:
            data = load(config_file)
        return data['theme']

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    def _store_selected_theme(theme_name):
        with open(CONFIG_FILE_PATH, mode="w") as config_file:
            config_file.write(dumps({"theme": theme_name}))

    # *****************************************************************************************************************


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info("PSIO - SDCard Manager Started!")
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
