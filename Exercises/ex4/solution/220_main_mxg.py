import re
import sys

import pyvisa
#  Need to avoid hidden dependency to "compile" with pyinstaller
import pyvisa_py

import pyarbtools as arb
import yaml
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.uic import loadUi

from python_rf_course_utils.qt import h_gui
from python_rf_course_utils.arb import multitone

def is_valid_ip(ip:str) -> bool:
    # Regular expression pattern for matching IP address
    ip_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return re.match(ip_pattern, ip) is not None

# Load the UI file into the Class (LabDemoMxgControl) object
# The UI file (BasicMxgControl.ui) is created using Qt Designer
# The UI file is located in the same directory as this Python script
# The GUI controller clas inherit from QMainWindow object as defined in the ui file
class LabDemoMxgControl(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load the UI file into the Class (LabDemoMxgControl) object
        loadUi("MxgControlMultiTone.ui", self)
        # Apply light theme stylesheet for clear visibility
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QWidget {
                background-color: #ffffff;
                color: #202020;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #e8e8e8;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                padding: 5px 15px;
                color: #202020;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
                border: 1px solid #808080;
            }
            QPushButton:pressed {
                background-color: #b8b8b8;
            }
            QPushButton:checked {
                background-color: #90c8f0;
                border: 1px solid #4080c0;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #c0c0c0;
                border-radius: 3px;
                padding: 3px;
                color: #000000;
            }
            QLineEdit:focus {
                border: 2px solid #4080c0;
            }
            QSlider::groove:horizontal {
                background: #d0d0d0;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4080c0;
                border: 1px solid #2060a0;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QDial {
                background-color: #f0f0f0;
            }
            QDoubleSpinBox, QSpinBox {
                background-color: #ffffff;
                border: 2px solid #c0c0c0;
                border-radius: 3px;
                padding: 2px;
                color: #000000;
            }
            QLCDNumber {
                background-color: #e0e0e0;
                border: 1px solid #a0a0a0;
                color: #000000;
            }
            QLabel {
                color: #202020;
                background-color: transparent;
            }
            QMenuBar {
                background-color: #f0f0f0;
                color: #202020;
            }
            QMenuBar::item:selected {
                background-color: #d0d0d0;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
                color: #202020;
            }
            QMenu::item:selected {
                background-color: #90c8f0;
            }
        """)

        self.setWindowTitle("MXG Control")

        # Interface of the GUI Widgets to the Python code
        self.h_gui = dict(
            Connect             = h_gui(self.pushButton         , self.cb_connect           ),
            RF_On_Off           = h_gui(self.pushButton_2       , self.cb_rf_on_off         ),
            Mod_On_Off          = h_gui(self.pushButton_3       , self.cb_mod_on_off        ),
            IP                  = h_gui(self.lineEdit           , self.cb_ip                ),
            Fc                  = h_gui(self.lineEdit_2         , self.cb_fc                ),
            Pout                = h_gui(self.horizontalSlider   , self.cb_pout_slider       ),
            Save                = h_gui(self.actionSave         , self.cb_save              ),
            Load                = h_gui(self.actionLoad         , self.cb_load              ),
            MultiTone_On_Off    = h_gui(self.pushButton_4       , self.cb_multitone_on_off  ),
            MultiToneBw         = h_gui(self.doubleSpinBox      , self.cb_multitone_update  ),
            MultiToneNtones     = h_gui(self.dial               , self.cb_multitone_update  ))

        # Create a Resource Manager object
        self.rm         = pyvisa.ResourceManager('@py')
        self.sig_gen    = None
        self.arb_gen    = None


        # Load the configuration/default values from the YAML file
        self.Params     = None
        self.file_name  = "sig_gen_defaults.yaml"
        self.h_gui['Load'].emit() #  self.cb_load

        self.file_name = "last.yaml"
        try:
            self.h_gui['Load'].callback()  # self.cb_load
        except FileNotFoundError:
            print("No last.yaml file found")

        self.h_gui['Save'].emit() #  self.cb_save

    def sig_gen_write(self, cmd:str):
        if self.sig_gen is not None:
            self.sig_gen.write(cmd)

    # Callback function for the Connect button
    # That is a checkable button
    def cb_connect(self):
        if self.sender().isChecked(): # self.h_gui['Connect'].obj.isChecked():
            print("Connect button Checked")
            # Open the connection to the signal generator
            try:
                ip           = self.h_gui['IP'].get_val()
                self.sig_gen = self.rm.open_resource(f"TCPIP0::{ip}::inst0::INSTR")
                print(f"Connected to {ip}")
                # Read the signal generator status and update the GUI (RF On/Off, Modulation On/Off,Pout and Fc)
                # Query the signal generator name
                # <company_name>, <model_number>, <serial_number>,<firmware_revision>
                # Remove the firmware revision
                idn         = self.sig_gen.query("*IDN?").strip().split(',')[0:3]
                idn         = ','.join(idn)
                self.setWindowTitle(idn)
                self.sig_gen.write("*CLS")
                # Query RF On/Off mode
                self.sig_gen.write(":OUTPUT:STATE?")
                rf_state    = bool(int(self.sig_gen.read().strip()))
                # Query Modulation On/Off mode
                self.sig_gen.write(":OUTPUT:MOD:STATE?")
                mod_state   = bool(int(self.sig_gen.read().strip()))
                # Query Output Power
                self.sig_gen.write(":POWER?")
                output_power_dbm = float(self.sig_gen.read())
                # Query Frequency
                self.sig_gen.write(":FREQ?")
                fc          = float(self.sig_gen.read()) * 1e-6

                # Update the GUI (no callbacks)
                self.h_gui['RF_On_Off'  ].set_val( rf_state)
                self.h_gui['Mod_On_Off' ].set_val(mod_state)
                self.h_gui['Pout'       ].set_val(output_power_dbm, is_callback=True) # True so the LCD will be updated
                self.h_gui['Fc'         ].set_val(fc)
            except Exception:
                if self.sig_gen is not None:
                    self.sig_gen.close()
                    self.sig_gen = None
                # Clear Button state
                self.sender().setChecked(False)
        else:
            print("Connect button Cleared")
            # Close the connection to the signal generator
            if self.sig_gen is not None:
                self.sig_gen.close()
                self.sig_gen = None

    # Callback function for the RF On/Off button
    # That is a checkable button
    def cb_rf_on_off(self):
        if self.sender().isChecked():
            self.sig_gen_write(":OUTPUT:STATE ON")
            print("RF On")
        else:
            self.sig_gen_write(":OUTPUT:STATE OFF")
            print("RF Off")

    # Callback function for the Modulation On/Off button
    # That is a checkable button
    def cb_mod_on_off(self):
        if self.sender().isChecked():
            self.sig_gen_write(":OUTPUT:MOD:STATE ON")
            print("Modulation On")
        else:
            self.sig_gen_write(":OUTPUT:MOD:STATE OFF")
            print("Modulation Off")

    # Callback function for the IP lineEdit
    def cb_ip(self):
        ip          = self.h_gui['IP'].get_val()
        # Check if the ip is a valid
        if not is_valid_ip(ip):
            print(f"Invalid IP address: {ip}, Resetting to default")
            ip = self.Params["IP"]
            # Set the default value to the GUI object
            self.h_gui['IP'].set_val(ip)

        print(f"IP = {ip}")

    # Callback function for the Fc lineEdit
    def cb_fc(self):
        # Check if the frequency is a valid float number
        try:
            frequency_mhz = self.h_gui['Fc'].get_val()
        except ValueError:
            print(f"Invalid Frequency: Resetting to default")
            frequency_mhz = self.Params["Fc"]
            # Set the default value to the GUI object
            self.h_gui['Fc'].set_val(frequency_mhz)

        self.sig_gen_write(f":FREQuency {frequency_mhz} MHz") # can replace the '} MHz' with '}e6'
        print(f"Fc = {frequency_mhz} MHz")

    def cb_pout_slider( self ):
        val = self.h_gui['Pout'].get_val()
        self.sig_gen_write(f":POWER {val} dBm")

        print(f"Pout = {val} dBm")

    def cb_save(self):
        print("Save")
        # Read the values from the GUI objects and save them to the Params dictionary
        for key, value in self.Params.items():
            if key in self.h_gui:
                self.Params[key] = self.h_gui[key].get_val()

        with open(self.file_name, "w") as f:
            yaml.dump(self.Params, f)

    def cb_load(self):
        print("Load")
        try:
            with open(self.file_name, "r") as f:
                self.Params = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"File not found: {self.file_name}")
            raise

        # Set the default values to the GUI objects
        for key, value in self.Params.items():
            if key in self.h_gui:
                self.h_gui[key].set_val(value, is_callback=True)

        # Additional configuration parameters
        self.h_gui['Pout'].call_widget_method('setMaximum',False,self.Params["PoutMax"])
        self.h_gui['Pout'].call_widget_method('setMinimum',False,self.Params["PoutMin"])

    # Callback function for the MultiTone On/Off button
    def cb_multitone_on_off(self):
        """
        Callback function for the MultiTone On/Off button
        Actions:
        - When the button is checked (On):
            - Create an ARB object
            - Configure the ARB object
            - Clear errors
            - Set ALC to Off
            - Call the MultiToneBw callback function to update the waveform
            - Set the Mod_On_Off and RF_On_Off buttons to On
        - When the button is unchecked (Off):
            - Stop and delete the ARB object
            - Set the Mod_On_Off button to Off
        """
        if self.sender().isChecked():
            print("MultiTone On")
            try:
                # Create ARB object
                mxg_ip         = self.h_gui['IP'].get_val()
                self.arb_gen    = arb.instruments.VSG(mxg_ip, timeout=3)
                self.arb_gen.configure(fs=self.Params['ArbMaxFs']*1e6, iqScale=70 )
                # Clear Errors
                self.sig_gen_write('*CLS')
                # Set the Auto Level Control to Off (ALC)
                # Note - It is critical not to use boolean types for the SCPI commands!
                self.arb_gen.set_alcState(0)
                self.h_gui['MultiToneBw'].callback()
                # Set GUI MOD to On
                self.h_gui['Mod_On_Off'].set_val(True, is_callback=False)
                self.h_gui['RF_On_Off' ].set_val(True, is_callback=False)
            except Exception as e:
                print(f"Error: {e}")
                self.h_gui['Mod_On_Off'].set_val(False, is_callback=True)
                self.h_gui['RF_On_Off' ].set_val(False, is_callback=True)
                if self.arb_gen is not None:
                    self.arb_gen = None
                # Clear Button state
                self.sender().setChecked(False)
        else:
            print("MultiTone Off")
            if self.arb_gen is not None:
                self.arb_gen.stop()
                self.arb_gen = None
            self.h_gui['Mod_On_Off'].set_val(False, is_callback=False)

    def cb_multitone_update(self):
        """
        Callback function for the MultiTone Bandwidth and Number of Tones
        Sequence of actions:
        - Print the MultiTone Bandwidth and Number of Tones
        - If the ARB object is not None:
            - Generate the MultiTone waveform using the multitone function
            - Download the waveform to the ARB object
            - Play the waveform
        """
        print(f"MultiTone Bandwidth = {self.h_gui['MultiToneBw'].get_val()} MHz")
        print(f"MultiTone Number of Tones = {self.h_gui['MultiToneNtones'].get_val()}")
        if self.arb_gen is not None:
            sig = multitone(BW=self.h_gui['MultiToneBw'].get_val(), Ntones=self.h_gui['MultiToneNtones'].get_val(),
                            Fs=self.Params['ArbMaxFs'], Nfft=2048)
            self.arb_gen.download_wfm(sig, wfmID='RfLabMultiTone')
            self.arb_gen.play('RfLabMultiTone')

    def closeEvent(self, event):
        print("Exiting the application")
        # Clean up the resources
        # Close the connection to the signal generator
        if self.sig_gen is not None:
            self.sig_gen.close()
        # Close the Resource Manager
        self.rm.close()

if __name__ == "__main__":
    # Initializes the application and prepares it to run a Qt event loop
    #  it is necessary to create an instance of this class before any GUI elements can be created
    app         = QApplication( sys.argv )
    # Create the LabDemoMxgControl object
    controller  = LabDemoMxgControl()
    # Show the GUI
    controller.show()
    # Start the Qt event loop (the sys.exit is for correct exit status to the OS)
    sys.exit(app.exec())
