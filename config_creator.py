import configparser

config_path = "/Users/pierrebouvet/Documents/Code/Ghost_treat/config.ini"

def read_config():
    # Create a ConfigParser object
    config = configparser.ConfigParser()

    # Read the configuration file
    config.read('config.ini')

    # Access values from the configuration file
    debug_mode = config.getboolean('General', 'debug')
    log_level = config.get('General', 'log_level')
    db_name = config.get('Database', 'db_name')
    db_host = config.get('Database', 'db_host')
    db_port = config.get('Database', 'db_port')

    # Return a dictionary with the retrieved values
    config_values = {
        'debug_mode': debug_mode,
        'log_level': log_level,
        'db_name': db_name,
        'db_host': db_host,
        'db_port': db_port
    }

    return config_values

def create_config():
    config = configparser.ConfigParser()

    # Define File Formats acceptable for spectra information
    file_format = [["ghost", "*.DAT"],
                    ["numpy", "*.npy"]]
    
    # Define columns in database
    db_colums = [["id","INTEGER PRIMARY KEY AUTOINCREMENT"],
                 ["name","TEXT"],
                 ["filepath","TEXT"],
                 ["date","TEXT"],
                 ["sample","TEXT"],
                 ["brillouin_signal_type","TEXT"],
                 ["scanning_strategy","TEXT"],
                 ["spectrometer_type","TEXT"],
                 ["acquisition_time","TEXT"],
                 ["laser_wavelength","TEXT"],
                 ["laser_model","TEXT"],
                 ["laser_power","TEXT"],
                 ["lens_NA","TEXT"],
                 ["scattering_angle","TEXT"],
                 ["immersion_medium","TEXT"],
                 ["objective_model","TEXT"],
                 ["temperature","TEXT"],
                 ["temperature_uncertainty","TEXT"],
                 ["data_shape","TEXT"],
                 ["spatial_resolution","TEXT"],
                 ["abscissa_type","TEXT"],
                 ["info","TEXT"],
                 ["spectro_caracterization","TEXT"],
                 ["tfp_range","TXT"]
                 ]

    display_column = [["name","name"],
                      ["date","date"],
                      ["sample","sample"]]
    
    # Add properties to the configuration
    config['File Format'] = {}
    for e in file_format: config['File Format'][e[0]] = e[1]
    config['Database Columns'] = {}
    for e in db_colums: config['Database Columns'][e[0]] = e[1]
    config['Columns at opening'] = {}
    for e in display_column: config['Columns at opening'][e[0]] = e[1]

    # Write the configuration to a file
    with open(config_path, 'w') as configfile:
        config.write(configfile)


if __name__ == "__main__":
    # Call the function to read the configuration file
    config_data = create_config()
