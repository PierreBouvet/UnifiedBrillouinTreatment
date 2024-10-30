# Unified Brillouin Treatment User Interface

## Introduction to the project

This project aims at proposing a standard interface to store and treat Brillouin Scattered spectra, particularly to be used by the BioBrillouin community. As such this User Interface has the following goals:
- Allow an easy conversion of spectra to a standardized BH5 format
- Regroup a series of spectra obtained during an experiment in a single database
- Standardize the treatment of Brillouin spectra with optimized algorithms
- Allow basic statistical analysis on the treated data

## Setting up

To test the User Interface, you should open the main.py file and run it.

## Use

### BH5 attributes

All the attributes that will be stored on the BH5 are listed in the "standard_parameters_v0.1.csv" file. This list of parameters is flexible: you can add your own parameters directly in the CSV file. To fill the value of a parameter, you can either create a custom CSV file and fill-in all the parameters or you can open the user interface and modify the parameters directly from the interface.

### Current limitations

The User Interface currently only supports the following files
- 0D (point measure) spectra obtained with the GHOST software

## Future developments

### Adding file formats

To adapt this project to your needs, we encourage you either to develop the conversion from your individual raw data to BH5 file formats and push the code (fastest) or to send us an example of raw spectrum you wish to add to the database (slowest because we'll have to code it ourselves).

### Treatment capabilities

The goal of this interface is to allow users to treat their spectra with the same algorithms. This idea is currently in development but we would be happy to have your participation on this matter.
