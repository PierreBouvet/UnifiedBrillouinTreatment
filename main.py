import sys
import sqlite3
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QHBoxLayout, QWidget, QFileDialog, QMessageBox, QVBoxLayout,QTableWidget, QTableWidgetItem, QMenu, QHeaderView, QFrame, QLabel, QComboBox, QDialog, QTabWidget, QTreeWidget, QTreeWidgetItem
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize, Qt, QPoint
import subprocess
import os
import pyperclip
import configparser
import numpy as np
import time
import h5py
from functools import partial
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import csv
from datetime import datetime

loc = "/Users/pierrebouvet/Documents/Code/UnifiedBrillouinTreatment/"

class ImportSpectra:
    def __init__(self, db_manager, filepath, main_gui):
        self.db_manager = db_manager
        self.filepath = filepath
        self.main_gui = main_gui
        (name,ext) = os.path.splitext(os.path.basename(filepath))
        if ext == ".bh5": self.add_bh5_spectra(name)
        elif ext == ".DAT": self.add_ghost_spectra(name)
    
    def add_bh5_spectra(self,name):
        timestmp = time.ctime(os.path.getctime(self.filepath))

        if self.check_in_db(name):
            QMessageBox.information(self.main_gui,"File already in database","The database has already a file with identical name. Please change the name of your file to add it to the database.")
            return
        
        QMessageBox.critical(self.main_gui,"Not implemented yet","The functionnality to add bh5 files to the database is not yet implemented")

    def add_ghost_spectra(self, name):
        metadata = {}
        data = []
        timestmp = time.ctime(os.path.getctime(self.filepath))

        if self.check_in_db(name):
            QMessageBox.information(self.main_gui,"File already in database","The database has already a file with identical name. Please change the name of your file to add it to the database.")
            return
        
        with open(self.filepath, 'r') as file:
            lines = file.readlines()
            
            # Extract metadata
            for line in lines:
                if line.strip() == '':
                    continue  # Skip empty lines
                if any(char.isdigit() for char in line.split()[0]):
                    break  # Stop at the first number
                else:
                    # Split metadata into key-value pairs
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()
            
            # Extract numerical data
            for line in lines:
                if line.strip().isdigit():
                    data.append(int(line.strip()))

        # Convert data to a NumPy array
        data_array = np.array(data)

        # Create the bh5 file and generate associated command to add to database
        bh5_filepath = self.create_bh5_file(name, data_array)
        
        # Assign attributes to bh5 file
        with h5py.File(bh5_filepath, 'a') as f:
            # 1. Create the root group and add attributes
            f.attrs['FILEPROP.BLS_HDF5_Version'] = '0.1'
            f.attrs['FILEPROP.Name'] = name
            f.attrs['MEASURE.Date_of_measure'] = timestmp
            f.attrs['MEASURE.Sample'] = metadata["Sample"]
            f.attrs['SPECTROMETER.Scanning_Strategy'] = "point_scanning"
            f.attrs['SPECTROMETER.Type'] = "TFP"
            f.attrs['SPECTROMETER.Illumination_Type'] = "CW"
            f.attrs['SPECTROMETER.Detector_Type'] = "Photon Counter"
            f.attrs['SPECTROMETER.Filtering_Module'] = "None"
            f.attrs['SPECTROMETER.Wavelength_nm'] = metadata["Wavelength"]
            f.attrs['SPECTROMETER.Scan_Amplitude'] = metadata["Scan amplitude"]
            spectral_resolution = float(float(metadata["Scan amplitude"])/data_array.shape[-1])
            f.attrs['SPECTROMETER.Spectral_Resolution'] = str(spectral_resolution)

        # Add spectrum to database
        self.db_manager.add_spectrum(name,
                                    data_array, 
                                    bh5_filepath,
                                    date = timestmp, 
                                    sample = metadata["Sample"],
                                    brillouin_signal_type = "spontaneous",
                                    scanning_strategy = "point_scanning",
                                    spectrometer_type = "FP",
                                    laser_wavelength = int(metadata["Wavelength"]),
                                    scan_amplitude = float(metadata["Scan amplitude"]))

    def check_in_db(self, name):
        with self.db_manager.connect() as conn:
            cursor = conn.cursor()

            # SQL query to check if the file path exists
            cursor.execute("SELECT COUNT(*) FROM spectra WHERE name = ?", (name,))

            # Fetch the result
            count = cursor.fetchone()[0]

        # Return True if the file exists, otherwise False
        return count > 0

    def create_bh5_file(self, name, data):
        # Create the BH5 file directory where all BH5 of database will be stored
        directory_db = '/'.join(self.db_manager.db_path.split('/')[:-1])
        try:
            os.mkdir(directory_db+"/BH5_files")
        except FileExistsError:
            pass
        except PermissionError:
            QMessageBox.critical(self.main_gui, "Error", f"BH5 directory couldn't be created due to permission error")
        except Exception as e:
            QMessageBox.critical(self.main_gui, "Error", f"BH5 directory couldn't be created")
        
        bh5_path = directory_db+"/BH5_files/"+name+".bh5"

        # Create BH5 file
        with h5py.File(bh5_path, 'w') as f:
            # Create the '/data' group and attributes
            datag = f.create_group('Data')
            datag.create_dataset('Raw_data', data = data)
        
        return bh5_path

class CustomHeader(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.main_window = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.main_window.show_column_selector(event.pos())  # Pass the click position
        else:
            super().mousePressEvent(event)

    def sectionResized(self, logicalIndex, oldSize, newSize):
        super().sectionResized(logicalIndex, oldSize, newSize)

class DatabaseManager:
    def __init__(self, db_path, config):
        self.db_path = db_path
        self.config = config

    def create_table(self):
        with self.connect() as conn:
            cursor = conn.cursor()

            # Create the create table command with all the parameters in the configuration file
            cmd = "CREATE TABLE IF NOT EXISTS spectra ("
            for e in self.config["Database Columns"]:
                cmd = cmd + e + " " + self.config["Database Columns"][e] + ","
            cmd = cmd[:-1] + ")"

            cursor.execute(cmd)
            conn.commit()

    def connect(self, compatibility = False):
        conn = sqlite3.connect(self.db_path)
        
        if compatibility:
            cursor = conn.cursor()
        
            # Fetch the column names of the spectra table
            cursor.execute("PRAGMA table_info(spectra)")
            columns = cursor.fetchall()

            # Extract the column names and print them
            column_db = [column[1] for column in columns]
            column_config = [e for e in self.config["Database Columns"]]

            column_db.sort()
            column_config.sort()
            
            if column_config != column_db: 
                if len(column_config)>len(column_db): # If the new standard has added columns, we alter the db to add the columns
                    new_columns = []
                    cmd = "ALTER TABLE spectra ADD "
                    for e in column_config:
                        if not e in column_db: 
                            cmd = cmd + e + " " + self.config["Database Columns"][e]
                    cursor.execute(cmd)
                    conn.commit()
        return conn

    def add_spectrum(self, name, data, bh5_filepath, **kwargs):
        date = kwargs.get("date", "Not specified")
        sample = kwargs.get('sample', "Not specified")
        brillouin_signal_type = kwargs.get("brillouin_signal_type","Not specified")
        scanning_strategy = kwargs.get("scanning_strategy", "Not specified")
        spectrometer_type = kwargs.get("spectrometer_type", "Not specified")
        laser_wavelength = kwargs.get("laser_wavelength", 0)
        scan_amplitude = kwargs.get("scan_amplitude", 0)
        acquisition_time = kwargs.get("acquisition_time", 0)
        laser_model = kwargs.get("laser_model", "Not specified")
        laser_power = kwargs.get("laser_power", 0)
        lens_NA = kwargs.get("lens_NA", 0)
        scattering_angle = kwargs.get("scattering_angle", 180)
        immersion_medium = kwargs.get("immersion_medium", "Not specified")
        objective_model = kwargs.get("objective_model", "Not specified")
        temperature = kwargs.get("temperature", 0)
        temperature_uncertainty = kwargs.get("temperature_uncertainty", 0)
        information = kwargs.get("information", "")

        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO spectra (name, filepath, date, sample, brillouin_signal_type, scanning_strategy, spectrometer_type, laser_wavelength, data_shape, TFP_range) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (name, bh5_filepath, date, sample, brillouin_signal_type, scanning_strategy, spectrometer_type, laser_wavelength, str(data.shape), scan_amplitude))
            conn.commit()

    def fetch_spectra(self):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM spectra")
            return cursor.fetchall()

    def remove_spectrum(self, filepath):
        """Remove a spectrum from the database by its filepath."""
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM spectra WHERE filepath=?", (filepath,))
                conn.commit()
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Failed to remove spectrum located at {filepath}: {e}")

class FileProperties(QDialog):
    def __init__(self, parent=None):
        self.parent = parent
        self.filepath_measure = parent.filepath_item
        self.parsed_data = {"MEASURE": [], "SPECTROMETER": [], "FILEPROP": []}

        super().__init__(parent)
        self.setWindowTitle("File Properties")
        self.setGeometry(100, 100, 800, 500)  # Set size and position of the window

        # Main layout for the window
        self.main_layout = QVBoxLayout()

        # Create a horizontal layout for the top row with an open file button
        top_layout = QHBoxLayout()
        self.open_file_button = QPushButton()
        self.open_file_button.setIcon(QIcon(loc + "img/open_config.png"))  # Replace with actual image path
        self.open_file_button.setIconSize(self.parent.icon_size)
        self.open_file_button.setToolTip("Complete informations with existing configuration file")
        self.open_file_button.setFixedSize(50, 50)  # Set a standard icon size
        self.open_file_button.clicked.connect(self.open_file_config)

        self.save_as_properties_button = QPushButton()
        self.save_as_properties_button.setIcon(QIcon(loc + "img/save_as.png"))  # Replace with actual image path
        self.save_as_properties_button.setIconSize(self.parent.icon_size)
        self.save_as_properties_button.setToolTip("Save the current configuration in a CSV file to reuse for further experiments")
        self.save_as_properties_button.setFixedSize(50, 50)  # Set a standard icon size
        self.save_as_properties_button.clicked.connect(self.save_as_properties)

        self.close_properties_button = QPushButton()
        self.close_properties_button.setIcon(QIcon(loc + "img/exit.png"))  # Replace with actual image path
        self.close_properties_button.setIconSize(self.parent.icon_size)
        self.close_properties_button.setToolTip("Save changes and close property window")
        self.close_properties_button.setFixedSize(50, 50)  # Set a standard icon size
        self.close_properties_button.clicked.connect(self.exit)

        top_layout.addWidget(self.open_file_button)
        top_layout.addWidget(self.save_as_properties_button)
        top_layout.addWidget(self.close_properties_button)
        top_layout.addStretch()

        # Add the top layout to the main layout
        self.main_layout.addLayout(top_layout)

       # Tab widget for different sections
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Initialize tabs with tables
        self.init_tabs()

        # Set the main layout for the dialog
        self.setLayout(self.main_layout)

    def init_tabs(self):
        # Create tabs for "Measure", "Spectrometer", and "File properties"
        self.measure_tab = QWidget()
        self.spectrometer_tab = QWidget()
        self.File_Properties_tab = QWidget()
        
        # Add tabs to the tab widget
        self.tab_widget.addTab(self.measure_tab, "Measure")
        self.tab_widget.addTab(self.spectrometer_tab, "Spectrometer")
        self.tab_widget.addTab(self.File_Properties_tab, "File properties")
        
        # Create tables in each tab and add them to the layouts
        self.measure_table = self.create_table()
        self.spectrometer_table = self.create_table()
        self.File_Properties_table = self.create_table()

        # Set the layouts for each tab
        self.measure_tab.setLayout(QVBoxLayout())
        self.spectrometer_tab.setLayout(QVBoxLayout())
        self.File_Properties_tab.setLayout(QVBoxLayout())

        # Add tables to each layout
        self.measure_tab.layout().addWidget(self.measure_table)
        self.spectrometer_tab.layout().addWidget(self.spectrometer_table)
        self.File_Properties_tab.layout().addWidget(self.File_Properties_table)

        # Populate table with attributes of HDF5 file
        self.populate_hdf5()

    def create_table(self):
        # Initialize a QTableWidget with 3 columns
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Property", "Value", "Unit"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return table

    def open_file_config(self):
        # Open a file dialog to select a .csv file
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Configuration File", "", "CSV Files (*.csv)")
        
        if file_path:
            # Parse the CSV file and display it in tables
            parsed_data = self.extract_information(file_path)
            self.populate_tables(parsed_data)

    def populate_hdf5(self):
        self.parsed_data["FILEPROP"].append(("Filepath",self.filepath_measure,""))
        with h5py.File(self.filepath_measure, 'r') as f:
            for e in f.attrs.keys():
                cat,prop = e.split('.')
                self.parsed_data[cat].append((prop, f.attrs[e], ""))
        self.extract_information(loc+"standard_parameters_v0.1.csv")
        self.populate_tables(self.parsed_data)

    def extract_information(self, file_path):
        current_section = "FILEPROP"

        # Read the CSV file
        with open(file_path, mode='r') as csvfile:
            reader = csv.reader(csvfile)
            skip_first = True
            for row in reader:
                if skip_first:
                    skip_first = False
                    continue

                if not row: continue  # Skip empty rows

                first_cell = row[0].strip()  # Trim whitespace
                if first_cell == "": continue # Skip rows with no information

                # Check if the first cell is a section header
                if first_cell.isupper() and first_cell.isalpha():
                    current_section = first_cell if first_cell in self.parsed_data else "FILEPROP"
                else:
                    # Add property to the current section
                    property_name = first_cell
                    property_value = row[1].strip() if len(row) > 1 else ""
                    property_unit = row[2].strip() if len(row) > 2 else ""

                    prec = []
                    for i, e in enumerate(self.parsed_data[current_section]):
                        if property_name == e[0]: 
                            prec = list(e)
                            if len(e[1])==0:
                                prec[1] = property_value
                            self.parsed_data[current_section].pop(i)
                    if len(prec)==0: 
                        self.parsed_data[current_section].append((property_name, property_value, property_unit))
                    else:
                        prec[-1] = property_unit
                        self.parsed_data[current_section].append(tuple(prec))

        return self.parsed_data

    def populate_tables(self, parsed_data):
        # Populate Measure table
        self.populate_table(self.measure_table, parsed_data.get("MEASURE", []))
        
        # Populate Spectrometer table
        self.populate_table(self.spectrometer_table, parsed_data.get("SPECTROMETER", []))
        
        # Populate File Properties table
        self.populate_table(self.File_Properties_table, parsed_data.get("FILEPROP", []))

    def populate_table(self, table, data):
        # Clear any existing rows in the table
        table.setRowCount(0)

        # Populate table with provided data
        for row_idx, (name, value, unit) in enumerate(data):
            table.insertRow(row_idx)
            table.setItem(row_idx, 0, QTableWidgetItem(name))
            table.setItem(row_idx, 1, QTableWidgetItem(value))
            table.setItem(row_idx, 2, QTableWidgetItem(unit))

    def save_as_properties(self):
        # Open a file dialog to specify where to save the CSV file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Properties As", "", "CSV Files (*.csv)")
        
        if not file_path:
            return  # If no file is selected, do nothing

        # Extract data from table
        extracted_data = {
            "MEASURE": self.extract_table_data(self.measure_table),
            "SPECTROMETER": self.extract_table_data(self.spectrometer_table),
            "FILEPROP": self.extract_table_data(self.File_Properties_table),
        }

        # Define the file metadata
        file_name = file_path.split("/")[-1]
        file_name = file_name.split(".")[0]
        creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        version = self.parent.config["Version"]["brillouin_bh5"]
        
        try:
            # Write the CSV file
            with open(file_path, mode='w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write the file metadata as the first line
                writer.writerow([file_name, creation_date, version])
                
                # Loop through each section in self.extracted_data and write the properties
                for key, data in extracted_data.items():
                    writer.writerow([])  # Blank line before each section
                    writer.writerow([key.upper()])  # Write the section name
                    
                    # Write each property (name, value, unit) in the section
                    for name, value, unit in data:
                        writer.writerow([name, value, unit])  # Assuming empty unit for now
                        
        except Exception as e:
            print(f"Error saving properties to file: {e}")

    def exit(self):
        # Retrieve names and values for each tab
        self.extracted_data = {
            "MEASURE": self.extract_table_data(self.measure_table),
            "SPECTROMETER": self.extract_table_data(self.spectrometer_table),
            "FILEPROP": self.extract_table_data(self.File_Properties_table),
        }

        with h5py.File(self.filepath_measure, 'a') as f:
            for k in ["MEASURE","SPECTROMETER","FILEPROP"]:
                for (name, val, _) in self.extracted_data[k]:
                    s = k+'.'+name
                    f.attrs[s] = val

        # Close the dialog
        self.close()

    def extract_table_data(self, table):
        data = []
        for row in range(table.rowCount()):
            name = table.item(row, 0).text() if table.item(row, 0) else ""
            value = table.item(row, 1).text() if table.item(row, 1) else ""
            unit = table.item(row, 2).text() if table.item(row, 1) else ""
            data.append((name, value, unit))
        return data

class TreatSpectra(QMainWindow):
    def __init__(self, parent, spectra_selected):
        super().__init__(parent)

        self.spectra_selected = spectra_selected
        self.setWindowTitle("Treat Spectra")
        self.setGeometry(100, 100, 1000, 600)  # Window size
        
        self.initUI()

    def initUI(self):
        # Main layout
        main_layout = QHBoxLayout()

        # Left: Matplotlib plot for raw spectra
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        
        # Create a vertical layout for the canvas and toolbar
        left_layout = QVBoxLayout()
        self.toolbar = NavigationToolbar(self.canvas, self) # Add the Matplotlib toolbar
        left_layout.addWidget(self.toolbar)  # Add toolbar at the top
        left_layout.addWidget(self.canvas)  # Add canvas below the toolbar

        # Right: Combo box for spectrum selection and treatment options
        self.right_layout = QVBoxLayout()

        # Vary presentation in function of the number of spectra to treat
        if len(self.spectra_selected) == 1:
            self.treat_selected_spectrum_button = QPushButton("Treat selected spectrum")
            self.treat_selected_spectrum_button.clicked.connect(self.treat_selected)
            self.right_layout.addWidget(self.treat_selected_spectrum_button)
        else:
            # Create and add a combo box to choose spectra
            self.combo_box = QComboBox()
            self.combo_box.addItem("Display All")
            for spectrum in self.spectra_selected:
                self.combo_box.addItem(spectrum[1])
            self.combo_box.currentIndexChanged.connect(self.select_spectrum)

            self.treat_all_spectra_button = QPushButton("Treat all selected spectra")
            self.treat_all_spectra_button.clicked.connect(self.treat_all)
            self.treat_selected_spectrum_button = QPushButton("Treat selected spectrum")
            self.treat_selected_spectrum_button.clicked.connect(self.treat_selected)
            self.treat_selected_spectrum_button.setEnabled(False)
        
            self.right_layout.addWidget(self.treat_all_spectra_button)
            self.right_layout.addWidget(QLabel("Or select Spectrum to treat:"))
            self.right_layout.addWidget(self.combo_box)
            self.right_layout.addWidget(self.treat_selected_spectrum_button)

        self.right_layout.addStretch()  # Push other widgets up

        # Add both sections to the main layout
        right_frame = QFrame()  # Create a frame for the right section
        right_frame.setLayout(self.right_layout)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(right_frame)

        # Set layout in central widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Plot all spectra by default
        self.plot_all_spectra()

    def plot_all_spectra(self):
        self.ax.clear()  # Clear previous plots
        for spectrum in self.spectra_selected:
            self.plot_raw_spectra(spectrum[2])
        self.ax.set_title("All Selected Spectra")
        self.ax.set_xlabel("Spectral channels")
        self.ax.set_ylabel("Counts on detector")
        self.canvas.draw()

    def select_spectrum(self):
        selected_spectrum = self.combo_box.currentText()
        self.ax.clear()  # Clear previous plot

        if selected_spectrum == "Display All":
            self.plot_all_spectra()
            self.frequency_button.setEnabled(False)  # Disable frequency button when all spectra are displayed
        else:
            self.treat_selected_spectrum_button.setEnabled(True)
            # Plot only the selected spectrum
            for spectrum in self.spectra_selected:
                if spectrum[1] == selected_spectrum:
                    self.plot_raw_spectra(spectrum[2]) 

        self.canvas.draw()

    def treat_all(self):
        QMessageBox.information(self, "To do", "Treatment of all spectra not implemented.")

    def treat_selected(self):
        def enable_treat_button():
            self.add_treatment_button.setEnabled(True)

        # Clear right pane
        for i in reversed(range(self.right_layout.count())):
            widget = self.right_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # Extract the filepath of the file to treat
        try:
            selected_spectrum = self.combo_box.currentText()
        except:
            selected_spectrum = self.spectra_selected[0][1]
        for spectrum in self.spectra_selected:
            if spectrum[1] == selected_spectrum:
                filepath = spectrum[2]
        
        # Open bh5 file and get the raw data and frequency
        with h5py.File(filepath, 'a') as f:
            spectrometer_type = f.attrs["SPECTROMETER.Type"]
            date_created = f.attrs["MEASURE.Date_of_measure"]
            arr = f["Data"]["Raw_data"][:]
            
            # Generate or retrieve the frequency axis
            if spectrometer_type == "TFP": 
                scan_amplitude = float(f.attrs["SPECTROMETER.Scan_Amplitude"])
                if "Frequency" in f["Data"]:
                    if QMessageBox.question(
                        self, 'Replace Frequency Axis',
                        "Do you want to replace the existing frequency axis?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    ) == QMessageBox.Yes:
                        frequency = np.linspace(-scan_amplitude/2, scan_amplitude/2, arr.shape[-1])
                        f["Data"]["Frequency"][...] = frequency
                        f["Data"]["Frequency"].attrs["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        date_frequency = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        frequency = f["Data"]["Frequency"][:]
                        date_frequency = f["Data"]["Frequency"].attrs["Date"]
                else:
                    frequency = np.linspace(-scan_amplitude/2, scan_amplitude/2, arr.shape[-1])
                    f["Data"].create_dataset("Frequency", data=frequency)
                    f["Data"]["Frequency"].attrs["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    date_frequency = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Plot the spectrum
                self.ax.clear()
                self.ax.plot(frequency, arr)
                self.ax.set_title("Raw Spectrum")
                self.ax.set_xlabel("Frequency shift (GHz)")
                self.ax.set_ylabel("Counts on detector")
                self.canvas.draw()

        # Create the combobox used to add treatment steps
        self.combo_box_treat = QComboBox()
        self.combo_box_treat.addItem("Treatmen steps")
        self.combo_box_treat.addItem("--Substract Noise Average--")
        self.combo_box_treat.addItem("--Normalize intensity of peak to unity--")
        self.combo_box_treat.addItem("--DHO fit on peak doublet with elastic peak compensation--")
        self.combo_box_treat.addItem("--DHO fit on peak doublet without elastic peak compensation--")
        self.combo_box_treat.addItem("--Lorentzian fit on peak doublet with elastic peak compensation--")
        self.combo_box_treat.addItem("--Lorentzian fit on peak doublet without elastic peak compensation--")
        
        self.combo_box_treat.activated.connect(enable_treat_button)

        self.add_treatment_button = QPushButton("Add treatment to selected data")
        self.add_treatment_button.clicked.connect(self.add_treatment)
        self.add_treatment_button.setEnabled(False)

        # Create a QTreeWidget for displaying treatment steps
        self.treeview = QTreeWidget()
        self.treeview.setColumnCount(2)
        self.treeview.setHeaderLabels(["Name", "Date Created"])

        # Add the initial raw data entry to the tree view
        self.treeview_treat_frequency_item = QTreeWidgetItem(["frequency", date_frequency])
        self.treeview_treat_raw_data_item = QTreeWidgetItem(["raw_data", date_created])
        self.treeview.addTopLevelItem(self.treeview_treat_frequency_item)
        self.treeview.addTopLevelItem(self.treeview_treat_raw_data_item)
        self.treeview_dict = {"frequency": {"parent": self.treeview_treat_frequency_item}, 
                              "raw_data": {"parent": self.treeview_treat_raw_data_item}}

        # Add the tree view to the right layout
        self.right_layout.addWidget(self.treeview)
        self.right_layout.addWidget(self.combo_box_treat)
        self.right_layout.addWidget(self.add_treatment_button)
        self.right_layout.addStretch()

    def add_treatment(self):
        # Check if an item in the tree view is selected
        selected_item = self.treeview.currentItem()
        if selected_item is None:
            QMessageBox.warning(self, "Selection Error", "Please select an item in the treatment steps.")
            return

        # Extract the name of the selected item in the tree view
        selected_item_name = selected_item.text(0)

        # Extract the selected treatment from the combo box
        selected_treatment = self.combo_box_treat.currentText()

        QMessageBox.information(self, "To do", f"Selected item name: {selected_item_name}, selected treatment: {selected_treatment}")

    def plot_raw_spectra(self, file_path):
        try:
            # Open the .bh5 file and extract the raw data
            with h5py.File(file_path, 'r') as f:
                raw_data = f['Data']['Raw_data'][:]
            self.ax.plot(raw_data)
            self.ax.set_title("Raw Spectrum")
            self.ax.set_xlabel("Spectral channels")
            self.ax.set_ylabel("Counts on detector")
            self.canvas.draw()

        except Exception as e:
            QMessageBox(self,"Plot failure",f"Failed to load or plot raw spectrum: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        self.db_manager = None
        self.icon_size = QSize(40, 40)  # Define the icon size for the buttons
        self.config = configparser.ConfigParser()
        self.config.read(loc+"config.ini") # Load configuration file
        self.db_tools = False

        super().__init__()
        self.setWindowTitle("Spectra Treatment GUI")
        self.create_GUI()
    
    def create_GUI(self):
        def create_left_buttons(self):
            left_button_box = QHBoxLayout()

            # Create the buttons with images (replace with your image paths)
            new_db_button = QPushButton()
            new_db_button.setIcon(QIcon(loc + "img/new_db.png"))
            new_db_button.setIconSize(self.icon_size)
            new_db_button.setFixedSize(50, 50) 
            new_db_button.setToolTip("Create a new database")
            new_db_button.clicked.connect(self.new_db)

            open_db_button = QPushButton()
            open_db_button.setIcon(QIcon(loc + "img/open_db.png"))
            open_db_button.setIconSize(self.icon_size)
            open_db_button.setFixedSize(50, 50) 
            open_db_button.setToolTip("Open a database")
            open_db_button.clicked.connect(self.open_db)

            # Add the new and open buttons to the left button box
            left_button_box.addWidget(new_db_button)
            left_button_box.addWidget(open_db_button)
            left_button_box.addSpacing(5)  # Space between buttons

            return left_button_box

        def create_right_buttons(self):
            right_button_box = QHBoxLayout()
            close_db_button = QPushButton()
            close_db_button.setIcon(QIcon(loc + "img/exit.png"))
            close_db_button.setIconSize(self.icon_size)
            close_db_button.setFixedSize(50, 50) 
            close_db_button.setToolTip("Close program")
            close_db_button.clicked.connect(self.close)  # Native closing function

            # Add the new and open buttons to the left button box
            right_button_box.addWidget(close_db_button)
            right_button_box.addSpacing(5)  # Space between buttons

            return right_button_box

        def create_table(self):
            # Create a QTableWidget to display the spectra
            table_widget = QTableWidget()
            column_names = [e for e in self.config['Database Columns']]
            table_widget.setColumnCount(len(column_names))  # Adjust based on your database columns
            table_widget.setHorizontalHeaderLabels(column_names)  # Set the headers
            table_widget.setRowCount(0)  # Initially, no rows

            # Set custom header view to intercept right-clicks
            header = CustomHeader(Qt.Horizontal, self)
            table_widget.setHorizontalHeader(header)

            # Enable context menu policy
            table_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            table_widget.customContextMenuRequested.connect(self.file_properties)

            return table_widget

        # Create a widget to act as the central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create layout
        main_layout = QVBoxLayout() # Create a vertical layout for the main layout
        button_box = QHBoxLayout()# Create a horizontal layout for the buttons

        # Add the buttons to the button box
        self.left_button_box = create_left_buttons(self)# Create a horizontal layout for the left-side buttons
        button_box.addLayout(self.left_button_box)
        button_box.addStretch()  # This will push the close button to the right
        self.right_button_box = create_right_buttons(self)# Create a horizontal layout for the left-side buttons
        button_box.addLayout(self.right_button_box)

        # Add the button box and the table to the main layout
        main_layout.addLayout(button_box)
        self.table_widget = create_table(self)
        main_layout.addWidget(self.table_widget)

        # Set the main layout to the central widget
        central_widget.setLayout(main_layout)

    def new_db(self):
        # Open a file dialog to select the location and name for the new database
        db_path, _ = QFileDialog.getSaveFileName(self, "Save New Database", "", "SQLite Database (*.db);;All Files (*)")

        if db_path:  # Check if a path was selected
            try:
                # Create a new DatabaseManager instance
                self.db_manager = DatabaseManager(db_path, self.config)
                self.db_manager.create_table()
                self.add_db_tools()  # Call to add database tools

            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to create database: {e}")

    def open_db(self):
        # Open a file dialog to select an existing database
        db_path, _ = QFileDialog.getOpenFileName(self, "Open Database", "", "SQLite Database (*.db);;All Files (*)")

        if db_path:  # Check if a path was selected
            try:
                # Create a new DatabaseManager instance
                self.db_manager = DatabaseManager(db_path, self.config)
                self.db_manager.connect(compatibility=True)
                if not self.db_tools: self.add_db_tools()  # Call to add database tools
                self.update_table(init = True)

            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to open database: {e}")

    def add_db_tools(self):
        # Create a vertical layout for the new buttons
        db_tools_layout = QVBoxLayout()

        # Create the buttons for database operations
        add_spectrum_button = QPushButton()
        add_spectrum_button.setIcon(QIcon(loc+"img/add_spectra.png"))
        add_spectrum_button.setIconSize(self.icon_size)
        add_spectrum_button.setFixedSize(50,50)
        add_spectrum_button.setToolTip("Add a spectrum to the database")
        add_spectrum_button.clicked.connect(self.add_spectrum)

        remove_spectrum_button = QPushButton()
        remove_spectrum_button.setIcon(QIcon(loc+"img/remove_spectra.png"))
        remove_spectrum_button.setIconSize(self.icon_size)
        remove_spectrum_button.setFixedSize(50,50)
        remove_spectrum_button.setToolTip("Remove the spectrum/a from database")
        remove_spectrum_button.clicked.connect(self.remove_spectrum)  # Placeholder function

        display_raw_spectrum_button = QPushButton()
        display_raw_spectrum_button.setIcon(QIcon(loc+"img/display_raw_spectra.png"))
        display_raw_spectrum_button.setIconSize(self.icon_size)
        display_raw_spectrum_button.setFixedSize(50,50)
        display_raw_spectrum_button.setToolTip("Display the raw spectrum/a")
        display_raw_spectrum_button.clicked.connect(self.display_raw_spectrum)  # Placeholder function

        display_treated_spectrum_button = QPushButton()
        display_treated_spectrum_button.setIcon(QIcon(loc+"img/display_treat_spectra.png"))
        display_treated_spectrum_button.setIconSize(self.icon_size)
        display_treated_spectrum_button.setFixedSize(50,50)
        display_treated_spectrum_button.setToolTip("Display the treated spectrum/a")
        display_treated_spectrum_button.clicked.connect(self.display_treated_spectrum)  # Placeholder function

        treat_spectrum_button = QPushButton()
        treat_spectrum_button.setIcon(QIcon(loc+"img/treat_spectra.png"))
        treat_spectrum_button.setIconSize(self.icon_size)
        treat_spectrum_button.setFixedSize(50,50)
        treat_spectrum_button.setToolTip("Treat the selected spectrum/a")
        treat_spectrum_button.clicked.connect(self.treat_spectrum)  # Placeholder function

        # Add buttons to the vertical layout
        self.left_button_box.addWidget(add_spectrum_button)
        self.left_button_box.addWidget(remove_spectrum_button)
        self.left_button_box.addWidget(display_raw_spectrum_button)
        self.left_button_box.addWidget(treat_spectrum_button)
        self.left_button_box.addWidget(display_treated_spectrum_button)
        

        # Add the new layout to the main layout
        self.centralWidget().layout().addLayout(db_tools_layout)

        self.db_tools = True
    
    def add_spectrum(self):
        # Open a file dialog to select a .DAT file
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Spectrum File", "", "DAT Files (*.DAT);;All Files (*)")

        if file_paths:  # Check if a file was selected
            for file_path in file_paths:
                try:
                    ImportSpectra(self.db_manager, file_path, self)
                    
                    #Update the table
                    self.update_table()

                except sqlite3.Error as e:
                    QMessageBox.critical(self, "Error", f"Failed to add spectrum: {e}")

    def apply_column_selection(self, dialog):
        # Loop through all checkboxes and show/hide columns based on their state
        for checkbox, index in self.column_checkboxes:
            if checkbox.isChecked():
                self.table_widget.setColumnHidden(index, False)  # Show the column
            else:
                self.table_widget.setColumnHidden(index, True)  # Hide the column
        dialog.close()

    def show_column_selector(self, pos):
        context_menu = QMenu(self)
        column_names = [e for e in self.config['Database Columns']]  # Fetch column names from config

        for i, name in enumerate(column_names):
            action = context_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not self.table_widget.isColumnHidden(i))  # Check if column is visible

            # Use functools.partial to capture the index correctly
            action.triggered.connect(partial(self.toggle_column_visibility, i))

        context_menu.exec_(self.table_widget.viewport().mapToGlobal(pos))  # Use the click position

    def toggle_column_visibility(self, index, checked):
        self.table_widget.setColumnHidden(index, not checked)  # Show the column if checked

    def remove_spectrum(self):
        # Get the selected rows from the table
        selected_items = self.table_widget.selectedItems()
        spectra = self.db_manager.fetch_spectra()
        
        if selected_items:
            spectra_to_remove = []
            for item in selected_items:
                row = item.row()
                spectra_to_remove.append(spectra[row])
            
            # Confirm deletion from the database
            reply = QMessageBox.question(
                self, 'Remove Spectrum',
                f"Are you sure you want to remove the selected spectra from the database?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                for spectrum_id in spectra_to_remove:
                    try:
                        print(spectrum_id[2])
                        # Call DatabaseManager to remove the spectrum
                        self.db_manager.remove_spectrum(spectrum_id[2])
                        
                        # Ask if BH5 file should also be deleted
                        bh5_file_path = spectrum_id[2]
                        if os.path.isfile(bh5_file_path):
                            delete_bh5 = QMessageBox.question(
                                self, 'Delete BH5 File',
                                f"Do you also want to delete the BH5 file for spectrum ID {spectrum_id[1]}?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                            )
                            if delete_bh5 == QMessageBox.Yes:
                                os.remove(bh5_file_path)
                        
                        # Update the table after removal
                        self.update_table()

                    except sqlite3.Error as e:
                        QMessageBox.critical(self, "Error", f"Failed to remove spectrum: {e}")

    def display_raw_spectrum(self):
        # Get the item at the clicked position
        selected_items = self.table_widget.selectedItems()

        # Fetch the spectra from the database
        spectra = self.db_manager.fetch_spectra()
        
        # Create a new matplotlib window
        fig, ax = plt.subplots(figsize=(8, 6))

        for item in selected_items:
            row = item.row()
            spectrum = spectra[row]

            file_path = spectrum[2]  # Assuming the path is in the third column

            try:
                # Open the .bh5 file
                with h5py.File(file_path, 'r') as f:
                    # Navigate to the group "Data" and dataset "Raw_data"
                    raw_data = f['Data']['Raw_data'][:]

                    if spectrum[7] == "FP": 
                        range = spectrum[23]
                        nu = np.linspace(-0.5,0.5,raw_data.size)*range
                        xlabel = "Frequency (GHz)"
                    else:
                        nu = np.arange(raw_data.size)
                        xlabel = "X-axis"
                    
                    # Plot the raw data (assuming it's 1D)
                    ax.plot(nu, raw_data, label=spectrum[1])  # Use the spectrum name as label (second column)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load spectrum from {file_path}: {e}")
                return

        # Customize the plot
        ax.set_title("Raw Spectra")
        ax.set_xlabel(xlabel)  # Modify as needed based on your data
        ax.set_ylabel("Intensity")  # Modify as needed
        ax.legend()

        # Display the plot in a new matplotlib window
        plt.show()

    def display_treated_spectrum(self):
        QMessageBox.information(self, "To do", "Displaying of treated spectra not yet implemented.")

    def treat_spectrum(self):
        # Get the item at the clicked position
        selected_items = self.table_widget.selectedItems()
        spectra = self.db_manager.fetch_spectra()  # Fetch spectra from the database

        spectra_selected = [spectra[item.row()] for item in selected_items]

        if spectra_selected:  # Ensure there are spectra to treat
            # Open the treatment window and pass the spectra to it
            self.treat_spectra_window = TreatSpectra(self, spectra_selected)
            self.treat_spectra_window.show()
    
    def update_properties(self, file_path):
        # Open the FileProperties window
        self.filepath_item = file_path
        self.File_Properties_window = FileProperties(self)
        self.File_Properties_window.exec_()

    def file_properties(self, pos):
        # Get the item at the clicked position
        item = self.table_widget.itemAt(pos)

        # Proceed only if an item was clicked
        if item:
            row = item.row()
            file_path_item = self.table_widget.item(row, 2)  # Get the 'Path' item
            if file_path_item:
                file_path = file_path_item.text()

                # Create a context menu for right-click
                context_menu = QMenu(self)
                copy_action = context_menu.addAction("Copy File Path")
                context_menu.addSeparator()
                properties_action = context_menu.addAction("Edit Properties")
                context_menu.addSeparator()
                delete_action = context_menu.addAction("Delete Data")
                context_menu.addSeparator()
                disp_raw_action = context_menu.addAction("Display Raw Spectrum/a")
                disp_treat_action = context_menu.addAction("Display Treated Spectrum/a")
                context_menu.addSeparator()
                treat_action = context_menu.addAction("Treat Data")


                # Show context menu
                action = context_menu.exec_(self.table_widget.viewport().mapToGlobal(pos))

                if action == copy_action:
                    # Copy the file path to the clipboard
                    pyperclip.copy(file_path)
                    QMessageBox.information(self, "Copied", "File path copied to clipboard.")
                
                elif action == properties_action:
                    self.update_properties(file_path)

                elif action == delete_action:
                    self.remove_spectrum()
                
                elif action == disp_raw_action:
                    self.display_raw_spectrum()

                elif action == disp_treat_action:
                    self.display_treated_spectrum()
                
                elif action == treat_action:
                    self.treat_spectrum()

    def update_table(self, init = False):
        # Clear the table before updating
        self.table_widget.setRowCount(0)

        # Fetch spectra from the database
        spectra = self.db_manager.fetch_spectra()

        # Define the indices of the columns you want to display
        column_names = [e for e in self.config['Database Columns']]  # Fetch column names from config
        columns_to_show = [e for e in self.config['Columns at opening']]
        columns_indices = [column_names.index(col) for col in columns_to_show if col in column_names]

        for spectrum in spectra:
            row_position = self.table_widget.rowCount()  # Get current row count
            self.table_widget.insertRow(row_position)  # Insert a new row

            # Populate the row with only the specified columns
            for column in range(len(column_names)):
                self.table_widget.setItem(row_position, column, QTableWidgetItem(str(spectrum[column])))
        
        # Show only specified columns
        for i in range(len(column_names)):
            self.table_widget.setColumnHidden(i, i not in columns_indices)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = MainWindow()
    
    # Open the window in maximized screen
    window.showMaximized()
    
    sys.exit(app.exec_())
