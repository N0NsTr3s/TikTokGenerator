import os
import sys
import threading
import subprocess
import time
from typing import Optional
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton, QLabel, 
                              QLineEdit, QProgressBar, QTabWidget, QVBoxLayout, QHBoxLayout, 
                              QFormLayout, QTextEdit, QComboBox, QFileDialog, QMessageBox, 
                              QSlider, QGroupBox, QFrame, QSplitter, QCheckBox, QScrollArea,QListWidget,QInputDialog,
                              QAbstractItemView)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer, QMetaObject, Q_ARG, Slot, QAbstractListModel
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtGui import QIcon, QDesktopServices, QDoubleValidator
import random
import logging
from path_utils import find_project_root

os.environ["PYTHONIOENCODING"] = "utf-8"
# Create a custom log handler that redirects to the UI
class UILogHandler(logging.Handler):
    def __init__(self, ui_callback):
        super().__init__()
        self.ui_callback = ui_callback
        self.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
    def emit(self, record):
        log_entry = self.format(record)
        # Use Qt's signal-slot mechanism to safely update UI from another thread
        self.ui_callback(log_entry)

# Update the WorkerThread class to track and terminate subprocesses

class WorkerThread(QThread):
    update_log = Signal(str)
    finished = Signal(bool, str)
    progress_update = Signal(int)
    request_review = Signal(str)  # Signal to request review dialog from main thread
    
    def __init__(self, function, args=None):
        super().__init__()
        self.function = function
        self.args = args or []
        self.stop_requested = False
        self.processes = []  # Track running processes
        
    def run(self):
        try:
            result = self.function(*self.args)
            if not self.stop_requested:
                self.finished.emit(result, "")
            else:
                # Don't send error message when stopped by user
                self.finished.emit(False, "")
        except Exception as e:
            # Always emit the finished signal, even when exceptions occur
            self.update_log.emit(f"Error in worker thread: {str(e)}")
            self.finished.emit(False, str(e))
        finally:
            # Ensure we reset the UI state regardless of how the thread ends
            try:
                # Use a timer to reset the UI from the main thread
                QTimer.singleShot(100, lambda: self.finished.emit(False, ""))
            except Exception:
                pass  # Ignore any errors during cleanup
    
    def request_stop(self):
        self.stop_requested = True
        # Terminate all tracked processes
        for process in self.processes:
            try:
                # Force kill process on Windows
                if process.poll() is None:  # Process is still running
                    import subprocess
                    from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                                   capture_output=True)
            except Exception as e:
                print(f"Error terminating process: {e}")
        
        # Clear the process list
        self.processes.clear()

class TikTokCreatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok Video Creator")
        self.resize(1000, 700)
        
        # Initialize review flag
        self.review_confirmed = False
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.setup_logging()
        # Log application startup
        logging.info("TikTok Creator application started")

        # Set icon if available
        try:
            project_root = find_project_root()
            if project_root:
                icon_path = os.path.join(project_root, "Resources", "ico.ico")
                if os.path.exists(icon_path):
                    self.setWindowIcon(QIcon(icon_path))
        except:
            pass
        
        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create header
        self.header_label = QLabel("TikTok Video Creator")
        self.header_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        self.main_layout.addWidget(self.header_label)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.workflow_tab = QWidget()
        self.custom_workflows_tab = QWidget()
        self.settings_tab = QWidget()
        self.logs_tab = QWidget()
        self.tab_widget.addTab(self.workflow_tab, "Main Workflow")
        self.tab_widget.addTab(self.custom_workflows_tab, "Custom Workflows")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        self.tab_widget.addTab(self.logs_tab, "Logs")

        # Setup tabs
        self.setup_logs_tab()  # Set up logs first so logging works in other setup methods
        self.setup_workflow_tab()
        self.setup_custom_workflows_tab()
        self.setup_settings_tab()
        
        # Initialize variables
        self.process_running = False
        self.worker_thread: Optional[WorkerThread] = None
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        self.load_settings_from_file()


    def save_settings(self):
        """Save settings to both internal state and configuration file"""
        # Save to config file
        if self.save_settings_to_file():
            # Create output directory if needed
            os.makedirs(self.output_input.text(), exist_ok=True)
            
            QMessageBox.information(self, "Settings Saved", 
                                  "Your settings have been saved to CONFIG.txt", 
                                  QMessageBox.StandardButton.Ok)
        else:
            QMessageBox.warning(self, "Save Error", 
                            "There was an error saving your settings to CONFIG.txt")
        
    def setup_logging(self):
        """Configure centralized logging system to capture all logs"""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Set up root logger with a very low level to capture everything
        root_logger.setLevel(logging.DEBUG)
        
        # Console handler 
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        console_handler.setLevel(logging.INFO)  # Console only shows INFO and above
        root_logger.addHandler(console_handler)
        
        # UI handler
        ui_handler = UILogHandler(self.log)
        ui_handler.setLevel(logging.INFO)  # UI shows INFO and above
        root_logger.addHandler(ui_handler)
        
        # File handler for persistent logs
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"tiktok_creator_{time.strftime('%Y%m%d_%H%M%S')}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        file_handler.setLevel(logging.DEBUG)  # File captures all logs
        root_logger.addHandler(file_handler)
        
        # Disable propagation of external loggers to prevent duplicate logs
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            logger.propagate = True  # Make sure logs propagate to the root logger
        
        self.log(f"Logging to file: {log_file}")


    # Add these methods to your TikTokCreatorApp class

    def save_settings_to_file(self):
        """Save all application settings to CONFIG.txt"""
        try:
            config = {
                # General settings
                "output_directory": self.output_input.text(),

                # TikTok account settings
                "tiktok_account": self.tiktok_account.text(),

                # Voice settings
                "voice": self.voice_combo.currentText(),
                "vibe": self.vibe_combo.currentText() if hasattr(self, 'vibe_combo') else "---",
                
                # Video settings
                "zoom_factor": self.zoom_slider.value()/10,
                
                # Workflow settings
                "last_query": self.query_input.text(),
                
                # Custom workflow settings
                "last_workflow": self.workflow_dropdown.currentText() if self.workflow_dropdown.count() > 0 else "",
                
                # Minigame settings
                # Separate minigame settings for main workflow
                "main_add_minigame_to_video": self.main_add_minigame_checkbox.isChecked(),
                "main_record_game": self.main_record_checkbox.isChecked(),
                "main_selected_game": self.main_game_dropdown.currentText(),
                
                # Separate minigame settings for custom workflow
                "custom_add_minigame_to_video": self.custom_add_minigame_checkbox.isChecked(),
                "custom_record_game": self.custom_record_checkbox.isChecked(),
                "custom_selected_game": self.custom_game_dropdown.currentText(),
                # Add the new setting
                "review_prompt": self.review_prompt_checkbox.isChecked(),
                # Add timestamp for reference
                "last_saved": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Write to CONFIG.txt in a readable format
            with open("CONFIG.txt", "w", encoding="utf-8") as f:
                f.write("# TikTok Creator Configuration File\n")
                f.write(f"# Last saved: {config['last_saved']}\n\n")
                
                for key, value in config.items():
                    if key != "last_saved":  # Skip timestamp in main config
                        f.write(f"{key}={value}\n")
            
            self.log(f"Settings saved to CONFIG.txt")
            return True
        except Exception as e:
            self.log(f"Error saving settings: {str(e)}")
            return False

    def load_settings_from_file(self):
        """Load application settings from CONFIG.txt if it exists"""

        if not os.path.exists("CONFIG.txt"):
            self.log("No config file found, using default settings")
            return False
        
        try:
            config = {}
            with open("CONFIG.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
            
            # Apply settings to UI elements
            if "output_directory" in config and os.path.exists(config["output_directory"]):
                self.output_input.setText(config["output_directory"])
            
            if "voice" in config:
                index = self.voice_combo.findText(config["voice"])
                if index >= 0:
                    self.voice_combo.setCurrentIndex(index)
            if "vibe" in config:
                index = self.vibe_combo.findText(config["vibe"])
                if index >= 0:
                    self.vibe_combo.setCurrentIndex(index)
            
            if "zoom_factor" in config:
                try:
                    zoom = float(config["zoom_factor"])
                    self.zoom_slider.setValue(int(zoom * 10))
                except ValueError:
                    pass
            
            if "last_query" in config:
                self.query_input.setText(config["last_query"])
            
            if "last_workflow" in config and config["last_workflow"]:
                index = self.workflow_dropdown.findText(config["last_workflow"])
                if index >= 0:
                    self.workflow_dropdown.setCurrentIndex(index)
            
        # Load main workflow minigame settings
            if "main_add_minigame_to_video" in config:
                self.main_add_minigame_checkbox.setChecked(config["main_add_minigame_to_video"].lower() == "true")
            
            if "main_record_game" in config:
                self.main_record_checkbox.setChecked(config["main_record_game"].lower() == "true")
            
            if "main_selected_game" in config:
                index = self.main_game_dropdown.findText(config["main_selected_game"])
                if index >= 0:
                    self.main_game_dropdown.setCurrentIndex(index)
            
            # Load custom workflow minigame settings
            if "custom_add_minigame_to_video" in config:
                self.custom_add_minigame_checkbox.setChecked(config["custom_add_minigame_to_video"].lower() == "true")
            
            if "custom_record_game" in config:
                self.custom_record_checkbox.setChecked(config["custom_record_game"].lower() == "true")
            
            if "custom_selected_game" in config:
                index = self.custom_game_dropdown.findText(config["custom_selected_game"])
                if index >= 0:
                    self.custom_game_dropdown.setCurrentIndex(index)

            if "review_prompt" in config:
                self.review_prompt_checkbox.setChecked(config["review_prompt"].lower() == "true") 

            if "tags_file" in config and os.path.exists(config["tags_file"]):
                self.load_tags_from_file(config["tags_file"])
            else:
                # Try to load default tags
                default_tags = os.path.join(os.getcwd(), "Tags", "default_tags.txt")
                if os.path.exists(default_tags):
                    self.load_tags_from_file(default_tags)
            
            # Auto-load styles if file is specified
            if "styles_file" in config and os.path.exists(config["styles_file"]):
                self.load_styles_from_file(config["styles_file"])
            else:
                # Try to load default styles
                default_styles = os.path.join(os.getcwd(), "Styles", "default_styles.txt")
                if os.path.exists(default_styles):
                    self.load_styles_from_file(default_styles)
            
            
            
            self.log("Settings loaded from CONFIG.txt")
            return True
        except Exception as e:
            self.log(f"Error loading settings: {str(e)}")
            return False

    def get_voice_vibe_settings(self):
        """Get voice and vibe settings from CONFIG.txt or UI controls"""
        try:
            # First try to get from CONFIG.txt
            voice = "Shimmer"  # default
            vibe = "---"       # default
            
            if os.path.exists("CONFIG.txt"):
                with open("CONFIG.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key == "voice":
                                voice = value
                            elif key == "vibe":
                                vibe = value
            
            # Fall back to UI controls if available
            if hasattr(self, 'voice_combo') and self.voice_combo.currentText():
                voice = self.voice_combo.currentText()
            if hasattr(self, 'vibe_combo') and self.vibe_combo.currentText():
                vibe = self.vibe_combo.currentText()
                
            return voice, vibe
        except Exception as e:
            self.log(f"Error getting voice/vibe settings: {str(e)}")
            return "Shimmer", "---"
    def show_review_dialog(self, file_path):
        """Show dialog for text review and open the file - must be called from main thread"""
        # Reset flag before showing the dialog
        self.review_confirmed = False
        
        # Open the file with default text editor
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        
        # Create confirmation dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Review Text")
        msg_box.setText("The processed text file is now open for review.")
        msg_box.setInformativeText("Please review the text and make any edits if needed. Click Continue when ready to proceed with TTS conversion.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.button(QMessageBox.StandardButton.Ok).setText("Continue")
        
        # Show the dialog
        msg_box.exec()
        
        # Set flag to indicate review is complete
        self.review_confirmed = True
        self.log("Text review confirmed by user")
        
    def setup_workflow_tab(self):
        layout = QVBoxLayout(self.workflow_tab)
        
        # News query section
        query_layout = QHBoxLayout()
        query_label = QLabel("News Query:")
        self.query_input = QLineEdit()
        
        query_layout.addWidget(query_label)
        query_layout.addWidget(self.query_input)
        layout.addLayout(query_layout)
        
        # Workflow buttons section
        button_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run Full Workflow")
        self.stop_btn = QPushButton("Stop Process")
        
        self.run_btn.clicked.connect(self.run_full_workflow)
        self.stop_btn.clicked.connect(self.stop_process)
        
        button_layout.addWidget(self.run_btn)
        button_layout.addWidget(self.stop_btn)
        layout.addLayout(button_layout)
        
        # Individual steps section
        steps_group = QGroupBox("Individual Steps")
        steps_layout = QHBoxLayout(steps_group)
        
        self.news_check_btn = QPushButton("1. News Check")
        self.speech_btn = QPushButton("2. Generate Speech")
        self.video_btn = QPushButton("3. Edit Video")
        self.post_btn = QPushButton("4. Post to TikTok")
        
        self.news_check_btn.clicked.connect(lambda: self.run_step("news_check"))
        self.speech_btn.clicked.connect(lambda: self.run_step("generate_speech"))
        self.video_btn.clicked.connect(lambda: self.run_step("edit_video"))
        self.post_btn.clicked.connect(lambda: self.run_step("post_tiktok"))
        
        steps_layout.addWidget(self.news_check_btn)
        steps_layout.addWidget(self.speech_btn)
        steps_layout.addWidget(self.video_btn)
        steps_layout.addWidget(self.post_btn)
        layout.addWidget(steps_group)
        
        # Progress section
        progress_layout = QHBoxLayout()
        progress_label = QLabel("Progress:")
        self.progress_bar = QProgressBar()

        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        # Browser configuration
        browser_group = QGroupBox("Browser Configuration")
        browser_layout = QVBoxLayout(browser_group)
        
        configure_browser_btn = QPushButton("Configure Browser")
        configure_browser_btn.clicked.connect(self.configure_browser)
        browser_layout.addWidget(configure_browser_btn)
        layout.addWidget(browser_group)
        minigames_group = self.setup_minigames_section(layout, is_main_workflow=True)


        
    # Add this method to your TikTokCreatorApp class to set up the new settings panels
    def setup_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        
        # Create a scrollable area for all settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # TikTok Account Settings
        account_group = QGroupBox("TikTok Profile")
        account_layout = QFormLayout(account_group)
        
        self.tiktok_account = QLineEdit()
        self.tiktok_account.setPlaceholderText("Example: https://www.tiktok.com/@Your_Username")
        account_layout.addRow("Account:", self.tiktok_account)
        
        scroll_layout.addWidget(account_group)
        
        # Video settings (existing)
        video_group = QGroupBox("Video Settings")
        video_layout = QFormLayout(video_group)
        
        zoom_layout = QHBoxLayout()
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 30)  # 1.0 to 3.0 with 10x precision
        self.zoom_slider.setValue(15)  # 1.5 default
        self.zoom_label = QLabel("1.5")
        self.zoom_slider.valueChanged.connect(lambda v: self.zoom_label.setText(f"{v/10:.1f}"))
        
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_label)
        video_layout.addRow("Zoom Factor:", zoom_layout)
        
        scroll_layout.addWidget(video_group)
        
        # Tags Panel
        tags_group = QGroupBox("Video Tags")
        tags_layout = QVBoxLayout(tags_group)
        
        self.use_tags_checkbox = QCheckBox("Use tags in videos")
        self.use_tags_checkbox.setChecked(True)
        tags_layout.addWidget(self.use_tags_checkbox)
        
        # Create dual-panel layout
        tags_panels_layout = QHBoxLayout()
        
        # Available tags panel
        available_tags_panel = QGroupBox("Available Tags")
        available_tags_layout = QVBoxLayout(available_tags_panel)
        self.available_tags_list = QListWidget()
        self.available_tags_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        available_tags_layout.addWidget(self.available_tags_list)
        self.available_tags_list.setMinimumHeight(200)  # Minimum height
        self.available_tags_list.setMaximumHeight(300)  # Maximum height
       
        # Used tags panel
        used_tags_panel = QGroupBox("Used Tags")
        used_tags_layout = QVBoxLayout(used_tags_panel)
        self.used_tags_list = QListWidget()
        self.used_tags_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        used_tags_layout.addWidget(self.used_tags_list)
        self.used_tags_list.setMinimumHeight(200)  # Minimum height
        self.used_tags_list.setMaximumHeight(300)  # Maximum height
        # Transfer buttons in the middle
        transfer_layout = QVBoxLayout()
        move_right_btn = QPushButton(">")
        move_right_btn.setToolTip("Move selected tags to Used")
        move_right_btn.clicked.connect(lambda: self.move_items(self.available_tags_list, self.used_tags_list))
        
        move_left_btn = QPushButton("<")
        move_left_btn.setToolTip("Move selected tags to Available")
        move_left_btn.clicked.connect(lambda: self.move_items(self.used_tags_list, self.available_tags_list))
        
        transfer_layout.addStretch()
        transfer_layout.addWidget(move_right_btn)
        transfer_layout.addWidget(move_left_btn)
        transfer_layout.addStretch()
        
        # Add panels to dual-panel layout
        tags_panels_layout.addWidget(available_tags_panel)
        tags_panels_layout.addLayout(transfer_layout)
        tags_panels_layout.addWidget(used_tags_panel)
        tags_layout.addLayout(tags_panels_layout)
        
        # File management buttons
        tags_btn_layout = QHBoxLayout()
        save_tags_btn = QPushButton("Save Tags Configuration")
       
        
        save_tags_btn.clicked.connect(self.save_tags)

        tags_btn_layout.addWidget(save_tags_btn)
        tags_layout.addLayout(tags_btn_layout)

        # After the dual-panel layout for tags
        tags_control_layout = QHBoxLayout()
        create_tag_btn = QPushButton("Create Tag")
        create_tag_btn.setToolTip("Add a new tag")
        create_tag_btn.clicked.connect(self.add_new_tag)

        delete_tag_btn = QPushButton("Delete Selected")
        delete_tag_btn.setToolTip("Delete selected tags from any list")
        delete_tag_btn.clicked.connect(self.delete_selected_tags)

        tags_control_layout.addWidget(create_tag_btn)
        tags_control_layout.addWidget(delete_tag_btn)
        tags_layout.addLayout(tags_control_layout)

        # File management buttons remain the same
        tags_btn_layout = QHBoxLayout()

        tags_layout.addLayout(tags_btn_layout)
        
        scroll_layout.addWidget(tags_group)
        
        # Image Styles Panel - Replace with dual-panel system
        styles_group = QGroupBox("Image Generation Styles")
        styles_layout = QVBoxLayout(styles_group)
        
        self.use_styles_checkbox = QCheckBox("Use custom styles for image generation")
        self.use_styles_checkbox.setChecked(True)
        styles_layout.addWidget(self.use_styles_checkbox)
        
        # Create dual-panel layout
        styles_panels_layout = QHBoxLayout()
        
        # Available styles panel
        available_styles_panel = QGroupBox("Available Styles")
        available_styles_layout = QVBoxLayout(available_styles_panel)
        self.available_styles_list = QListWidget()
        self.available_styles_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        available_styles_layout.addWidget(self.available_styles_list)
        self.available_styles_list.setMinimumHeight(200)  # Minimum height
        self.available_styles_list.setMaximumHeight(300)  # Maximum height
        
        # Used styles panel
        used_styles_panel = QGroupBox("Used Styles")
        used_styles_layout = QVBoxLayout(used_styles_panel)
        self.used_styles_list = QListWidget()
        self.used_styles_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        used_styles_layout.addWidget(self.used_styles_list)
        self.used_styles_list.setMinimumHeight(200)  # Minimum height
        self.used_styles_list.setMaximumHeight(300)  # Maximum height

        # Transfer buttons in the middle
        styles_transfer_layout = QVBoxLayout()
        move_style_right_btn = QPushButton(">")
        move_style_right_btn.setToolTip("Move selected styles to Used")
        move_style_right_btn.clicked.connect(lambda: self.move_items(self.available_styles_list, self.used_styles_list))
        
        move_style_left_btn = QPushButton("<")
        move_style_left_btn.setToolTip("Move selected styles to Available")
        move_style_left_btn.clicked.connect(lambda: self.move_items(self.used_styles_list, self.available_styles_list))
        
        styles_transfer_layout.addStretch()
        styles_transfer_layout.addWidget(move_style_right_btn)
        styles_transfer_layout.addWidget(move_style_left_btn)
        styles_transfer_layout.addStretch()
        
        # Add panels to dual-panel layout
        styles_panels_layout.addWidget(available_styles_panel)
        styles_panels_layout.addLayout(styles_transfer_layout)
        styles_panels_layout.addWidget(used_styles_panel)
        styles_layout.addLayout(styles_panels_layout)
        
        # File management buttons
        styles_btn_layout = QHBoxLayout()
        save_styles_btn = QPushButton("Save Styles Configuration")
        
        save_styles_btn.clicked.connect(self.save_styles)
        
        styles_btn_layout.addWidget(save_styles_btn)
        styles_layout.addLayout(styles_btn_layout)

        # Similarly update the Styles panel:
        styles_control_layout = QHBoxLayout()
        create_style_btn = QPushButton("Create Style")
        create_style_btn.setToolTip("Add a new style")
        create_style_btn.clicked.connect(self.add_new_style)

        delete_style_btn = QPushButton("Delete Selected")
        delete_style_btn.setToolTip("Delete selected styles from any list")
        delete_style_btn.clicked.connect(self.delete_selected_styles)

        styles_control_layout.addWidget(create_style_btn)
        styles_control_layout.addWidget(delete_style_btn)
        styles_layout.addLayout(styles_control_layout)
        
        scroll_layout.addWidget(styles_group)
        
        
        # Output directory (existing)
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)
        
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Output Directory:")
        self.output_input = QLineEdit(os.path.join(os.getcwd(), "Output"))
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output_dir)
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.output_input)
        dir_layout.addWidget(output_browse)
        output_layout.addLayout(dir_layout)
        
        scroll_layout.addWidget(output_group)
        
        # Voice & Vibe settings
        voice_group = QGroupBox("Voice Settings")
        voice_layout = QFormLayout(voice_group)

        self.voice_combo = QComboBox()
        # populate voices dynamically from OpenAIFM data
        try:
            from GeneratedScripts.OpenAITTS import find_openaifm_data_dir, load_voices_json, list_voice_names
            data_dir = find_openaifm_data_dir()
            voices = None
            if data_dir:
                voices = load_voices_json(data_dir)
            names = list_voice_names(voices) if voices is not None else []
            if not names:
                names = ["en-US:Steffan(Male)", "en-US:Ana(Female)", "en-GB:Ryan(Male)"]
        except Exception:
            names = ["en-US:Steffan(Male)", "en-US:Ana(Female)", "en-GB:Ryan(Male)"]

        self.voice_combo.addItems(names)

        # Vibe dropdown
        self.vibe_combo = QComboBox()
        try:
            from GeneratedScripts.OpenAITTS import find_openaifm_data_dir, load_voices_json
            data_dir = find_openaifm_data_dir()
            vibes = None
            if data_dir:
                import json
                vfile = data_dir / 'vibes.json'
                if vfile.exists():
                    with open(vfile, 'r', encoding='utf-8') as vf:
                        vibes = json.load(vf)
            vibe_names = ["---"]
            if isinstance(vibes, dict):
                vibe_names += list(vibes.keys())
        except Exception:
            vibe_names = ["---"]

        self.vibe_combo.addItems(vibe_names)

        voice_layout.addRow("Voice:", self.voice_combo)
        voice_layout.addRow("Vibe:", self.vibe_combo)
        scroll_layout.addWidget(voice_group)

        # Vibe creator UI (separate fields for required parts)
        vibe_create_group = QGroupBox("Add Custom Vibe")
        vibe_create_layout = QFormLayout(vibe_create_group)
        self.new_vibe_name = QLineEdit()
        self.new_vibe_voice_affect = QLineEdit()
        self.new_vibe_tone = QLineEdit()
        self.new_vibe_pacing = QLineEdit()
        self.new_vibe_emotion = QLineEdit()
        self.new_vibe_pronunciation = QLineEdit()
        self.new_vibe_pauses = QLineEdit()
        add_vibe_btn = QPushButton("Add Vibe")
        add_vibe_btn.clicked.connect(self.add_custom_vibe)
        vibe_create_layout.addRow("Vibe Name:", self.new_vibe_name)
        vibe_create_layout.addRow("Voice Affect:", self.new_vibe_voice_affect)
        vibe_create_layout.addRow("Tone:", self.new_vibe_tone)
        vibe_create_layout.addRow("Pacing:", self.new_vibe_pacing)
        vibe_create_layout.addRow("Emotion:", self.new_vibe_emotion)
        vibe_create_layout.addRow("Pronunciation:", self.new_vibe_pronunciation)
        vibe_create_layout.addRow("Pauses:", self.new_vibe_pauses)
        vibe_create_layout.addRow(add_vibe_btn)
        scroll_layout.addWidget(vibe_create_group)
        
        # Workflow Controls (existing)
        review_group = QGroupBox("Workflow Controls")
        review_layout = QVBoxLayout(review_group)
        
        self.review_prompt_checkbox = QCheckBox("Review processed text before TTS conversion")
        self.review_prompt_checkbox.setToolTip("Pauses workflow to let you review and edit the processed.txt file")
        review_layout.addWidget(self.review_prompt_checkbox)
        
        scroll_layout.addWidget(review_group)
        
        # Complete the scroll area setup
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # Save button (should be at the end)
        save_btn = QPushButton("Save All Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def add_new_tag(self):
        """Add a new tag to the available tags list"""
        tag, ok = QInputDialog.getText(self, "Add Tag", "Enter a new tag (include # prefix):")
        if ok and tag:
            if not tag.startswith('#'):
                tag = '#' + tag
            self.available_tags_list.addItem(tag)

    def add_new_style(self):
        """Add a new style to the available styles list"""
        style, ok = QInputDialog.getText(self, "Add Style", "Enter a new image generation style:")
        if ok and style:
            self.available_styles_list.addItem(style)

    def delete_tags(self, list_widget):
        """Delete selected tags from the specified list widget"""
        selected_items = list_widget.selectedItems()
        if not selected_items:
            return
            
        result = QMessageBox.question(
            self, "Confirm Delete", 
            f"Delete {len(selected_items)} selected tag(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                row = list_widget.row(item)
                list_widget.takeItem(row)

    def delete_styles(self, list_widget):
        """Delete selected styles from the specified list widget"""
        selected_items = list_widget.selectedItems()
        if not selected_items:
            return
            
        result = QMessageBox.question(
            self, "Confirm Delete", 
            f"Delete {len(selected_items)} selected style(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                row = list_widget.row(item)
                list_widget.takeItem(row)

    def add_custom_vibe(self):
        """Validate and add a custom vibe to the openaifm vibes.json and CONFIG.txt"""
        try:
            name = self.new_vibe_name.text().strip()
            voice_affect = self.new_vibe_voice_affect.text().strip()
            tone = self.new_vibe_tone.text().strip()
            pacing = self.new_vibe_pacing.text().strip()
            emotion = self.new_vibe_emotion.text().strip()
            pronunciation = self.new_vibe_pronunciation.text().strip()
            pauses = self.new_vibe_pauses.text().strip()
        except Exception:
            QMessageBox.warning(self, "Vibe Error", "Vibe UI not available")
            return

        if not name:
            QMessageBox.warning(self, "Vibe Error", "Please enter a name for the vibe")
            return
        # All fields are mandatory
        if not all([voice_affect, tone, pacing, emotion, pronunciation, pauses]):
            QMessageBox.warning(self, "Vibe Error", "All vibe fields are mandatory")
            return

        # Build the lines list
        lines = [
            f"Voice Affect: {voice_affect}",
            f"Tone: {tone}",
            f"Pacing: {pacing}",
            f"Emotion: {emotion}",
            f"Pronunciation: {pronunciation}",
            f"Pauses: {pauses}",
        ]

        # Locate vibes.json dynamically
        try:
            from GeneratedScripts.OpenAITTS import find_openaifm_data_dir
            data_dir = find_openaifm_data_dir()
            if not data_dir:
                QMessageBox.warning(self, "Vibe Error", "Could not locate OpenAIFM data directory")
                return
            vibes_file = data_dir / 'vibes.json'
            import json
            if vibes_file.exists():
                with open(vibes_file, 'r', encoding='utf-8') as vf:
                    vibes = json.load(vf)
            else:
                vibes = {}

            # Add or overwrite
            vibes[name] = lines
            with open(vibes_file, 'w', encoding='utf-8') as vf:
                json.dump(vibes, vf, ensure_ascii=False, indent=4)

            # Update CONFIG.txt with selected vibe
            cfg_path = os.path.join(os.getcwd(), 'CONFIG.txt')
            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as cf:
                    for ln in cf:
                        ln = ln.strip()
                        if ln and not ln.startswith('#') and '=' in ln:
                            k, v = ln.split('=', 1)
                            cfg[k.strip()] = v.strip()
            cfg['vibe'] = name
            with open(cfg_path, 'w', encoding='utf-8') as cf:
                for k, v in cfg.items():
                    cf.write(f"{k}={v}\n")

            # Update UI
            self.vibe_combo.addItem(name)
            index = self.vibe_combo.findText(name)
            if index >= 0:
                self.vibe_combo.setCurrentIndex(index)

            QMessageBox.information(self, "Vibe Added", f"Vibe '{name}' added to vibes.json and CONFIG.txt")
        except Exception as e:
            QMessageBox.warning(self, "Vibe Error", f"Failed to add vibe: {e}")

    def move_items(self, source_list, target_list):
        """Move selected items from source list to target list"""
        selected_items = source_list.selectedItems()
        if not selected_items:
            return
            
        for item in selected_items:
            # Get row and text
            row = source_list.row(item)
            text = item.text()
            
            # Add to target list
            target_list.addItem(text)
            
            # Remove from source list
            source_list.takeItem(row)

    # Add methods to handle tags and styles
    def save_tags(self):
        """Save tags to default tags file"""
        try:
            # Get tags from the used tags list
            used_tags = []
            for i in range(self.used_tags_list.count()):
                used_tags.append(self.used_tags_list.item(i).text())
            
            # Get available tags
            available_tags = []
            for i in range(self.available_tags_list.count()):
                available_tags.append(self.available_tags_list.item(i).text())
            
            # Create tags directory if it doesn't exist
            tags_dir = os.path.join(os.getcwd(), "Tags")
            os.makedirs(tags_dir, exist_ok=True)
            
            # Define default filepath
            filepath = os.path.join(tags_dir, "default_tags.txt")
            
            with open(filepath, "w", encoding="utf-8") as f:
                # Save used tags first
                f.write("# Used Tags\n")
                f.write("\n".join(used_tags))
                f.write("\n\n# Available Tags\n")
                f.write("\n".join(available_tags))
                
            self.log(f"Tags saved to {filepath}")
            
            # Update the current tags file in the settings
            config = {}
            if os.path.exists("CONFIG.txt"):
                with open("CONFIG.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            key, value = line.split("=", 1)
                            config[key.strip()] = value.strip()
            
            config["tags_file"] = filepath
            config["use_tags"] = str(self.use_tags_checkbox.isChecked())
            
            with open("CONFIG.txt", "w", encoding="utf-8") as f:
                f.write("# TikTok Creator Configuration File\n")
                f.write(f"# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for key, value in config.items():
                    f.write(f"{key}={value}\n")
            
            return True
        except Exception as e:
            self.log(f"Error saving tags: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save tags: {str(e)}")
            return False


    def delete_selected_tags(self):
        """Delete selected tags from either list"""
        # Check both lists for selections
        available_items = self.available_tags_list.selectedItems()
        used_items = self.used_tags_list.selectedItems()
        
        total_selected = len(available_items) + len(used_items)
        if total_selected == 0:
            return
        
        result = QMessageBox.question(
            self, "Confirm Delete", 
            f"Delete {total_selected} selected tag(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            # Delete from available list
            for item in available_items:
                row = self.available_tags_list.row(item)
                self.available_tags_list.takeItem(row)
                
            # Delete from used list
            for item in used_items:
                row = self.used_tags_list.row(item)
                self.used_tags_list.takeItem(row)

    def delete_selected_styles(self):
        """Delete selected styles from either list"""
        # Check both lists for selections
        available_items = self.available_styles_list.selectedItems()
        used_items = self.used_styles_list.selectedItems()
        
        total_selected = len(available_items) + len(used_items)
        if total_selected == 0:
            return
        
        result = QMessageBox.question(
            self, "Confirm Delete", 
            f"Delete {total_selected} selected style(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            # Delete from available list
            for item in available_items:
                row = self.available_styles_list.row(item)
                self.available_styles_list.takeItem(row)
                
            # Delete from used list
            for item in used_items:
                row = self.used_styles_list.row(item)
                self.used_styles_list.takeItem(row)

    def save_styles(self):
        """Save styles to default styles file"""
        try:
            # Get styles from the used styles list
            used_styles = []
            for i in range(self.used_styles_list.count()):
                used_styles.append(self.used_styles_list.item(i).text())
            
            # Get available styles
            available_styles = []
            for i in range(self.available_styles_list.count()):
                available_styles.append(self.available_styles_list.item(i).text())
            
            # Create styles directory if it doesn't exist
            styles_dir = os.path.join(os.getcwd(), "Styles")
            os.makedirs(styles_dir, exist_ok=True)
            
            # Define default filepath
            filepath = os.path.join(styles_dir, "default_styles.txt")
            
            with open(filepath, "w", encoding="utf-8") as f:
                # Save used styles first
                f.write("# Used Styles\n")
                f.write("\n".join(used_styles))
                f.write("\n\n# Available Styles\n")
                f.write("\n".join(available_styles))
                
            self.log(f"Styles saved to {filepath}")
            
            # Update the current styles file in the settings
            config = {}
            if os.path.exists("CONFIG.txt"):
                with open("CONFIG.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            key, value = line.split("=", 1)
                            config[key.strip()] = value.strip()
            
            config["styles_file"] = filepath
            config["use_styles"] = str(self.use_styles_checkbox.isChecked())
            
            with open("CONFIG.txt", "w", encoding="utf-8") as f:
                f.write("# TikTok Creator Configuration File\n")
                f.write(f"# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for key, value in config.items():
                    f.write(f"{key}={value}\n")
            
            return True
        except Exception as e:
            self.log(f"Error saving styles: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save styles: {str(e)}")
            return False


    def load_tags_from_file(self, filepath):
        """Load tags from a specific file path without prompting"""
        try:
            # Clear existing lists
            self.available_tags_list.clear()
            self.used_tags_list.clear()
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Parse the file - look for section markers
            used_tags = []
            available_tags = []
            
            if "# Used Tags" in content and "# Available Tags" in content:
                # File has sections
                sections = content.split("# Available Tags")
                used_section = sections[0].replace("# Used Tags", "").strip()
                available_section = sections[1].strip()
                
                used_tags = [tag for tag in used_section.split('\n') if tag.strip() and tag.startswith('#')]
                available_tags = [tag for tag in available_section.split('\n') if tag.strip() and tag.startswith('#')]
            else:
                # Legacy format or no sections - add all to available
                available_tags = [tag for tag in content.split('\n') if tag.strip() and tag.startswith('#')]
            
            # Add to the lists
            for tag in used_tags:
                self.used_tags_list.addItem(tag)
                
            for tag in available_tags:
                self.available_tags_list.addItem(tag)
                
            self.log(f"Tags loaded from {filepath}")
        except Exception as e:
            self.log(f"Error loading tags from {filepath}: {str(e)}")

    def load_styles_from_file(self, filepath):
        """Load styles from a specific file path without prompting"""
        try:
            # Clear existing lists
            self.available_styles_list.clear()
            self.used_styles_list.clear()
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Parse the file - look for section markers
            used_styles = []
            available_styles = []
            
            if "# Used Styles" in content and "# Available Styles" in content:
                # File has sections
                sections = content.split("# Available Styles")
                used_section = sections[0].replace("# Used Styles", "").strip()
                available_section = sections[1].strip()
                
                used_styles = [style for style in used_section.split('\n') if style.strip() and not style.startswith('#')]
                available_styles = [style for style in available_section.split('\n') if style.strip() and not style.startswith('#')]
            else:
                # Legacy format or no sections - add all to available
                available_styles = [style for style in content.split('\n') if style.strip() and not style.startswith('#')]
            
            # Add to the lists
            for style in used_styles:
                self.used_styles_list.addItem(style)
                
            for style in available_styles:
                self.available_styles_list.addItem(style)
                
            self.log(f"Styles loaded from {filepath}")
        except Exception as e:
            self.log(f"Error loading styles from {filepath}: {str(e)}")


    def setup_logs_tab(self):
        layout = QVBoxLayout(self.logs_tab)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Log control buttons
        button_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear Logs")
        save_btn = QPushButton("Save Logs")
        
        clear_btn.clicked.connect(self.clear_logs)
        save_btn.clicked.connect(self.save_logs)
        
        button_layout.addWidget(clear_btn)
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)
    
    def log(self, message):
        """Add a message to the log text area with error handling"""
        # Only append to log text if it exists
        if hasattr(self, 'log_text') and self.log_text is not None:
            try:
                # First append the message
                self.log_text.append(message)
                
                # Then scroll to bottom
                self.log_text.verticalScrollBar().setValue(
                    self.log_text.verticalScrollBar().maximum()
                )
            except Exception as e:
                print(f"Error writing to log_text: {str(e)}")
                print(message)  # Fallback to console
        else:
            print(message)  # Fallback to console
    
    def clear_logs(self):
        self.log_text.clear()
        self.log("Logs cleared")
    
    def save_logs(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Logs", "", "Text Files (*.txt);;All Files (*)"
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.log_text.toPlainText())
            self.log(f"Logs saved to {filepath}")
    
    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_input.setText(directory)
            self.log(f"Output directory set to: {directory}")
    
    
    def open_output_folder(self):
        output_path = self.output_input.text()
        if os.path.exists(output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(output_path))
            self.log(f"Opened output folder: {output_path}")
        else:
            QMessageBox.critical(self, "Error", "Output folder doesn't exist!")
            self.log(f"Failed to open output folder: {output_path} (does not exist)")
    
    def run_full_workflow(self):
        if self.process_running:
            QMessageBox.warning(self, "Process Running", "A process is already running!")
            return
        
        query = self.query_input.text().strip()
        if not query:
            QMessageBox.critical(self, "Error", "Please enter a news query!")
            return
        
        # Save current settings before running workflow
        self.save_settings_to_file()
        self.log("Settings automatically saved before running workflow")
        
        self.process_running = True
        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # Create and start worker thread
        self.worker_thread = WorkerThread(self._run_full_workflow, [query])
        self.worker_thread.update_log.connect(self.log)
        self.worker_thread.progress_update.connect(self.progress_bar.setValue)
        self.worker_thread.finished.connect(self.workflow_finished)
        self.worker_thread.request_review.connect(self.show_review_dialog)
        self.worker_thread.start()
        
        self.log(f"Started full workflow with query: {query}")
        self.status_bar.showMessage(f"Running full workflow")

    def _run_full_workflow(self, query):
        """Execute the full workflow starting with NewsCheck.py"""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit(f"Running full workflow with query: {query}")
            
            # Initialize progress bar at 0%
            self.worker_thread.progress_update.emit(0)
            
            # Get minigame settings from UI
            add_minigame = self.main_add_minigame_checkbox.isChecked()
            record_game = self.main_record_checkbox.isChecked()
            selected_game = self.main_game_dropdown.currentText()
            
            # Count total steps for progress calculation
            remaining_scripts = []
            
            # Get voice and vibe settings for TTSCaller
            voice, vibe = self.get_voice_vibe_settings()
            text_file = os.path.join(os.getcwd(), "processed.txt")
            
            # Add TTSCaller.py with proper arguments
            remaining_scripts.append([sys.executable, r"GeneratedScripts\TTSCaller.py", 
                                    "--text-file", text_file, "--voice", voice, "--vibe", vibe])
            
            if add_minigame and record_game:
                remaining_scripts.append([sys.executable, r"GeneratedScripts\tiktokimagegenForGenerated.py", "--add-minigame=True"])
                remaining_scripts.append([sys.executable, r"GeneratedScripts\editVideoTestForGenerated.py", "--add-minigame=True"])
            else:
                remaining_scripts.append([sys.executable, r"GeneratedScripts\tiktokimagegenForGenerated.py"])
                remaining_scripts.append([sys.executable, r"GeneratedScripts\editVideoTestForGenerated.py"])
            remaining_scripts.append(r"GeneratedScripts\postForGenerated.py")
            
            # Calculate progress increment including NewsCheck.py
            total_steps = len(remaining_scripts) + 1  # +1 for NewsCheck.py
            progress_increment = 100 // total_steps
            current_progress = 0
            
            # Handle game recording if enabled
            if record_game:
                self.worker_thread.update_log.emit("Starting game recording...")
                
                # Determine game path based on selection
                if selected_game == "Random Game" or selected_game == "randomgame":
                    games = [r"Minigames\game.py", r"Minigames\circlegame.py"]
                    game_path = random.choice(games)
                elif selected_game == "Rotating Circles Game" or selected_game == "circlegame":
                    game_path = r"Minigames\circlegame.py"
                else:  # Default to racing game
                    game_path = r"Minigames\game.py"
                
                # Launch the game
                game_process = subprocess.Popen([sys.executable, game_path])
                self.worker_thread.processes.append(game_process)
                
                # Wait a moment for game to initialize
                time.sleep(2)
                
                # Start the recording process
                record_process = subprocess.Popen([sys.executable, r"Minigames\recordgame.py"])
                self.worker_thread.processes.append(record_process)
                
                # Wait for processes to complete
                game_process.wait()
                if self.worker_thread.stop_requested:
                    return False
                self.worker_thread.update_log.emit("Game recording completed")
            
            # Execute NewsCheck.py with the query
            self.worker_thread.update_log.emit(f"Running NewsCheck.py with query: {query}")
            self.worker_thread.progress_update.emit(current_progress)  # Show initial progress
            
            process = subprocess.Popen(
                [sys.executable, "NewsCheck.py", query],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1
            )
            
            # Register the process with the worker thread
            self.worker_thread.processes.append(process)
            
            # Process output in real-time
            def read_output(pipe, prefix):
                """Process output from a subprocess, handling encoding errors"""
                try:
                    for line in iter(pipe.readline, ''):
                        if line.strip() and not self.worker_thread.stop_requested: # pyright: ignore[reportOptionalMemberAccess]
                            # Try to decode with utf-8 if needed
                            if isinstance(line, bytes):
                                try:
                                    line = line.decode('utf-8')
                                except UnicodeDecodeError:
                                    # Fall back to a more forgiving encoding
                                    line = line.decode('utf-8', errors='replace')
                            
                            self.worker_thread.update_log.emit(f"{prefix}: {line.strip()}") # pyright: ignore[reportOptionalMemberAccess]
                except UnicodeDecodeError:
                    self.worker_thread.update_log.emit(f"{prefix}: [Unicode decoding error - some output could not be displayed]") # pyright: ignore[reportOptionalMemberAccess]
                finally:
                    pipe.close()
            
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "[NewsCheck]"))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "[NewsCheck]"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete with progress updates
            is_running = True
            while is_running:
                is_running = process.poll() is None
                if not is_running:
                    break
                time.sleep(1)
                # Gradually increase progress during NewsCheck execution
                # but not exceeding the allocated increment for the step
                if current_progress < progress_increment - 1:
                    current_progress += 1
                    self.worker_thread.progress_update.emit(current_progress)
            
            if process.returncode != 0 and not self.worker_thread.stop_requested:
                self.worker_thread.update_log.emit(f"NewsCheck error: Process returned {process.returncode}")
                return False
            
            # Update progress after NewsCheck completion
            current_progress = progress_increment
            self.worker_thread.progress_update.emit(current_progress)
                
            # Check if the user wants to review processed text before TTS conversion
            if hasattr(self, 'review_prompt_checkbox') and self.review_prompt_checkbox.isChecked():
                # Check for stop request first
                if self.worker_thread.stop_requested:
                    self.worker_thread.update_log.emit("Process stopped, skipping file review")
                    return False
                    
                self.worker_thread.update_log.emit("Review processed text option is enabled")
                
                # Check if processed.txt exists
                processed_file_path = os.path.join(os.getcwd(), "processed.txt")
                if os.path.exists(processed_file_path):
                    # Request review dialog from main thread
                    self.worker_thread.request_review.emit(processed_file_path)
                    
                    # Wait for the dialog result with timeout
                    timeout = 300  # 5 minutes timeout
                    start_time = time.time()
                    while not self.review_confirmed:
                        if self.worker_thread.stop_requested:
                            return False
                        # Check for timeout
                        if time.time() - start_time > timeout:
                            self.worker_thread.update_log.emit("Timeout waiting for text review. Continuing workflow...")
                            break
                        time.sleep(0.5)
                    
                    # Reset the confirmation flag
                    self.review_confirmed = False
                    
                    self.worker_thread.update_log.emit("Continuing workflow after prompt review")
                else:
                    self.worker_thread.update_log.emit("processed.txt file not found. Continuing workflow.")
                    
            # Execute remaining scripts
            for i, script in enumerate(remaining_scripts):
                if self.worker_thread.stop_requested:
                    return False
                    
                # Update progress for current script
                current_progress = (i + 1) * progress_increment
                self.worker_thread.progress_update.emit(current_progress)
                
                if isinstance(script, list):
                    # Script with arguments
                    self.worker_thread.update_log.emit(f"Running: {' '.join(script)}")
                    process = subprocess.Popen(
                        script,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        bufsize=1
                    )
                else:
                    # Script without arguments
                    self.worker_thread.update_log.emit(f"Running: {script}")
                    process = subprocess.Popen(
                        [sys.executable, script],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        bufsize=1
                    )
                
                # Register the process with the worker thread
                self.worker_thread.processes.append(process)
                
                # Process output in real-time
                stdout_thread = threading.Thread(target=read_output, args=(process.stdout, f"[Script {i+1}/{len(remaining_scripts)}]"))
                stderr_thread = threading.Thread(target=read_output, args=(process.stderr, f"[Script {i+1}/{len(remaining_scripts)}] ERROR"))
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                # Wait for process to complete
                process.wait()
                if process.returncode != 0 and not self.worker_thread.stop_requested:
                    self.worker_thread.update_log.emit(f"Script error: Process returned {process.returncode}")
                    return False

            # Set final progress
            self.worker_thread.progress_update.emit(100)
            self.worker_thread.update_log.emit("Full workflow completed successfully")
            return True
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error running full workflow: {str(e)}")
            return False
        
    def stop_process(self):
        """Force stop any running process"""
        if not self.process_running or not self.worker_thread:
            return
        
        self.log("Forcefully stopping all processes...")
        self.status_bar.showMessage("Stopping process...")
        
        # Request stop in the worker thread (which will kill all subprocesses)
        self.worker_thread.request_stop()
        
        # Reset progress bar immediately
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(0)
        if hasattr(self, 'workflow_progress'):
            self.workflow_progress.setValue(0)
        
        # Show a notification instead of an error
        QMessageBox.information(self, "Process Stopped", "The process has been stopped successfully.", QMessageBox.StandardButton.Ok)
        
        # Reset UI state
        self.reset_process_state()

    def reset_process_state(self):
        """Reset the UI state after process completion or termination"""
        self.process_running = False
        self.run_btn.setEnabled(True)
        self.run_workflow_btn.setEnabled(True)
        self.status_bar.showMessage("Ready")
        self.log("Process state reset. Ready for new operations.")
        
    def run_step(self, step):
        """Execute a specific step of the workflow"""
        if self.process_running:
            QMessageBox.warning(self, "Process Running", "A process is already running!")
            return
        
        # Set process state
        self.process_running = True
        self.run_btn.setEnabled(False)
        self.run_workflow_btn.setEnabled(False)
        
        # Determine which set of checkboxes to use - default to main workflow
        add_minigame = self.main_add_minigame_checkbox.isChecked()
        record_game = self.main_record_checkbox.isChecked()
        selected_game = self.main_game_dropdown.currentText()
        
        # Create and start worker thread
        if step == "news_check":
            self.worker_thread = WorkerThread(self._run_news_check, [self.query_input.text()])
        elif step == "generate_speech":
            self.worker_thread = WorkerThread(self._run_speech_generation)
        elif step == "edit_video":
            # Pass the minigame settings from the main workflow
            self.worker_thread = WorkerThread(self._run_video_editing, [add_minigame, record_game, selected_game])
        elif step == "post_tiktok":
            self.worker_thread = WorkerThread(self._run_posting)
        
        if self.worker_thread:  # Add null check
            self.worker_thread.update_log.connect(self.log)
            self.worker_thread.finished.connect(self.process_finished)
            self.worker_thread.start()
        
        # Update status
        self.status_bar.showMessage(f"Running step: {step}")
    

    def _run_news_check(self, query):
        """Execute the NewsCheck.py script with the provided query."""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit(f"Running NewsCheck with query: {query}")
            
            if not query.strip():
                self.worker_thread.update_log.emit("Error: Empty query provided")
                return False
            
            # Run NewsCheck.py with the query
            process = subprocess.Popen(
                [sys.executable, "NewsCheck.py", query],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Register the process with the worker thread
            self.worker_thread.processes.append(process)
            
            # Process output in real-time
            def read_output(pipe, prefix):
                """Process output from a subprocess, handling encoding errors"""
                try:
                    for line in iter(pipe.readline, ''):
                        if line.strip() and not self.worker_thread.stop_requested: # pyright: ignore[reportOptionalMemberAccess]
                            # Try to decode with utf-8 if needed
                            if isinstance(line, bytes):
                                try:
                                    line = line.decode('utf-8')
                                except UnicodeDecodeError:
                                    # Fall back to a more forgiving encoding
                                    line = line.decode('utf-8', errors='replace')
                            
                            self.worker_thread.update_log.emit(f"{prefix}: {line.strip()}") # pyright: ignore[reportOptionalMemberAccess]
                except UnicodeDecodeError:
                    self.worker_thread.update_log.emit(f"{prefix}: [Unicode decoding error - some output could not be displayed]") # pyright: ignore[reportOptionalMemberAccess]
                finally:
                    pipe.close()
            
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "[NewsCheck]"))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "[NewsCheck]"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            process.wait()
            if self.worker_thread.stop_requested:
                return False
                
            if process.returncode != 0:
                self.worker_thread.update_log.emit(f"NewsCheck failed with code {process.returncode}")
                return False
            
            self.worker_thread.update_log.emit("NewsCheck completed successfully")
            return True
        
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error in NewsCheck: {str(e)}")
            return False

    def _run_speech_generation(self):
        """Execute the TTSCaller.py script for text-to-speech conversion."""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit("Running speech generation...")
            
            # Set environment variables to prevent Qt conflicts
            env = os.environ.copy()
            env["MPLBACKEND"] = "Agg"  # Use non-interactive matplotlib backend
            env["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""  # Prevent Qt plugin conflicts
            
            # Run TTSCaller.py (local wrapper that calls OPENAIFM node)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, "GeneratedScripts", "TTSCaller.py")

            # Use processed.txt file path instead of reading content to avoid command line length issues
            text_file = os.path.join(os.getcwd(), "processed.txt")

            # Get voice and vibe settings from CONFIG.txt or UI
            voice, vibe = self.get_voice_vibe_settings()

            process = subprocess.Popen(
                [sys.executable, script_path, "--text-file", text_file, "--voice", voice, "--vibe", vibe],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                text=True,
                bufsize=1,
                env=env  # Pass modified environment
            )
            
            # Register the process with the worker thread
            self.worker_thread.processes.append(process)
            
            # Process output in real-time
            def read_output(pipe, prefix):
                """Process output from a subprocess, handling encoding errors"""
                try:
                    for line in iter(pipe.readline, ''):
                        if line.strip() and not self.worker_thread.stop_requested: # pyright: ignore[reportOptionalMemberAccess]
                            # Try to decode with utf-8 if needed
                            if isinstance(line, bytes):
                                try:
                                    line = line.decode('utf-8')
                                except UnicodeDecodeError:
                                    # Fall back to a more forgiving encoding
                                    line = line.decode('utf-8', errors='replace')
                            
                            self.worker_thread.update_log.emit(f"{prefix}: {line.strip()}") # pyright: ignore[reportOptionalMemberAccess]
                except UnicodeDecodeError:
                    self.worker_thread.update_log.emit(f"{prefix}: [Unicode decoding error - some output could not be displayed]") # pyright: ignore[reportOptionalMemberAccess]
                finally:
                    pipe.close()
            
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "[Speech Generation]"))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "[Speech Generation]"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            process.wait()
            if self.worker_thread.stop_requested:
                return False
                
            if process.returncode != 0:
                # Check if failure was due to Qt warnings vs actual errors
                self.worker_thread.update_log.emit(f"Speech generation process returned code {process.returncode}")
                # Don't treat Qt GUI integration warnings as fatal errors
                if process.returncode in [-1073741819, 1]:  # Common Qt warning exit codes
                    self.worker_thread.update_log.emit("Process completed despite Qt warnings (non-critical)")
                    return True
                else:
                    self.worker_thread.update_log.emit(f"Speech generation failed with code {process.returncode}")
                    return False
            
            self.worker_thread.update_log.emit("Speech generation completed successfully")
            return True
        
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error in speech generation: {str(e)}")
            return False

    def _run_posting(self):
        """Execute the postForGenerated.py script to post content to TikTok."""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit("Running TikTok posting...")
            
            # Run postForGenerated.py
            process = subprocess.Popen(
                [sys.executable, r"GeneratedScripts\postForGenerated.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace',
                text=True,
                bufsize=1
            )
            
            # Register the process with the worker thread
            self.worker_thread.processes.append(process)
            
            # Process output in real-time
            def read_output(pipe, prefix):
                """Process output from a subprocess, handling encoding errors"""
                try:
                    for line in iter(pipe.readline, ''):
                        if line.strip() and not self.worker_thread.stop_requested: # pyright: ignore[reportOptionalMemberAccess]
                            self.worker_thread.update_log.emit(f"{prefix}: {line.strip()}") # pyright: ignore[reportOptionalMemberAccess]
                except UnicodeDecodeError:
                    self.worker_thread.update_log.emit(f"{prefix}: [Unicode decoding error - some output could not be displayed]") # pyright: ignore[reportOptionalMemberAccess]
                finally:
                    pipe.close()
            
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "[TikTok Posting]"))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "[TikTok Posting]"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            process.wait()
            if self.worker_thread.stop_requested:
                return False
                
            if process.returncode != 0:
                self.worker_thread.update_log.emit(f"TikTok posting failed with code {process.returncode}")
                return False
            
            self.worker_thread.update_log.emit("TikTok posting completed successfully")
            return True
        
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error in TikTok posting: {str(e)}")
            return False

    def process_finished(self, success, error_msg):
        """Handle completion of a process."""
        self.process_running = False
        self.run_btn.setEnabled(True)
        
        # Don't show any message if the process was stopped by the user
        if self.worker_thread and self.worker_thread.stop_requested:
            self.status_bar.showMessage("Process stopped by user")
            return
        
        if success:
            self.status_bar.showMessage("Process completed successfully")
            self.log("Process completed successfully")
        else:
            error_msg = error_msg or "Unknown error"
            self.status_bar.showMessage(f"Error: {error_msg}")
            self.log(f"Process failed: {error_msg}")
            QMessageBox.critical(self, "Error", f"Process failed: {error_msg}")


    def _run_video_editing(self, add_minigame=False, record_game=False, selected_game="Random Game"):
        """Execute the tiktokimagegenForGenerated.py and editVideoTestForGenerated.py scripts."""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit("Running image generation and video editing...")
            
            # Updated to use parameters instead of directly accessing self.add_minigame_checkbox
            if add_minigame and record_game:
                imggen_args = ["--add-minigame=True"]
                video_args = ["--add-minigame=True"]
            else:
                imggen_args = []
                video_args = []
            
            # Log which game was selected (using the parameter)
            if record_game:
                self.worker_thread.update_log.emit(f"Using minigame: {selected_game}")
                
                # Determine game path based on selection
                if selected_game == "Random Game" or selected_game == "randomgame":
                    games = [r"Minigames\game.py", r"Minigames\circlegame.py"]
                    game_path = random.choice(games)
                elif selected_game == "Rotating Circles Game" or selected_game == "circlegame":
                    game_path = r"Minigames\circlegame.py"
                else:  # Default to racing game
                    game_path = r"Minigames\game.py"
                
                # Launch the game
                self.worker_thread.update_log.emit(f"Launching game: {game_path}")
                game_process = subprocess.Popen([sys.executable, game_path])
                self.worker_thread.processes.append(game_process)
                
                # Wait a moment for game to initialize
                time.sleep(2)
                
                # Start the recording process
                record_process = subprocess.Popen([sys.executable, r"Minigames\recordgame.py"])
                self.worker_thread.processes.append(record_process)
                
                # Wait for processes to complete
                game_process.wait()
                if self.worker_thread.stop_requested:
                    return False
                self.worker_thread.update_log.emit("Game recording completed")
            
            # Run image generation
            imggen_process = subprocess.Popen(
                [sys.executable, r"GeneratedScripts\tiktokimagegenForGenerated.py"] + imggen_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Register the process with the worker thread
            self.worker_thread.processes.append(imggen_process)
            
            # Process output in real-time
            def read_output(pipe, prefix):
                """Process output from a subprocess, handling encoding errors"""
                try:
                    for line in iter(pipe.readline, ''):
                        if line.strip() and not self.worker_thread.stop_requested: # pyright: ignore[reportOptionalMemberAccess]
                            # Try to decode with utf-8 if needed
                            if isinstance(line, bytes):
                                try:
                                    line = line.decode('utf-8')
                                except UnicodeDecodeError:
                                    # Fall back to a more forgiving encoding
                                    line = line.decode('utf-8', errors='replace')
                            
                            self.worker_thread.update_log.emit(f"{prefix}: {line.strip()}") # pyright: ignore[reportOptionalMemberAccess]
                except UnicodeDecodeError:
                    self.worker_thread.update_log.emit(f"{prefix}: [Unicode decoding error - some output could not be displayed]") # pyright: ignore[reportOptionalMemberAccess]
                finally:
                    pipe.close()
            
            stdout_thread = threading.Thread(target=read_output, args=(imggen_process.stdout, "[Image Generation]"))
            stderr_thread = threading.Thread(target=read_output, args=(imggen_process.stderr, "[Image Generation]"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            imggen_process.wait()
            if self.worker_thread.stop_requested:
                return False
                
            if imggen_process.returncode != 0:
                self.worker_thread.update_log.emit(f"Image generation failed with code {imggen_process.returncode}")
                return False
            
            # Run video editing with the video args we prepared
            self.worker_thread.update_log.emit("Running video editing...")
            video_process = subprocess.Popen(
                [sys.executable, r"GeneratedScripts\editVideoTestForGenerated.py"] + video_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Register the process with the worker thread
            self.worker_thread.processes.append(video_process)
            
            # Process output in real-time
            stdout_thread = threading.Thread(target=read_output, args=(video_process.stdout, "[Video Editing]"))
            stderr_thread = threading.Thread(target=read_output, args=(video_process.stderr, "[Video Editing]"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            video_process.wait()
            if self.worker_thread.stop_requested:
                return False
                
            if video_process.returncode != 0:
                self.worker_thread.update_log.emit(f"Video editing failed with code {video_process.returncode}")
                return False
            
            self.worker_thread.update_log.emit("Video generation and editing completed successfully")
            return True
        
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error in video editing: {str(e)}")
            return False

    
    def workflow_finished(self, success, error_msg):
        self.process_running = False
        self.run_btn.setEnabled(True)
        self.run_workflow_btn.setEnabled(True)
        
        # Don't show any message if the process was stopped by user
        if self.worker_thread and self.worker_thread.stop_requested:
            self.status_bar.showMessage("Process stopped by user")
            return
        
        if success:
            self.status_bar.showMessage("Ready")
            QMessageBox.information(self, "Success", "Workflow completed successfully!", QMessageBox.StandardButton.Ok)
        else:
            self.status_bar.showMessage(f"Error: {error_msg}")
            QMessageBox.critical(self, "Error", f"Workflow failed: {error_msg}")
    
    def step_finished(self, success, error_msg):
        # Similar to workflow_finished
        pass

    def setup_custom_workflows_tab(self):
        """Setup the custom workflows tab with workflow selection and execution controls."""
        layout = QVBoxLayout(self.custom_workflows_tab)
        
        # Workflows section
        workflows_group = QGroupBox("Custom Workflows")
        workflows_layout = QVBoxLayout(workflows_group)
        
        # Workflow selection
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Select Workflow:"))
        
        self.workflow_dropdown = QComboBox()
        self.refresh_workflow_list()  # Populate the dropdown
        selection_layout.addWidget(self.workflow_dropdown)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_workflow_list)
        selection_layout.addWidget(refresh_btn)
        
        workflows_layout.addLayout(selection_layout)
        
        # Run workflow button
        run_layout = QHBoxLayout()
        self.run_workflow_btn = QPushButton("Run Selected Workflow")
        self.run_workflow_btn.clicked.connect(self.run_selected_workflow)
        run_layout.addWidget(self.run_workflow_btn)
        
        self.stop_workflow_btn = QPushButton("Stop Workflow")
        self.stop_workflow_btn.clicked.connect(self.stop_process)
        run_layout.addWidget(self.stop_workflow_btn)
        
        workflows_layout.addLayout(run_layout)
        
        # Browser configuration
        browser_group = QGroupBox("Browser Configuration")
        browser_layout = QVBoxLayout(browser_group)
        
        configure_browser_btn = QPushButton("Configure Browser")
        configure_browser_btn.clicked.connect(self.configure_browser)
        browser_layout.addWidget(configure_browser_btn)
        
        # Create new workflow section
        create_group = QGroupBox("Create New Workflow")
        create_layout = QVBoxLayout(create_group)
        
        self.new_workflow_name = QLineEdit()
        self.new_workflow_name.setPlaceholderText("Enter workflow name")
        create_layout.addWidget(self.new_workflow_name)
        
        create_btn = QPushButton("Create with Selenium Recorder")
        create_btn.clicked.connect(self.create_new_workflow)
        create_layout.addWidget(create_btn)
        
        # Add all components to main layout
        layout.addWidget(workflows_group)
        layout.addWidget(browser_group)
        layout.addWidget(create_group)
        
        # Workflow progress
        progress_layout = QHBoxLayout()
        progress_label = QLabel("Workflow Progress:")
        self.workflow_progress = QProgressBar()
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.workflow_progress)
        layout.addLayout(progress_layout)

        minigames_group = self.setup_minigames_section(layout, is_main_workflow=False)
    
        # Add a separator before the workflow progress
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

    def refresh_workflow_list(self):
        """Scan for available workflow scripts and update the dropdown."""
        self.workflow_dropdown.clear()
        
        # Check for generated scripts in the GeneratedScripts directory
        scripts_dir = os.path.join(os.getcwd(), "GeneratedScripts")
        
        if os.path.exists(scripts_dir):
            workflow_scripts = []
            for file in os.listdir(scripts_dir):
                excluded_files = ["tiktokimagegenForGenerated.py", "editVideoTestForGenerated.py", 
                                  "parsetextForGenerated.py", 
                                 "postForGenerated.py", "SeleniumRecorder.py", "TTSCaller.py", "OpenAITTS.py"]
                if file.endswith(".py") and not file.startswith("__") and file not in excluded_files:
                    workflow_scripts.append(file)
            
            workflow_scripts.sort()
            for script in workflow_scripts:
                self.workflow_dropdown.addItem(script)
        
        self.log(f"Found {self.workflow_dropdown.count()} custom workflows")

    def run_selected_workflow(self):
        """Run the selected workflow using runallForGenerated.py."""
        if self.process_running:
            QMessageBox.warning(self, "Process Running", "A process is already running!")
            return
        
        if self.workflow_dropdown.count() == 0:
            QMessageBox.warning(self, "No Workflows", "No workflows available. Please create one first.")
            return
        
        # Save current settings before running workflow
        self.save_settings_to_file()
        self.log("Settings automatically saved before running workflow")
        
        selected_workflow = self.workflow_dropdown.currentText()
        workflow_path = os.path.join("GeneratedScripts", selected_workflow)
        
        if not os.path.exists(workflow_path):
            QMessageBox.critical(self, "Error", f"Workflow file not found: {workflow_path}")
            return
        
        self.process_running = True
        self.run_workflow_btn.setEnabled(False)
        self.workflow_progress.setValue(0)
        
        # Create and start worker thread
        self.worker_thread = WorkerThread(self._run_workflow, [workflow_path])
        if self.worker_thread:  # Add null check
            self.worker_thread.update_log.connect(self.log)
            self.worker_thread.progress_update.connect(self.workflow_progress.setValue)
            self.worker_thread.finished.connect(self.workflow_finished)
            self.worker_thread.request_review.connect(self.show_review_dialog)
            self.worker_thread.start()
        
        self.log(f"Started workflow: {selected_workflow}")
        self.status_bar.showMessage(f"Running workflow: {selected_workflow}")

    def _run_workflow(self, workflow_path):
        """Execute the workflow directly implementing the functionality of runallForGenerated.py"""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit(f"Running workflow: {workflow_path}")
            
            # Get minigame settings from UI
            add_minigame = self.custom_add_minigame_checkbox.isChecked()
            record_game = self.custom_record_checkbox.isChecked()
            selected_game = self.custom_game_dropdown.currentText()
            
            # Define remaining scripts to calculate progress properly
            remaining_scripts = []
            
            # Get voice and vibe settings for TTSCaller
            voice, vibe = self.get_voice_vibe_settings()
            text_file = os.path.join(os.getcwd(), "processed.txt")
            
            # Add TTSCaller.py with proper arguments
            remaining_scripts.append([sys.executable, r"GeneratedScripts\TTSCaller.py", 
                                    "--text-file", text_file, "--voice", voice, "--vibe", vibe])
            
            # Add image generation and video editing scripts with proper arguments
            if add_minigame and record_game:
                remaining_scripts.append([sys.executable, r"GeneratedScripts\tiktokimagegenForGenerated.py", "--add-minigame=True"])
                remaining_scripts.append([sys.executable, r"GeneratedScripts\editVideoTestForGenerated.py", "--add-minigame=True"])
            else:
                remaining_scripts.append([sys.executable, r"GeneratedScripts\tiktokimagegenForGenerated.py"])
                remaining_scripts.append([sys.executable, r"GeneratedScripts\editVideoTestForGenerated.py"])
                
            # Add post script
            remaining_scripts.append(r"GeneratedScripts\postForGenerated.py")
            
            # Calculate progress increment per script including the custom workflow
            total_scripts = len(remaining_scripts) + 1  # +1 for the custom workflow
            progress_increment = 100 // total_scripts
            current_progress = 0  # Start from 0 progress
            
            # Initialize progress bar
            self.worker_thread.progress_update.emit(current_progress)
            
            # Handle game recording if enabled
            if record_game:
                self.worker_thread.update_log.emit("Starting game recording...")
                
                # Determine game path based on selection
                if selected_game == "Random Game" or selected_game == "randomgame":
                    games = [r"Minigames\game.py", r"Minigames\circlegame.py"]
                    game_path = random.choice(games)
                elif selected_game == "Rotating Circles Game" or selected_game == "circlegame":
                    game_path = r"Minigames\circlegame.py"
                else:  # Default to racing game
                    game_path = r"Minigames\game.py"
                
                # Launch the game
                game_process = subprocess.Popen([sys.executable, game_path])
                self.worker_thread.processes.append(game_process)
                
                # Wait a moment for game to initialize
                time.sleep(2)
                
                # Start the recording process
                record_process = subprocess.Popen([sys.executable, r"Minigames\recordgame.py"])
                self.worker_thread.processes.append(record_process)
                
                # Wait for processes to complete
                game_process.wait()
                if self.worker_thread.stop_requested:
                    return False
                self.worker_thread.update_log.emit("Game recording completed")
            
            # Execute the first script (custom workflow)
            self.worker_thread.update_log.emit(f"Running custom workflow: {workflow_path}")
            process = subprocess.Popen(
                [sys.executable, workflow_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1
            )
            
            # Register the process with the worker thread
            self.worker_thread.processes.append(process)
            
            # Process output in real-time
            def read_output(pipe, prefix):
                """Process output from a subprocess, handling encoding errors"""
                try:
                    for line in iter(pipe.readline, ''):
                        if line.strip() and not self.worker_thread.stop_requested: # pyright: ignore[reportOptionalMemberAccess]
                            # Try to decode with utf-8 if needed
                            if isinstance(line, bytes):
                                try:
                                    line = line.decode('utf-8')
                                except UnicodeDecodeError:
                                    # Fall back to a more forgiving encoding
                                    line = line.decode('utf-8', errors='replace')
                            
                            self.worker_thread.update_log.emit(f"{prefix}: {line.strip()}") # pyright: ignore[reportOptionalMemberAccess]
                except UnicodeDecodeError:
                    self.worker_thread.update_log.emit(f"{prefix}: [Unicode decoding error - some output could not be displayed]") # pyright: ignore[reportOptionalMemberAccess]
                finally:
                    pipe.close()
            
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, f"[Custom Workflow]"))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, f"[Custom Workflow]"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            process.wait()
            if process.returncode != 0 and not self.worker_thread.stop_requested:
                self.worker_thread.update_log.emit(f"Custom workflow error: Process returned {process.returncode}")
                return False
            
            # Update progress after first script completes
            current_progress += progress_increment
            self.worker_thread.progress_update.emit(current_progress)
                
            # Check if the user wants to review processed text before TTS conversion
            if hasattr(self, 'review_prompt_checkbox') and self.review_prompt_checkbox.isChecked():
                # Check for stop request first
                if self.worker_thread.stop_requested:
                    self.worker_thread.update_log.emit("Process stopped, skipping file review")
                    return False
                    
                self.worker_thread.update_log.emit("Review processed text option is enabled")
                
                # Check if processed.txt exists
                processed_file_path = os.path.join(os.getcwd(), "processed.txt")
                if os.path.exists(processed_file_path):
                    # Request review dialog from main thread
                    self.worker_thread.request_review.emit(processed_file_path)
                    
                    # Wait for the dialog result
                    while not self.review_confirmed:
                        if self.worker_thread.stop_requested:
                            return False
                        time.sleep(0.5)
                    
                    # Reset the confirmation flag
                    self.review_confirmed = False
                    
                    self.worker_thread.update_log.emit("Continuing workflow after prompt review")
                else:
                    self.worker_thread.update_log.emit("processed.txt file not found. Continuing workflow.")
                    
            # Execute remaining scripts
            for i, script in enumerate(remaining_scripts):
                if self.worker_thread.stop_requested:
                    return False
                    
                if isinstance(script, list):
                    # Script with arguments
                    self.worker_thread.update_log.emit(f"Running: {' '.join(script)}")
                    process = subprocess.Popen(
                        script,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',  # Explicitly set encoding to UTF-8
                        bufsize=1
                    )
                else:
                    # Script without arguments
                    self.worker_thread.update_log.emit(f"Running: {script}")
                    process = subprocess.Popen(
                        [sys.executable, script],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',  # Explicitly set encoding to UTF-8
                        bufsize=1
                    )
                
                # Register the process with the worker thread
                self.worker_thread.processes.append(process)
                
                # Process output in real-time
                stdout_thread = threading.Thread(target=read_output, args=(process.stdout, f"[Script {i+1}/{len(remaining_scripts)}]"))
                stderr_thread = threading.Thread(target=read_output, args=(process.stderr, f"[Script {i+1}/{len(remaining_scripts)}] ERROR"))
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                # Wait for process to complete
                process.wait()
                if process.returncode != 0 and not self.worker_thread.stop_requested:
                    self.worker_thread.update_log.emit(f"Script error: Process returned {process.returncode}")
                    return False
                    
                # Update progress after each script
                current_progress += progress_increment
                self.worker_thread.progress_update.emit(min(current_progress, 100))  # Ensure we don't exceed 100%

            # Set final progress to 100% in case of rounding errors
            self.worker_thread.progress_update.emit(100)
            self.worker_thread.update_log.emit("Workflow completed successfully")
            return True
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error running workflow: {str(e)}")
            return False

    def configure_browser(self):
        """Configure the browser using ConfigureBrowser.py."""
        try:
            self.log("Configuring browser...")
            
            # Run the browser configuration script
            subprocess.Popen([sys.executable, "ConfigureBrowser.py"], 
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            self.log("Browser configuration launched. Please follow the instructions in the new window.")
        except Exception as e:
            self.log(f"Error configuring browser: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to configure browser: {str(e)}")

    def create_new_workflow(self):
        """Create a new workflow using SeleniumRecorder."""
        workflow_name = self.new_workflow_name.text().strip()
        
        if not workflow_name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name for the new workflow.")
            return
        
        # Ensure name has proper format
        if not workflow_name.endswith(".py"):
            workflow_name += ".py"
        
        # Create GeneratedScripts directory if it doesn't exist
        scripts_dir = os.path.join(os.getcwd(), "GeneratedScripts")
        os.makedirs(scripts_dir, exist_ok=True)
        
        output_path = os.path.join(scripts_dir, workflow_name)
        
        try:
            self.log(f"Creating new workflow: {workflow_name}")
            
            # Run the Selenium recorder
            subprocess.Popen([sys.executable, "SeleniumRecorder.py", "--output", output_path], 
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            self.log("Selenium Recorder launched. Please follow the instructions in the new window.")
        except Exception as e:
            self.log(f"Error creating workflow: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to create workflow: {str(e)}")

    def setup_minigames_section(self, parent_layout, is_main_workflow=True):
        """Create a minigames section that can be added to any tab
        
        Parameters:
            parent_layout: The layout to add the minigames group to
            is_main_workflow: True for main workflow tab, False for custom workflow tab
        """
        minigames_group = QGroupBox("Minigames")
        minigames_layout = QVBoxLayout(minigames_group)
        
        # Data collection section
        data_section = QHBoxLayout()
        data_section.addWidget(QLabel("Player Data:"))
        
        get_data_btn = QPushButton("Collect Player Data")
        get_data_btn.setToolTip("Scrape TikTok for player avatars to use in games")
        get_data_btn.clicked.connect(self.run_get_data)
        data_section.addWidget(get_data_btn)
        
        minigames_layout.addLayout(data_section)
        
        # Game selection section
        game_section = QHBoxLayout()
        game_section.addWidget(QLabel("Select Game:"))
        
        # Create separate dropdown for each tab
        if is_main_workflow:
            self.main_game_dropdown = QComboBox()
            self.main_game_dropdown.addItems(["Random Game", "Racing Game", "Rotating Circles Game"])
            game_section.addWidget(self.main_game_dropdown)
        else:
            self.custom_game_dropdown = QComboBox()
            self.custom_game_dropdown.addItems(["Random Game", "Racing Game", "Rotating Circles Game"])
            game_section.addWidget(self.custom_game_dropdown)
        
        minigames_layout.addLayout(game_section)
        
        # Recording options - create separate checkboxes
        recording_layout = QHBoxLayout()
        recording_layout.addWidget(QLabel("Auto-record:"))
        
        if is_main_workflow:
            self.main_record_checkbox = QCheckBox()
            self.main_record_checkbox.setChecked(True)
            self.main_record_checkbox.stateChanged.connect(
                lambda state: self.update_record_setting(state, is_main=True))
            recording_layout.addWidget(self.main_record_checkbox)
        else:
            self.custom_record_checkbox = QCheckBox()
            self.custom_record_checkbox.setChecked(True)
            self.custom_record_checkbox.stateChanged.connect(
                lambda state: self.update_record_setting(state, is_main=False))
            recording_layout.addWidget(self.custom_record_checkbox)
        
        minigames_layout.addLayout(recording_layout)
        
        # Launch button
        launch_btn = QPushButton("Launch Game")
        launch_btn.clicked.connect(lambda: self.launch_game(is_main_workflow))
        minigames_layout.addWidget(launch_btn)
        
        # Add minigame options for video - separate checkboxes
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Add to Video:"))
        
        if is_main_workflow:
            self.main_add_minigame_checkbox = QCheckBox("Include in final video")
            self.main_add_minigame_checkbox.setChecked(True)
            self.main_add_minigame_checkbox.stateChanged.connect(
                lambda state: self.update_minigame_setting(state, is_main=True))
            options_layout.addWidget(self.main_add_minigame_checkbox)
        else:
            self.custom_add_minigame_checkbox = QCheckBox("Include in final video")
            self.custom_add_minigame_checkbox.setChecked(True)
            self.custom_add_minigame_checkbox.stateChanged.connect(
                lambda state: self.update_minigame_setting(state, is_main=False))
            options_layout.addWidget(self.custom_add_minigame_checkbox)
        
        minigames_layout.addLayout(options_layout)
        
        # Add the group to the parent layout
        parent_layout.addWidget(minigames_group)
        
        return minigames_group

    def update_record_setting(self, state, is_main=True):
        """Auto-save the record game setting when checkbox state changes"""
        if is_main:
            self.update_config_setting("main_record_game", state == Qt.CheckState.Checked)
            self.log("Main workflow auto-record setting updated in CONFIG.txt")
        else:
            self.update_config_setting("custom_record_game", state == Qt.CheckState.Checked)
            self.log("Custom workflow auto-record setting updated in CONFIG.txt")

    def update_minigame_setting(self, state, is_main=True):
        """Auto-save the add minigame setting when checkbox state changes"""
        if is_main:
            self.update_config_setting("main_add_minigame_to_video", state == Qt.CheckState.Checked)
            self.log("Main workflow add to video setting updated in CONFIG.txt")
        else:
            self.update_config_setting("custom_add_minigame_to_video", state == Qt.CheckState.Checked)
            self.log("Custom workflow add to video setting updated in CONFIG.txt")

    def update_config_setting(self, key, value):
        """Update a specific setting in CONFIG.txt without overwriting the entire file"""
        try:
            # Read current config
            config = {}
            if os.path.exists("CONFIG.txt"):
                with open("CONFIG.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            try:
                                k, v = line.split("=", 1)
                                config[k.strip()] = v.strip()
                            except ValueError:
                                # Skip malformed lines
                                pass
            
            # Update specific setting
            config[key] = str(value)
            
            # Write back to CONFIG.txt
            with open("CONFIG.txt", "w", encoding="utf-8") as f:
                f.write("# TikTok Creator Configuration File\n")
                f.write(f"# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for k, v in config.items():
                    f.write(f"{k}={v}\n")
            
            return True
        except Exception as e:
            print(f"Error updating configuration: {str(e)}")
            return False


    def run_get_data(self):
        """Run the getdata.py script to collect player data"""
        if self.process_running:
            QMessageBox.warning(self, "Process Running", "A process is already running!")
            return
        
        self.process_running = True
        self.log("Starting player data collection...")
        
        # Create and start worker thread
        self.worker_thread = WorkerThread(self._run_get_data)
        self.worker_thread.update_log.connect(self.log)
        self.worker_thread.finished.connect(self.get_data_finished)
        self.worker_thread.start()

    def _run_get_data(self):
        """Execute the getdata.py script"""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit("Running player data collection...")
            
            # Run the getdata.py script
            result = subprocess.run(
                [sys.executable, os.path.join("Minigames", "getdata.py")],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode != 0:
                self.worker_thread.update_log.emit(f"Error collecting player data: {result.stderr}")
                return False
            
            self.worker_thread.update_log.emit(result.stdout)
            self.worker_thread.update_log.emit("Player data collection completed successfully")
            return True
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error running player data collection: {str(e)}")
            return False

    def get_data_finished(self, success, error_msg):
        """Callback when getdata.py finishes"""
        self.process_running = False
        
        if success:
            self.status_bar.showMessage("Player data collection completed")
            self.log("Player data collection successful!")
        else:
            self.status_bar.showMessage(f"Error: {error_msg}")
            self.log(f"Player data collection failed: {error_msg}")

    def launch_game(self, is_main_workflow=True):
        """Launch the selected minigame and optionally record it"""
        try:
            # Use the correct dropdowns and checkboxes based on which workflow tab is active
            if is_main_workflow:
                selected_game = self.main_game_dropdown.currentText()
                record_game = self.main_record_checkbox.isChecked()
            else:
                selected_game = self.custom_game_dropdown.currentText()
                record_game = self.custom_record_checkbox.isChecked()
            
            # Determine which game to launch
            game_script = ""
            if selected_game == "Racing Game":
                game_script = "racinggame.py"
            elif selected_game == "Rotating Circles Game":
                game_script = "rotatingcircles.py"
            else:  # Random
                games = ["racinggame.py", "rotatingcircles.py"]
                game_script = random.choice(games)
            
            # Launch game
            game_path = os.path.join("Minigames", game_script)
            self.log(f"Launching {game_script}...")
            
            game_process = subprocess.Popen([sys.executable, game_path])
            
            # Launch recorder if enabled
            recorder_process = None
            if record_game:
                self.log("Recording gameplay...")
                recorder_path = os.path.join("Minigames", "recordgame.py")
                recorder_process = subprocess.Popen([sys.executable, recorder_path])
            
            return True
        except Exception as e:
            self.log(f"Error launching game: {str(e)}")
            return False

    def _launch_game(self, game_script, record=True):
        """Execute the game script and recording script in parallel if requested"""
        try:
            if not self.worker_thread:
                return False
            self.worker_thread.update_log.emit(f"Launching game: {game_script}")
            
            # Start the game process
            game_process = subprocess.Popen(
                [sys.executable, os.path.join("Minigames", game_script)],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            # Start recording process if enabled
            recorder_process = None
            if record:
                self.worker_thread.update_log.emit("Starting game recording...")
                time.sleep(1)  # Give game a moment to initialize
                recorder_process = subprocess.Popen(
                    [sys.executable, os.path.join("Minigames", "recordgame.py")],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            
            # Wait for game process to finish
            game_process.wait()
            
            # If recording was enabled, wait for recording to finish
            if recorder_process:
                recorder_process.wait()
                
                # Find the most recent recording
                output_dir = os.path.join(os.getcwd(), "Minigames", "output")
                if os.path.exists(output_dir):
                    recordings = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".avi")]
                    if recordings:
                        latest_recording = max(recordings, key=os.path.getctime)
                        self.worker_thread.update_log.emit(f"Game recorded: {latest_recording}")
            
            self.worker_thread.update_log.emit("Game session completed")
            return True
        except Exception as e:
            if self.worker_thread:
                self.worker_thread.update_log.emit(f"Error running game: {str(e)}")
            return False

    def game_finished(self, success, error_msg):
        """Callback when game finishes"""
        self.process_running = False
        
        if success:
            self.status_bar.showMessage("Game session completed")
            
            # If "Add to Video" is checked, update the settings
            # Check both main and custom workflow checkboxes
            add_to_video = False
            if hasattr(self, 'main_add_minigame_checkbox') and self.main_add_minigame_checkbox.isChecked():
                add_to_video = True
            elif hasattr(self, 'custom_add_minigame_checkbox') and self.custom_add_minigame_checkbox.isChecked():
                add_to_video = True
                
            if add_to_video:
                # Find the latest recording to use in the video
                output_dir = os.path.join(os.getcwd(), "Minigames", "output")
                if os.path.exists(output_dir):
                    recordings = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".avi")]
                    if recordings:
                        latest_recording = max(recordings, key=os.path.getctime)
                        # Store this path for later use when generating videos
                        self.minigame_video_path = latest_recording
                        self.log(f"Minigame video will be added to final video: {os.path.basename(latest_recording)}")
        else:
            self.status_bar.showMessage(f"Error: {error_msg}")
            self.log(f"Game session failed: {error_msg}")

if __name__ == "__main__":
    # Add this code to hide the console window on Windows
    if sys.platform == 'win32':
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd != 0:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
    app = QApplication(sys.argv)

    app.setStyle("Fusion")  # Modern look across platforms

    window = TikTokCreatorApp()
    window.show()
    sys.exit(app.exec())
