
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
    ## Method 1
    Use Python 3.7 from the Microsoft Store  
    Open a command prompt  
    **python -m pip install --upgrade pip**  
    Download PyAudio from https://www.lfd.uci.edu/~gohlke/pythonlibs/ for your version (32 or 64 bit)
 
    **pip install PyAudio-0.2.11-cp37-cp37m-win_XXX.whl   
    pip install bs4  
    pip install Pillow  
    pip install requests**  
    Edit pyUC.ini
    
     ## Method 2
    Using Download.bat file to download and install all required libs for USRP Client use. Tested on Windows 10 64
    
    
    If you get an error about MSVCP140.DLL, then you will need to install the MSVC C++ runtime library.  
    Get it from: https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads 
   
 
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
We encourage others to submit pull request to this repository.  We only ask that you submit the pull request on the development branch.  Your pull will be reviewed and merged into the master branch.
## Related projects
DVSwitch
## Licensing
This software is for use on amateur radio networks only, it is to be used  
for educational purposes only. Its use on commercial networks is strictly   
prohibited.  Permission to use, copy, modify, and/or distribute this software   
hereby granted, provided that the above copyright notice and this permission   
notice appear in all copies.  

THE SOFTWARE IS PROVIDED "AS IS" AND DVSWITCH DISCLAIMS ALL WARRANTIES WITH  
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY  
AND FITNESS.  IN NO EVENT SHALL N4IRR BE LIABLE FOR ANY SPECIAL, DIRECT,  
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM  
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE  
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR  
PERFORMANCE OF THIS SOFTWARE.  
