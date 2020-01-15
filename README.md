# USRP_Client (pyUC)

Download and unzip https://github.com/DVSwitch/USRP_Client/archive/master.zip

Install instructions by platform:

- Windows 10

    Use Python 3.7 from the Microsoft Store
 
    Open a command prompt
 
    python -m pip install --upgrade pip
 
    Download PyAudio from https://www.lfd.uci.edu/~gohlke/pythonlibs/ for your version (32 or 64 bit)
 
    pip install PyAudio-0.2.11-cp37-cp37m-win_XXX.whl
 
    pip install bs4
 
    pip install Pillow
 
    pip install requests
 
    Edit pyUC.ini
 
- Linux (Tested on a Raspberry Pi running Buster)

    Open a command prompt

    sudo apt-get install python3-pyaudio

    sudo apt-get install portaudio19-dev

    sudo apt-get install python3-pil.imagetk

    Edit pyUC.ini

- Mac

    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

    brew install python

    brew install portaudio

    pip3 install pyaudio

    pip3 install bs4 Pillow requests

    Edit pyUC.ini