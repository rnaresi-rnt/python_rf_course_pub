import re
import sys

import pyvisa
# EX4: Add pyarbtools, name it arb. (slide 3-51 example 219)

import yaml
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.uic import loadUi

# EX4: import h_gui from the python_rf_course_utils.qt directory (slide 2-7)

# EX4: import the multitone module from the python_rf_course_utils.arb directory (slide 2-7)

def is_valid_ip(ip:str) -> bool:
    # Regular expression pattern for matching IP address
    ip_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return re.match(ip_pattern, ip) is not None

# The GUI controller clas inherit from QMainWindow object as defined in the ui file
class LabDemoMxgControl(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load the UI file into the Class (LabDemoMxgControl) object
        # EX4: Change the file name to your new ui file
        loadUi("BasicMxgControl.ui", self)

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
            Load                = h_gui(self.actionLoad         , self.cb_load              ))
        # EX4: Add the new widgets to the h_gui dictionary use the following callbacks:
        # EX4:  cb_multitone_update (use the same callback for the BW and the Ntones)
        # EX4:  cb_multitone_on_off (slide 3-46 example 210)

        # Create a Resource Manager object
        self.rm         = pyvisa.ResourceManager('@py') # EX4: make sure - '@py' is for the PyVISA-py backend
        self.sig_gen    = None
        # EX4: define similarly arb_gen


        # Load the configuration/default values from the YAML file
        self.Params     = None
        # EX4: Don't forget to update the YAML file
        self.file_name  = "sig_gen_defaults.yaml"
        self.h_gui['Load'].emit() #  self.cb_load

        self.file_name = "last.yaml"
        try:
            self.h_gui['Load'].callback()  # self.cb_load - override the parameters from last.yaml by calling the cb function
        except FileNotFoundError: # File wasn't found
            print("No last.yaml file found")

        self.h_gui['Save'].emit() #  self.cb_save - save the existing parameters to last.yaml

    def sig_gen_write(self, cmd):
        """
        Accessor method to write to the sig_gen object if it exists
        Args:
            cmd: SCPI command to write
        """
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
                # EX4: Query the signal generator IDN string (Slide 2-62 ex 109)
                # EX4: Note the fields are <company_name>, <model_number>, <serial_number>,<firmware_revision>
                # EX4: split and join the fields without the firmware revision seperated by a comma
                # EX4: Update the window title with the joined string (Page 3-34 ex 200)

                # Query RF On/Off mode
                rf_state            = bool(int(self.sig_gen.query(":OUTPUT:STATE?"      ).strip()))
                # Query Modulation On/Off mode
                mod_state           = bool(int(self.sig_gen.query(":OUTPUT:MOD:STATE?"  ).strip()))
                # Query Output Power
                output_power_dbm    = float(self.sig_gen.query(":POWER?").strip())
                # Query Frequency
                fc                  = float(self.sig_gen.query(":FREQ?" ).strip()) * 1e-6

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

        # Write to YAML file
        with open(self.file_name, "w") as f:
            yaml.dump(self.Params, f)

    def cb_load(self):
        print("Load")
        try: # Read from YAML file
            with open(self.file_name, "r") as f:
                self.Params = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"File not found: {self.file_name}")
            raise

        # Set the default values to the GUI objects
        for key, value in self.Params.items():
            if key in self.h_gui:
                self.h_gui[key].set_val(value, is_callback=True)

        # Additional configuration parameters through non h_gui mapped widget methods
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

        # EX4: if the button is checked, create an ARB object and configure it (slide 3-37 example 203)
            # EX4: use try and except to catch any exceptions
                # EX4: Get the MXG IP from the h_gui using get_val() method (slide 3-47 example 210)

                # EX4: Create an ARB object using the VSG class from the arb module (slide 3-52 example 219)

                # EX4: Get the maximal ARB Fs from the self.Params dictionary

                # EX4: Configure the ARB object using the configure method (slide 3-52 example 219)

                # EX4: Clear Errors CLS

                # EX4: Set the Auto Level Control to Off (ALC) (slide 3-52 example 219)
                # Note - It is critical not to use boolean types for this arb function !!! (e.g. write 0 and not False, 1 and not True)

                # EX4: CALL the update function cb_multitone_update (the same used for the callback, to be implemented next)

                # Set GUI MOD to On
        self.h_gui['Mod_On_Off'].set_val(True, is_callback=False) # The callback is false in order to avoid sending the command to the sig_gen again
        self.h_gui['RF_On_Off' ].set_val(True, is_callback=False) # This was carried out in the cb_multitone_update function

            # EX4: handle the exception
            # except Exception as e:

                # EX4: Print the exception`

                # EX4: Switch MOD to Off and RF to Off using the set_val method of the h_gui dictionary
                # NOTE - the is_callback should be set to True, because we want the action, not just the GUI update

                # EX4: set the arb_gen to None

                # EX4: Clear Button state use the sender method to get the button object and set it to False
                # ---> self.sender().setChecked(False)
        # EX4: uncomment the else block
        # else:
        #     print("MultiTone Off")
        #     if self.arb_gen is not None:
        #         self.arb_gen.stop()
        #         self.arb_gen = None
        #     self.h_gui['Mod_On_Off'].set_val(False, is_callback=False)

        # Now would be a good time to review this entire function and make sure you understand it!

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
        pass
        # EX4: print the input BW and Ntones from the h_gui dictionary

        # EX4: if the arb_gen is not None
            # EX4: calculate the new signal by calling the multitone function (slide 3-51)
            # EX4: Get the bandwidth and Ntones from the h_gui dictionary
            # EX4: get the ARB Fs from the Params dictionary
            # EX4: change the default Nfft to 2048
            # EX4: download it to the ARB generator (using download_wfm) and play it (slide 3-52 example 219)


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
