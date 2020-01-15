
# USRP_Client (pyUC)

## Introduction
The pyUC python application is a GUI front end for accessing ham radio digital networks from your PC.  It is the front end app for the DVSwitch suite of software and connects to the Analog_Bridge component.
## Features
The user can:

 - Select digital network
 - Select "talk group" or reflector from a list
 - Transmit and receive to the network using their speakers and mic
 - Record a list of stations received in the session
 - See pictures of the hams from QRZ.com

## Installation
Download and unzip https://github.com/DVSwitch/USRP_Client/archive/master.zip

Install instructions by platform:

- Windows 10

    Use Python 3.7 from the Microsoft Store
    Open a command prompt
    **python -m pip install --upgrade pip**  
    Download PyAudio from https://www.lfd.uci.edu/~gohlke/pythonlibs/ for your version (32 or 64 bit)
 
    **pip install PyAudio-0.2.11-cp37-cp37m-win_XXX.whl   
    pip install bs4  
    pip install Pillow  
    pip install requests**  
    Edit pyUC.ini
 
- Linux (Tested on a Raspberry Pi running Buster and Linux Mint 19)

    Open a command prompt  
    **sudo apt-get install python3-pyaudio  
    sudo apt-get install portaudio19-dev  
    sudo apt-get install python3-pil.imagetk**  
    Edit pyUC.ini

- Mac

    **ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"  
    brew install python  
    brew install portaudio  
    pip3 install pyaudio  
    pip3 install bs4 Pillow requests**  
    Edit pyUC.ini

## Contributing
We encourage others of submit pull request tp this repository.  We only ask that you submit the pull request on the development branch.  Your pull will be reviewed and merged into the master branch.
## Related projects
DVSwitch
## Licensing
xxxxx
