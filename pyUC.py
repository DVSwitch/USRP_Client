#!/usr/bin/python3
###################################################################################
# pyUC ("puck")
# Copyright (C) 2014, 2015, 2016, 2019, 2020 N4IRR
#
# This software is for use on amateur radio networks only, it is to be used
# for educational purposes only. Its use on commercial networks is strictly 
# prohibited.  Permission to use, copy, modify, and/or distribute this software 
# hereby granted, provided that the above copyright notice and this permission 
# notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND DVSWITCH DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS.  IN NO EVENT SHALL N4IRR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
# OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
###################################################################################

from tkinter import *
from tkinter import ttk
from time import time, sleep, localtime, strftime
from random import randint
from tkinter import messagebox
import socket
import struct
import _thread
import shlex
import configparser, traceback
import pyaudio
import audioop
import json
import logging
import webbrowser
import os
import io
import base64
import urllib.request
import queue
from pathlib import Path
import hashlib
from tkinter import font

UC_VERSION = "1.2.2"

###################################################################################
# Declare input and output ports for communication with AB
###################################################################################
usrp_tx_port = 12345
usrp_rx_port = 12345

###################################################################################
# USRP packet types
###################################################################################
USRP_TYPE_VOICE = 0
USRP_TYPE_DTMF = 1
USRP_TYPE_TEXT = 2
USRP_TYPE_PING = 3
USRP_TYPE_TLV = 4
USRP_TYPE_VOICE_ADPCM = 5
USRP_TYPE_VOICE_ULAW = 6

###################################################################################
# TLV tags
###################################################################################
TLV_TAG_BEGIN_TX    = 0
TLV_TAG_AMBE        = 1
TLV_TAG_END_TX      = 2
TLV_TAG_TG_TUNE     = 3
TLV_TAG_PLAY_AMBE   = 4
TLV_TAG_REMOTE_CMD  = 5
TLV_TAG_AMBE_49     = 6
TLV_TAG_AMBE_72     = 7
TLV_TAG_SET_INFO    = 8
TLV_TAG_IMBE        = 9
TLV_TAG_DSAMBE      = 10
TLV_TAG_FILE_XFER   = 11

###################################################################################
# Globals (gah)
###################################################################################
noTrace = False                     # Boolean to control recursion when a new mode is selected
usrpSeq = 0                         # Each USRP packet has a unique sequence number
udp = None                          # UDP socket for USRP traffic
out_index = None                    # Current output (speaker) index in the pyaudio device list
in_index = None                     # Current input (mic) index in the pyaudio device list
regState = False                    # Global registration state boolean
noQuote = {ord('"'): ''}
empty_photo = ("photo", "", "", "") # instance of a blank photo
SAMPLE_RATE = 48000                 # Default audio sample rate for pyaudio (will be resampled to 8K)
toast_frame = None                  # A toplevel window used to display toast messages
ipc_queue = None                    # Queue used to pass info to main hread (UI)
ptt = False                         # Current ptt state
tx_start_time = 0                   # TX timer
done = False                        # Thread stop flag
transmit_enable = True              # Make sure that UC is half duplex
useQRZ = True
level_every_sample = 1
NAT_ping_timer = 0

listbox = None                      # tk object (talkgroup)
transmitButton = None               # tk object
logList = None                      # tk object
macros = {}

uc_background_color = "gray25"
uc_text_color = "white"

###################################################################################
# Strings
###################################################################################
STRING_USRP_CLIENT = "USRP Client"
STRING_FATAL_ERROR = "fatal error, python package not found: "
STRING_TALKGROUP = "Talk Group"
STRING_OK = "OK"
STRING_REGISTERED =  "Registered"
STRING_WINDOWS_PORT_REUSE = "On Windows, ignore the port reuse"
STRING_FATAL_OUTPUT_STREAM = "fatal error, can not open output audio stream"
STRING_OUTPUT_STREAM_ERROR = "Output stream  open error"
STRING_FATAL_INPUT_STREAM = "fatal error, can not open input audio stream"
STRING_INPUT_STREAM_ERROR = "Input stream  open error"
STRING_CONNECTION_FAILURE = "Connection failure"
STRING_SOCKET_FAILURE = "Socket failure"
STRING_CONNECTED_TO = "Connected to"
STRING_DISCONNECTED = "Disconnected "
STRING_SERVER = "Server"
STRING_READ = "Read"
STRING_WRITE = "Write"
STRING_AUDIO = "Audio"
STRING_MIC = "Mic"
STRING_SPEAKER = "Speaker"
STRING_INPUT = "Input"
STRING_OUTPUT = "Output"
STRING_TALKGROUPS = "Talk Groups"
STRING_TG = "TG"
STRING_TS = "TS"
STRING_CONNECT = "Connect"
STRING_DISCONNECT = "Disconnect"
STRING_DATE = "Date"
STRING_TIME = "Time"
STRING_CALL = "Call"
STRING_SLOT = "Slot"
STRING_LOSS = "Loss"
STRING_DURATION = "Duration"
STRING_MODE = "MODE"
STRING_REPEATER_ID = "Repeater ID"
STRING_SUBSCRIBER_ID = "Subscriber ID"
STRING_TAB_MAIN = "Main"
STRING_TAB_SETTINGS = "Settings"
STRING_TAB_ABOUT = "About"
STRING_CONFIG_NOT_EDITED = 'Please edit the configuration file and set it up correctly. Exiting...'
STRING_CONFIG_FILE_ERROR = "Config (ini) file error: "
STRING_EXITING = "Exiting pyUC..."
STRING_VOX = "Vox"
STRING_DONGLE_MODE = "Dongle Mode"
STRING_VOX_ENABLE = "Vox Enable"
STRING_VOX_THRESHOLD = "Threshold"
STRING_VOX_DELAY = "Delay"
STRING_NETWORK = "Network"
STRING_LOOPBACK = "Loopback"
STRING_IP_ADDRESS = "IP Address"
STRING_PRIVATE = "Private"
STRING_GROUP = "Group"
STRING_TRANSMIT = "Transmit"

###################################################################################
# HTML/QRZ import libraries
try:
    from urllib.request import urlopen
    from bs4 import BeautifulSoup
    from PIL import Image, ImageTk
    import requests
except:
    print(STRING_FATAL_ERROR + str(sys.exc_info()[1]))
    exit(1)

qrz_label = None
qrz_cache = {}      # we use this cache to 1) speed execution 2) limit the lookup count on qrz.com. 3) cache the thumbnails we do find
html_queue = None   # IPC queue to pass in lookup requests.  Each request is a callsign to lookup.  Successful lookups place the result in the ipc_queue

# Place the HTML lookup and image ownload on a different thread so as to not block the UI
def html_thread():
    global html_queue
    html_queue = queue.Queue()              # Create the queue
    while done == False:
        try:
            callsign, name = html_queue.get(0)        # wait forever for a message to be placed in the queue (a callsign)
            photo = getQRZImage( callsign ) if useQRZ else ""    # lookup the call and return an image     
            ipc_queue.put(("photo", callsign, photo, name))
        except queue.Empty:
            pass
        sleep(0.1)

# Return the URL of an image associated with the callsign.  The URL may be cached or scraped from QRZ    
def getImgUrl( callsign ):
    img = ""
    if callsign in qrz_cache:
        return qrz_cache[callsign]['url']

    try:
        # specify the url
        quote_page = 'https://qrz.com/lookup/' + callsign

        # query the website and return the html to the variable ‘page’
        page = urlopen(quote_page, timeout=20).read()

        # parse the html using beautiful soup and store in variable `soup`
        soup = BeautifulSoup(page, 'html.parser')
        img = soup.find(id='mypic')['src']
    except:
        pass
    qrz_cache[callsign] = {'url' : img}
    return img

# Given a URL, download the image from the web and return it.
def getQRZImage( callsign ):
    photo = ""              # If not found, this will be returned (causes the image to blank out)
    if len(callsign) > 0:
        image_url = getImgUrl(callsign)
        if len(image_url) > 0:
            if 'image' in qrz_cache[callsign]:
                return qrz_cache[callsign]['image']
            resp = requests.get(image_url, stream=True).raw
            try:
                image = Image.open(resp)
                image.thumbnail((170,110), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
            except:
                pass
            qrz_cache[callsign]['image'] = photo
    return photo

# Run on the main thread, show the image in the passed UI element (label)
def showQRZImage( msg, in_label ):
    photo = msg[2]
    in_label.configure(image=photo)
    in_label.image = photo
    in_label.callsign = msg[1]
    current_call.set(msg[1])
    current_name.set(msg[3])

###################################################################################
def ping_thread():
    while done == False:
        sleep(20.0)
        sendUSRPCommand(bytes("PING", 'ASCII'), USRP_TYPE_PING)

###################################################################################
# Log output to console
###################################################################################
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

###################################################################################
# Manage a popup dialog for on the fly TGs
###################################################################################
class MyDialog:
    
    def __init__(self, parent):

        win_offset = "250x100+{}+{}".format(root.winfo_x()+40, root.winfo_y()+65)

        top = self.top = Toplevel(parent)
        self.top.transient(parent)
        self.top.grab_set()

        top.geometry(win_offset)
        top.configure(bg=uc_background_color)

        Label(top, text=STRING_TALKGROUP, fg=uc_text_color, bg=uc_background_color).pack()
        
        if len(macros) == 0:
            self.e = Entry(top, fg=uc_text_color, bg=uc_background_color)
        else:
            self.e = ttk.Combobox(top, values=list(macros.values()))

        self.e.bind("<Return>", self.ok)
        self.e.bind("<Escape>", self.cancel)

        self.e.pack(padx=5)
        
        b = ttk.Button(top, text=STRING_OK, command=self.ok)
        b.pack(pady=5)
        self.e.focus_set()

    def popdown(self, popdown_state):
        if ((popdown_state != None) and (popdown_state == True)):
            self.e.event_generate('<Button-1>')

    def cancel(self, event=None):
        self.top.destroy()

    def ok(self, event=None):
        
        item = self.e.get()
        if len(item):
            logging.info( "value is %s", item )
            mode = master.get()
            tg_name = tg = item
            lst = item.split(',')
            if len(lst) == 1:
                if item in macros.values():
                    i = list(macros.values()).index(item)
                    tg = list(macros.keys())[i]
            else:
                tg_name = lst[0]
                tg = lst[1]
            connect((tg, tg_name))
            if tg.startswith('*') == False:
                i = None
                for x in talk_groups[mode]:
                    if x[1] == tg:
                        i = x
                if i == None: # tg not found?
                    talk_groups[mode].append((tg_name, tg))
                    fillTalkgroupList(master.get())
                selectTGByValue(tg)
                listbox.see(listbox.curselection())
        self.top.destroy()

###################################################################################
# Open the UDP socket for TX and RX
###################################################################################
def openStream():
    global usrpSeq
    global udp

    usrpSeq = 0
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except:
        logging.info(STRING_WINDOWS_PORT_REUSE)
        pass
    if (usrp_rx_port in usrp_tx_port) == False:    # single  port reply does not need a bind
        udp.bind(('', usrp_rx_port))

def sendto(usrp):
    for port in usrp_tx_port:
        udp.sendto(usrp, (ip_address.get(), port))

from ctypes import *
from contextlib import contextmanager

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    try:
        asound = cdll.LoadLibrary('libasound.so')
        asound.snd_lib_error_set_handler(c_error_handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except:
        yield
        pass

###################################################################################
# Log the EOT
###################################################################################
def log_end_of_transmission(call,rxslot,tg,loss,start_time):
    logging.info('End TX:   {} {} {} {} {:.2f}s'.format(call, rxslot, tg, loss, time() - start_time))
    logList.see(logList.insert('', 'end', None, values=(
        strftime(" %m/%d/%y", localtime(start_time)),
        strftime("%H:%M:%S", localtime(start_time)),
        call.ljust(10), rxslot, tg, loss, '{:.2f}s'.format(time() - start_time))))
    root.after(1000, logList.yview_moveto, 1)
    current_tx_value.set(my_call)
    html_queue.put(("", ""))  # clear the photo, use queue for short transmissions

###################################################################################
# RX thread, collect audio and metadata from AB
###################################################################################
def rxAudioStream():
    global ip_address
    global noTrace
    global regState
    global transmit_enable
    global macros

    logging.info('Start rx audio thread')
    USRP = bytes("USRP", 'ASCII')
    REG = bytes("REG:", 'ASCII')
    UNREG = bytes("UNREG", 'ASCII')
    OK = bytes("OK", 'ASCII')
    INFO = bytes("INFO:", 'ASCII')
    EXITING = bytes("EXITING", 'ASCII')

    FORMAT = pyaudio.paInt16
    CHUNK = 160 if SAMPLE_RATE == 8000 else (160*6)     # Size of chunk to read
    CHANNELS = 1
    RATE = SAMPLE_RATE
    
    try:
        stream = p.open(format=FORMAT,
                        channels = CHANNELS,
                        rate = RATE,
                        output = True,
                        frames_per_buffer = CHUNK,
                        output_device_index=out_index
                        )
    except:
        logging.critical(STRING_FATAL_OUTPUT_STREAM + str(sys.exc_info()[1]))
        messagebox.showinfo(STRING_USRP_CLIENT, STRING_OUTPUT_STREAM_ERROR)
        os._exit(1)

    _i = p.get_default_output_device_info().get('index') if out_index == None else out_index
    logging.info("Output Device: {} Index: {}".format(p.get_device_info_by_host_api_device_index(0, _i).get('name'), _i))

    lastKey = -1
    start_time = time()
    call = ''
    name = ''
    tg = ''
    lastSeq = 0
    seq = 0
    loss = '0.00%'
    rxslot = '0'
    state = None
    
    while done == False:
        soundData, addr = udp.recvfrom(1024)
        if addr[0] != ip_address.get():
            ip_address.set(addr[0]) # OK, this was supposed to help set the ip to a server, but multiple servers ping/pong.  I may remove it.
        if (soundData[0:4] == USRP):
            eye = soundData[0:4]
            seq, = struct.unpack(">i", soundData[4:8])
            memory, = struct.unpack(">i", soundData[8:12])
            keyup, = struct.unpack(">i", soundData[12:16])
            talkgroup, = struct.unpack(">i", soundData[16:20])
            type, = struct.unpack("i", soundData[20:24])
            mpxid, = struct.unpack(">i", soundData[24:28])
            reserved, = struct.unpack(">i", soundData[28:32])
            audio = soundData[32:]
            if (type == USRP_TYPE_VOICE): # voice
                audio = soundData[32:]
                #print(eye, seq, memory, keyup, talkgroup, type, mpxid, reserved, audio, len(audio), len(soundData))
                if (len(audio) == 320):
                    if RATE == 48000:
                        (audio48, state) = audioop.ratecv(audio, 2, 1, 8000, 48000, state)
                        stream.write(bytes(audio48), CHUNK)
                        if (seq % level_every_sample) == 0:
                            rms = audioop.rms(audio, 2)     # Get a relative power value for the sample
                            audio_level.set(int(rms/100))
                    else:
                        stream.write(audio, CHUNK)
                if (keyup != lastKey):
                    logging.debug('key' if keyup else 'unkey')
                    if keyup:
                        start_time = time()
                    if keyup == False:
                        log_end_of_transmission(call, rxslot, tg, loss, start_time)
                        transmit_enable = True  # Idle state, allow local transmit
                        audio_level.set(0)
                lastKey = keyup
            elif (type == USRP_TYPE_TEXT): #metadata
                if (audio[0:4] == REG):
                    if (audio[4:6] == OK):
                        connected_msg.set(STRING_REGISTERED)
                        requestInfo()
                        if in_index == -1:
                            transmitButton.configure(state='disabled')
                        else:
                            transmitButton.configure(state='normal')
                        regState = True
                    elif (audio[4:9] == UNREG):
                        disconnect()
                        transmitButton.configure(state='disabled')
                        regState = False
                        pass
                    elif (audio[4:11] == EXITING):
                        disconnect()
                        tmp = audio[:audio.find(b'\x00')].decode('ASCII') # C string
                        args = tmp.split(" ")
                        sleepTime = int(args[2])
                        logging.info("AB is exiting and wants a re-reg in %s seconds...", sleepTime)
                        if (sleepTime > 0):
                            sleep(sleepTime)
                            registerWithAB()
                    logging.info(audio[:audio.find(b'\x00')].decode('ASCII'))
                elif (audio[0:5] == INFO):
                    _json = audio[5:audio.find(b'\x00')].decode('ASCII')
                    if (_json[0:4] == "MSG:"):
                        logging.info("Text Message: " + _json[4:])
                        ipc_queue.put(("toast", "Text Message", _json[4:]))
                    elif (_json[0:6] == "MACRO:"):  # An ad-hoc macro menu
                        logging.info("Macro: " + _json[6:])
                        macs = _json[6:]
                        macrosx = dict(x.split(",") for x in macs.split("|"))
                        macros = { k:v.strip() for k, v in macrosx.items()}
                        ipc_queue.put(("macro", ""))    # popup the menu
                    elif (_json[0:5] == "MENU:"):  # An ad-hoc macro menu
                        logging.info("Menu: " + _json[5:])
                        macs = _json[5:]
                        macrosx = dict(x.split(",") for x in macs.split("|"))
                        macros = { k:v.strip() for k, v in macrosx.items()}
                    else:
                        obj=json.loads(audio[5:audio.find(b'\x00')].decode('ASCII'))
                        noTrace = True  # ignore the event generated by setting the combo box
                        if (obj["tlv"]["ambe_mode"][:3] == "YSF"):
                            master.set("YSF")
                        else:
                            master.set(obj["tlv"]["ambe_mode"])
                        noTrace = False
                        logging.info(audio[:audio.find(b'\x00')].decode('ASCII'))
                        connected_msg.set( STRING_CONNECTED_TO + " " + obj["last_tune"] )
                        selectTGByValue(obj["last_tune"])
                else:
                    # Tunnel a TLV inside of a USRP packet
                    if audio[0] == TLV_TAG_SET_INFO:
                        if transmit_enable == False:    #EOT missed?
                            log_end_of_transmission(call, rxslot, tg, loss, start_time)
                        rid = (audio[2] << 16) + (audio[3] << 8) + audio[4] # Source
                        tg = (audio[9] << 16) + (audio[10] << 8) + audio[11] # Dest
                        rxslot = audio[12]
                        rxcc = audio[13]
                        mode = STRING_PRIVATE if (rxcc  & 0x80) else STRING_GROUP
                        name = ""
                        if audio[14] == 0: # C string termintor for call
                            call = str(rid)
                        else:
                            call = audio[14:audio.find(b'\x00', 14)].decode('ASCII')
                            if call[0] == '{':    # its a json dict
                                obj=json.loads(call)
                                call = obj['call']
                                name = obj['name'].split(' ')[0] if 'name' in obj else ""
                        listName = master.get()
                        if (listName == 'DSTAR') or (listName == "YSF"): # for these modes the TG is not valid
                            tg = getCurrentTGName()
                        elif tg == subscriber_id.get(): # is the dest TG my dmr ID? (private call)
                            tg = my_call
                        for item in talk_groups[listName]:
                            if item[1] == str(tg):
                                tg = item[0]    # Found the TG number in the list, so we can use its friendly name
                        current_tx_value.set('{} -> {}'.format(call, tg))
                        logging.info('Begin TX: {} {} {} {}'.format(call, rxslot, tg, mode))
                        transmit_enable = False # Transmission from network will disable local transmit
                        if call.isdigit() == False:
                            html_queue.put((call, name))
                        if ((rxcc  & 0x80) and (rid > 10000)): # > 10000 to exclude "4000" from BM
#                            logging.info('rid {} ctg {}'.format(rid, getCurrentTG()))
                            # a dial string with a pound is a private call, see if the current TG matches
                            privateTG = str(rid) + '#'
                            if (privateTG != getCurrentTG()):
                                #Tune to tg
                                sendRemoteControlCommandASCII("txTg=" + privateTG)
                                talk_groups[listName].append((call + " Private", privateTG))
                                fillTalkgroupList(listName)
                                tg = privateTG # Make log entries say the right thing
                            selectTGByValue(privateTG)
            elif (type == USRP_TYPE_PING):
                if transmit_enable == False:    # Do we think we receiving packets?, lets test for EOT missed
                    if (lastSeq+1) == seq:
                        logging.info("missed EOT")
                        log_end_of_transmission(call, rxslot, tg, loss, start_time)
                        transmit_enable = True  # Idle state, allow local transmit
                    lastSeq = seq
#                logging.debug(audio[:audio.find('\x00')])
                pass
            elif (type == USRP_TYPE_TLV):
                tag = audio[0]
                length = audio[1]
                value = audio[2:]    
                if tag == TLV_TAG_FILE_XFER:
                    FILE_SUBCOMMAND_NAME = 0
                    FILE_SUBCOMMAND_PAYLOAD = 1
                    FILE_SUBCOMMAND_WRITE = 2
                    FILE_SUBCOMMAND_READ = 3
                    FILE_SUBCOMMAND_ERROR = 4
                    if value[0] == FILE_SUBCOMMAND_NAME:
                        file_len = (value[1] << 24) + (value[2] << 16) + (value[3] << 8) + value[4]
                        file_name = value[5:]
                        zero = file_name.find(0)
                        file_name = file_name[:zero].decode('ASCII')
                        logging.info("File transfer name: " + file_name)
                        m = hashlib.md5()
                    if value[0] == FILE_SUBCOMMAND_PAYLOAD:
                        logging.debug("payload len = " + str(length-1))
                        payload = value[1:length]
                        m.update(payload)
                        #logging.debug(payload.hex())
                        #logging.debug(payload)
                    if value[0] == FILE_SUBCOMMAND_WRITE:
                        digest = m.digest().hex().upper()
                        file_md5 = value[1:33].decode('ASCII')
                        if (digest == file_md5):
                            logging.info("File digest matches")
                        else:
                            logging.info("File digest does not match {} vs {}".format(digest, file_md5))
                        #logging.info("write (md5): " + value[1:33].hex())
                    if value[0] == FILE_SUBCOMMAND_ERROR:
                        logging.info("error")
        else:
#            logging.info(soundData, len(soundData))
            pass

#    udp.close()

###################################################################################
# TX thread, send audio to AB
###################################################################################
def txAudioStream():
    global usrpSeq
    global ptt
    global transmit_enable
    FORMAT = pyaudio.paInt16                            # 16 bit signed ints
    CHUNK = 160 if SAMPLE_RATE == 8000 else (160*6)     # Size of chunk to read
    CHANNELS = 1                                        # mono
    RATE = SAMPLE_RATE
    state = None                                        # resample state between fragments
    
    try:
        stream = p.open(format=FORMAT,
                        channels = CHANNELS,
                        rate = RATE,
                        input = True,
                        frames_per_buffer = CHUNK,
                        input_device_index=in_index
                        )
    except:
        logging.critical(STRING_FATAL_INPUT_STREAM + str(sys.exc_info()[1]))
        transmit_enable = False
        ipc_queue.put(("dialog", "Text Message", STRING_INPUT_STREAM_ERROR))
        return

    _i = p.get_default_output_device_info().get('index') if in_index == None else in_index
    logging.info("Input Device: {} Index: {}".format(p.get_device_info_by_host_api_device_index(0, _i).get('name'), _i))

    lastPtt = ptt
    while done == False:
        try:

            if RATE == 48000:       # If we are reading at 48K we need to resample to 8K
                audio48 = stream.read(CHUNK, exception_on_overflow=False)
                (audio, state) = audioop.ratecv(audio48, 2, 1, 48000, 8000, state)
            else:
                audio = stream.read(CHUNK, exception_on_overflow=False)

            rms = audioop.rms(audio, 2)     # Get a relative power value for the sample
            ###### Vox processing #####
            if vox_enable.get():
                if rms > vox_threshold.get():   # is it loud enough?
                    decay = vox_delay.get()     # Yes, reset the decay value (wont unkey for N samples)
                    if (ptt == False) and (transmit_enable == True):            # Are we changing ptt state to True?
                        ptt = True              # Set it
                        showPTTState(0)         # Update the UI (turn transmit button red, etc)
                elif ptt == True:               # Are we too soft and transmitting?
                    decay -= 1                  # Decrement the decay counter
                    if decay <= 0:              # Have we passed N samples, all of them less then the threshold?
                        ptt = False             # Unkey
                        showPTTState(1)         # Update the UI
            ###########################

            if ptt != lastPtt:
                usrp = 'USRP'.encode('ASCII') + struct.pack('>iiiiiii',usrpSeq, 0, ptt, 0, USRP_TYPE_VOICE, 0, 0) + audio
                sendto(usrp)
                usrpSeq = usrpSeq + 1
            lastPtt = ptt
            if ptt:
                usrp = 'USRP'.encode('ASCII') + struct.pack('>iiiiiii',usrpSeq, 0, ptt, 0, USRP_TYPE_VOICE, 0, 0) + audio
                sendto(usrp)
                usrpSeq = usrpSeq + 1
                audio_level.set(int(rms/100))
        except:
            logging.warning("TX thread:" + str(sys.exc_info()[1]))

def debugAudio():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    print("------------------------------------")
    print("Info: ", info)
    print("------------------------------------")
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            print("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get('name'))
        print("Device: ", p.get_device_info_by_host_api_device_index(0, i))
        print("===============================")
    print("Output: ", p.get_default_output_device_info())
    print("Input: ", p.get_default_input_device_info())

def listAudioDevices(want_input):
    devices = []
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        is_input = p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels') > 0
        if (is_input and want_input) or (want_input == False and is_input == False):
            devices.append(p.get_device_info_by_host_api_device_index(0, i).get('name'))
            logging.info("Device id {} - {}".format(i, p.get_device_info_by_host_api_device_index(0, i).get('name')))
    return devices

#debugAudio()
#exit(1)

###################################################################################
# Catch and display any socket errors
###################################################################################
def socketFailure():
    connected_msg.set( STRING_CONNECTION_FAILURE )
    logging.error(STRING_SOCKET_FAILURE)

###################################################################################
# Send command to AB
###################################################################################
def sendUSRPCommand( cmd, packetType ):
    global usrpSeq
    logging.info("sendUSRPCommand: "+ str(cmd))
    try:
        # Send "text" packet to AB. 
        usrp = 'USRP'.encode('ASCII') + (struct.pack('>iiiiiii',usrpSeq, 0, 0, 0, packetType << 24, 0, 0)) + cmd
        usrpSeq = (usrpSeq + 1) & 0xffff
        sendto(usrp)
    except:
        traceback.print_exc()
        socketFailure()

###################################################################################
# Send command to AB
###################################################################################
def sendRemoteControlCommand( cmd ):
    logging.info("sendRemoteControlCommand: "+ str(cmd))
    # Use TLV to send command (wrapped in a USRP packet). 
    tlv = struct.pack("BB", TLV_TAG_REMOTE_CMD, len(cmd))[0:2] + cmd
    sendUSRPCommand(tlv, USRP_TYPE_TLV)

def sendRemoteControlCommandASCII( cmd ):
    sendRemoteControlCommand(bytes(cmd, 'ASCII'))
###################################################################################
# Send command to DMRGateway
###################################################################################
def sendToGateway( cmd ):
    logging.info("sendToGateway: " + cmd)

###################################################################################
# Begin the registration sequence
###################################################################################
def registerWithAB():
    sendUSRPCommand(bytes("REG:DVSWITCH", 'ASCII'), USRP_TYPE_TEXT)

###################################################################################
# Unregister from server
###################################################################################
def unregisterWithAB():
    sendUSRPCommand(bytes("REG:UNREG", 'ASCII'), USRP_TYPE_TEXT)

###################################################################################
# Request the INFO json from AB
###################################################################################
def requestInfo():
    sendUSRPCommand(bytes("INFO:", 'ASCII'), USRP_TYPE_TEXT)

###################################################################################
# 
###################################################################################
def sendMetadata():
    metadata = ""
    sendRemoteControlCommandASCII(metadata)

###################################################################################
# Set the size (number of bits) of each AMBE sample
###################################################################################
def setAMBESize(size):
    sendRemoteControlCommandASCII("ambeSize="+size)

###################################################################################
# Set the AMBE mode to DMR|DSTAR|YSF|NXDN|P25
###################################################################################
def setAMBEMode(mode):
    sendRemoteControlCommandASCII("ambeMode="+mode)

###################################################################################
# 
###################################################################################
def getInfo():
    logging.info("getInfo")

###################################################################################
# xx_Bridge command: section
###################################################################################
def setRemoteNetwork( netName ):
    logging.info("setRemoteNetwork")

###################################################################################
# Set the AB mode by running the named macro
###################################################################################
def setMode( mode ):
    sendUSRPCommand(bytes("*" + mode, 'ASCII'), USRP_TYPE_DTMF)

###################################################################################
# Tell AB to select the passed tg
###################################################################################
def setRemoteTG( tg ):
    
    items = map(int, listbox.curselection())
    if len(list(items)) > 1:
        tgs="tgs="
        comma = ""
        for atg in items:
            foo = listbox.get(atg)
            tgs = tgs + comma + foo.split(',')[1]
            comma = ","
        sendRemoteControlCommandASCII(tgs)
        sendRemoteControlCommandASCII("txTg=0")
        connected_msg.set(STRING_CONNECTED_TO)
        transmitButton.configure(state='disabled')
    else :
        sendRemoteControlCommandASCII("tgs=" + str(tg))
        sendUSRPCommand(bytes(str(tg), 'ASCII'), USRP_TYPE_DTMF)
    transmit_enable = True
##        setAMBEMode(master.get())
    setDMRInfo()

###################################################################################
# Set the slot 
###################################################################################
def setRemoteTS( ts ):
    sendRemoteControlCommandASCII("txTs=" + str(ts))

###################################################################################
#
###################################################################################
def setDMRID( id ):
    sendRemoteControlCommandASCII("gateway_dmr_id=" + str(id))

###################################################################################
#
###################################################################################
def setPeerID( id ):
    sendRemoteControlCommandASCII("gateway_peer_id=" + str(id))

###################################################################################
#
###################################################################################
def setDMRCall( call ):
    sendRemoteControlCommandASCII("gateway_call=" + call)

###################################################################################
#
###################################################################################
def setDMRInfo():
    sendToGateway("set info " + str(subscriber_id.get()) + ',' + str(repeater_id.get()) + ',' + str(getCurrentTG()) + ',' + str(slot.get()) + ',1')

###################################################################################
#
###################################################################################
def setVoxData():
    v = "true" if vox_enable.get() > 0 else "false"
    sendToGateway("set vox " + v)
    sendToGateway("set vox_threshold " + str(vox_threshold.get()))
    sendToGateway("set vox_delay " + str(vox_delay.get()))

###################################################################################
#
###################################################################################
def getVoxData():
    sendToGateway("get vox")
    sendToGateway("get vox_threshold ")
    sendToGateway("get vox_delay ")

###################################################################################
#
###################################################################################
def setAudioData():
    dm = "true" if dongle_mode.get() > 0 else "false"
    sendToGateway("set dongle_mode " + dm)
    sendToGateway("set sp_level " + str(sp_vol.get()))
    sendToGateway("set mic_level " + str(mic_vol.get()))

###################################################################################
#
###################################################################################
def getCurrentTG():
    items = map(int, listbox.curselection())    # get the item selected in the list
    _first = next(iter(items))
    tg = talk_groups[master.get()][_first][1].translate(noQuote) # get the tg at that index
    return tg

###################################################################################
#
###################################################################################
def selectTGByValue(val):
    count = 0
    listName = master.get()
    for item in talk_groups[listName]:
        if item[1].translate(noQuote) == val:
            listbox.selection_clear(0,listbox.size()-1)
            listbox.selection_set(count)
        count = count + 1

###################################################################################
#
###################################################################################
def findTG(tg):
    listName = master.get()
    itemNum = 0
    for item in talk_groups[listName]:
        if item[1] == tg:
            return itemNum
        itemNum = itemNum+1
    return -1
    
###################################################################################
#
###################################################################################
def getCurrentTGName():
    items = map(int, listbox.curselection())
    _first = next(iter(items))
    tg = talk_groups[master.get()][_first][0]
    return tg

###################################################################################
# Connect to a specific set of TS/TG values
###################################################################################
def connect(tup):
    if regState == False:
        start()
    if tup != None:
        tg = tup[0]
        tg_name = tup[1]
    else:
        tg = getCurrentTG()
        tg_name = getCurrentTGName()
    if tg.startswith('*') == False:     # If it is not a macro, do a full dial sequence
        connected_msg.set( STRING_CONNECTED_TO + " " + tg_name )
#       transmitButton.configure(state='normal')
    
        setRemoteNetwork(master.get())
        setRemoteTS(slot.get())
    setRemoteTG(tg)     # set the TG (or a macro command)

###################################################################################
# Mute all TS/TGs
###################################################################################
def disconnect():
    connected_msg.set(STRING_DISCONNECTED)
#    transmitButton.configure(state='disabled')

###################################################################################
# Create a toast popup and begin the display and fade out
###################################################################################
def popup_toast(msg):
    global toast_frame
    if toast_frame != None: # If a toast is still on the screen, kill it first
        toast_frame.destroy()
    toast_frame = Toplevel()
    toast_frame.wm_title(msg[1])
    toast_frame.overrideredirect(1)

    x = root.winfo_x()
    y = root.winfo_y()
    toast_frame.geometry("+%d+%d" % (x + 250, y + 360))

    l = Label(toast_frame, text=msg[2])
    l.grid(row=0, column=0, padx=(10, 10))
    toast_frame.after(2000, toast_fade_away)

def toast_fade_away():
    global toast_frame
    if toast_frame != None:
        alpha = toast_frame.attributes("-alpha")
        if alpha > 0:
            alpha -= .1
            toast_frame.attributes("-alpha", alpha)
            toast_frame.after(100, toast_fade_away)
        else:
            toast_frame.destroy()
            toast_frame = None
 
def process_queue():
    try:
        msg = ipc_queue.get(0)      # wait forever for a message to be placed in the queue
        if msg[0] == "toast":   # a toast is a tupple of title and text
            popup_toast(msg)
        if msg[0] == "photo":    # an image is just a string containing the call to display
            showQRZImage(msg, qrz_label) 
        if msg[0] == "macro":
            tgDialog(True)       
        if msg[0] == "dialog":
            messagebox.showinfo(STRING_USRP_CLIENT, msg[2], parent=root)
    except queue.Empty:
        pass
    root.after(100, process_queue)

def init_queue():
    global ipc_queue
    ipc_queue = queue.Queue()
    root.after(100, process_queue)

###################################################################################
# Process the button press for disconnect
###################################################################################
def disconnectButton():
    tg = talk_groups[master.get()][0][1].translate(noQuote) # get the tg at that index
    setRemoteTG(tg)
    disconnect()

###################################################################################
#
###################################################################################
def start():
    global regState
    if asl_mode.get() != 0:    # Does this look like a ASL connection to USRP?
        transmitButton.configure(state='normal')    # Yes, fake the registration
        regState = True
    else:
        registerWithAB()

###################################################################################
# Combined command to get all values from servers and display them on UI
###################################################################################
def getValuesFromServer():
    #   ip_address.set("127.0.0.1")
    #   loopback.set(1)

    # get values from Analog_Bridge (repeater ID, Sub ID, master, tg, slot)
    ### Old Command ### sendRemoteControlCommand('get_info')
    sendToGateway('get info')
    #   current_tx_value.set(my_call)          #Subscriber  call
    #    master.set(servers[0])              #DMR Master
    #   repeater_id.set(311317)              #DMR Peer ID
    #   subscriber_id.set(3113043)           #DMR Subscriber radio ID
    slot.set(2)                         #current slot
    listbox.selection_set(0)            #current TG
    connected_msg.set(STRING_CONNECTED_TO)    #current TG
    
    # get values from Analog_Bridge (vox enable, delay and threshold) (not yet: sp level, mic level, audio devices)
    getVoxData()                        #vox enable, delay and threshold
    dongle_mode.set(1)                   #dongle mode enable
    mic_vol.set(50)                      #microphone level
    sp_vol.set(50)                       #speaker level

###################################################################################
# Update server data state to match GUI values
###################################################################################
def sendValuesToServer():
    # send values to Analog_Bridge
    setDMRInfo()
    # tg = getCurrentTG()
    # setRemoteNetwork(master.get())      #DMR Master
    # setRemoteTG(tg)                     #DMR TG
    # setRemoteTS(slot.get())             #DMR slot
    # setDMRID(subscriber_id.get())        #DMR Subscriber ID
    # setDMRCall(my_call)                  #Subscriber call
    # setPeerID(repeater_id.get())         #DMR Peer ID

    # send values to 
    setVoxData()                        #vox enable, delay and threshold
    setAudioData()                      #sp level, mic level, dongle mode

###################################################################################
# Toggle PTT and display new state
###################################################################################
def transmit():
    global ptt
    
    if (transmit_enable == False) and (ptt == False):  # Do not allow transmit key if rx is active
        return

    ptt = not ptt
    if ptt:
        showPTTState(0)
    else:
        showPTTState(1)

###################################################################################
# Update UI with PTT state.
###################################################################################
def showPTTState(flag):
    global tx_start_time
    if ptt:
        transmitButton.configure(highlightbackground='red')
        ttk.Style(root).configure("bar.Horizontal.TProgressbar", troughcolor=uc_background_color, bordercolor=uc_text_color, background="red", lightcolor="red", darkcolor="red")
        tx_start_time = time()
        current_tx_value.set('{} -> {}'.format(my_call, getCurrentTG()))
        html_queue.put((my_call, ""))     # Show my own pic when I transmit
        logging.info("PTT ON")
    else:
        transmitButton.configure(highlightbackground=uc_background_color)
        ttk.Style(root).configure("bar.Horizontal.TProgressbar", troughcolor=uc_background_color, bordercolor=uc_text_color, background="green", lightcolor="green", darkcolor="green")
        if flag == 1:
            _date = strftime("%m/%d/%y", localtime(time()))
            _time = strftime("%H:%M:%S", localtime(time()))
            _duration = '{:.2f}'.format(time() - tx_start_time)
            logList.see(logList.insert('', 'end', None, values=(_date, _time, my_call, str(slot.get()), str(getCurrentTGName()), '0.00%', str(_duration)+'s')))
            current_tx_value.set(my_call)
        ipc_queue.put(empty_photo)  # clear the pic when in idle state
        logging.info("PTT OFF")

###################################################################################
# Convience method to help with ttk values
###################################################################################
def makeTkVar( constructor, val, trace=None ):
    avar = constructor()
    avar.set(val)
    if trace:
        avar.trace('w', trace)
    return avar

###################################################################################
# Callback when the master has changed
###################################################################################
def masterChanged(*args):
    fillTalkgroupList(master.get())     # fill the TG list with the items from the new mode
    current_tx_value.set(my_call)          # Status bar back to idle
    ipc_queue.put(empty_photo)                   # Remove any picture from screen
    if (noTrace != True):               # ignore the event generated by setting the combo box (requestInfo side effect)
        logging.info("New mode selected: %s", master.get())
        setMode(master.get())
        transmit_enable = True
        root.after(1000, requestInfo())

###################################################################################
# Callback when a button is pressed
###################################################################################
def buttonPress(*args):
    messagebox.showinfo(STRING_USRP_CLIENT, "This is just a prototype")

###################################################################################
# Used for debug
###################################################################################
def cb(value):
    logging.info("value = %s", value.get())

###################################################################################
# Create a simple while label 
###################################################################################
def whiteLabel(parent, textVal):
    l = Label(parent, text=textVal, fg=uc_text_color, bg = uc_background_color, anchor=W)
    return l

###################################################################################
# Popup the Talkgroup dialog.  This dialog lets the user enter a custom TG into the list
###################################################################################
def tgDialog(popdown_state):
    d = MyDialog(root)
    d.popdown(popdown_state)
    root.wait_window(d.top)

###################################################################################
# 
###################################################################################
def makeModeFrame( parent ):
    modeFrame = LabelFrame(parent, text = STRING_SERVER, pady = 5, padx = 5, fg=uc_text_color, bg = uc_background_color, bd = 1, relief = SUNKEN)
    ttk.Button(modeFrame, text=STRING_READ, command=getValuesFromServer).grid(column=1, row=1, sticky=W)
    ttk.Button(modeFrame, text=STRING_WRITE, command=sendValuesToServer).grid(column=1, row=2, sticky=W)
    return modeFrame

###################################################################################
#
###################################################################################
def makeAudioFrame( parent ):
    audioFrame = LabelFrame(parent, text = STRING_AUDIO, pady = 5, padx = 5, fg=uc_text_color, bg = uc_background_color, bd = 1, relief = SUNKEN)
    whiteLabel(audioFrame, STRING_MIC).grid(column=1, row=1, sticky=W, padx = 5, pady=1)
    whiteLabel(audioFrame, STRING_SPEAKER).grid(column=1, row=2, sticky=W, padx = 5, pady=1)
    ttk.Scale(audioFrame, from_=0, to=100, orient=HORIZONTAL, variable=mic_vol,
              command=lambda x: cb(mic_vol)).grid(column=2, row=1, sticky=(W,E), pady=1)
    ttk.Scale(audioFrame, from_=0, to=100, orient=HORIZONTAL, variable=sp_vol,
              command=lambda x: cb(sp_vol)).grid(column=2, row=2, sticky=(W,E), pady=1)

    devices = listAudioDevices(True)
    if len(devices) > 0:
        whiteLabel(audioFrame, STRING_INPUT).grid(column=1, row=3, sticky=W, padx = 5)
        invar = StringVar(root)
        invar.set(devices[0]) # default value
        inp = OptionMenu(audioFrame, invar, *devices)
        inp.config(width=20, bg=uc_background_color)
        inp.grid(column=2, row=3, sticky=W)

    whiteLabel(audioFrame, STRING_OUTPUT).grid(column=1, row=4, sticky=W, padx = 5)
    devices = listAudioDevices(False)
    outvar = StringVar(root)
    outvar.set(devices[0]) # default value
    out = OptionMenu(audioFrame, outvar, *devices)
    out.config(width=20, bg=uc_background_color)
    out.grid(column=2, row=4, sticky=W)

    return audioFrame

###################################################################################
# Populate the talkgroup list with the entries loaded from the configuration file
###################################################################################
def fillTalkgroupList( listName ):
    listbox.delete(0, END)
    for item in talk_groups[listName]:
        listbox.insert(END, item[0])
    listbox.selection_set(0)

###################################################################################
#
###################################################################################
def makeGroupFrame( parent ):
    global listbox
    dmrFrame = LabelFrame(parent, text = STRING_TALKGROUPS, pady = 5, padx = 5, fg=uc_text_color, bg = uc_background_color, bd = 1, relief = SUNKEN)
    whiteLabel(dmrFrame, STRING_TS).grid(column=1, row=1, sticky=W, padx = 5)
    Spinbox(dmrFrame, from_=1, to=2, width = 5, fg=uc_text_color, bg=uc_background_color, textvariable = slot).grid(column=2, row=1, sticky=W)
    whiteLabel(dmrFrame, STRING_TG).grid(column=1, row=2, sticky=(N, W), padx = 5)

    listFrame = Frame(dmrFrame, bd=1, highlightbackground="black", highlightcolor="black", highlightthickness=1)
    listFrame.grid(column=2, row=2, sticky=W, columnspan=2)
    listbox = Listbox(listFrame, selectmode=EXTENDED, bd=0, bg=uc_background_color)
    listbox.configure(fg=uc_text_color, exportselection=False)
    listbox.grid(column=1, row=1, sticky=W)

    scrollbar = Scrollbar(listFrame, orient="vertical")
    scrollbar.config(command=listbox.yview)
    scrollbar.grid(column=3, row=1, sticky=(N,S))
    listbox.config(yscrollcommand=scrollbar.set)

    fillTalkgroupList(defaultServer)
    ttk.Button(dmrFrame, text=STRING_TG, command= lambda: tgDialog(False), width = 3).grid(column=1, row=3, sticky=W)
    ttk.Button(dmrFrame, text=STRING_CONNECT, command= lambda: connect(None)).grid(column=2, row=3, sticky=W)
    ttk.Button(dmrFrame, text=STRING_DISCONNECT, command=disconnectButton).grid(column=3, row=3, sticky=W)
    return dmrFrame

###################################################################################
#
###################################################################################
def makeLogFrame( parent ):
    global logList
    logFrame = Frame(parent, pady = 5, padx = 5, bg = uc_background_color, bd = 1, relief = SUNKEN)

    logList = ttk.Treeview(logFrame)
    logList.grid(column=1, row=2, sticky=W, columnspan=5)
    
    cols = (STRING_DATE, STRING_TIME, STRING_CALL, STRING_SLOT, STRING_TG, STRING_LOSS, STRING_DURATION)
    widths = [85, 85, 80, 55, 150, 70, 95]
    logList.config(columns=cols)
    logList.column("#0", width=1 )
    i = 0
    for item in cols:
        a = 'w' if i < 6 else 'e'
        logList.column(item, width=widths[i], anchor=a )
        logList.heading(item, text=item)
        i += 1

    setup_rightmouse_menu(root, logList)
    return logFrame

###################################################################################
#
###################################################################################
def makeTransmitFrame(parent):
    global transmitButton
    transmitFrame = Frame(parent, pady = 5, padx = 5, bg = uc_background_color, bd = 1)
    transmitButton = Button(transmitFrame, text=STRING_TRANSMIT, command=transmit, width = 40, font='Helvetica 18 bold', state='disabled')
    transmitButton.grid(column=1, row=1, sticky=W)
    transmitButton.configure(highlightbackground=uc_background_color)


    #ttk.Scale(transmitFrame, from_=0, to=100, orient=HORIZONTAL, variable=audio_level,).grid(column=1, row=2, sticky=(W,E), pady=1)

    ttk.Progressbar(transmitFrame, style="bar.Horizontal.TProgressbar", orient=HORIZONTAL, variable=audio_level).grid(column=1, row=2, sticky=(W,E), pady=1)


    return transmitFrame

###################################################################################
# Handle the user clicking on the pic, launch a browser with the URL pointint to the
# lookup.
###################################################################################
def clickQRZImage(event):
    call = event.widget.callsign
    if len(call) > 0:
        webbrowser.open_new_tab("http://www.qrz.com/lookup/"+call)

def makeQRZFrame(parent):
    global qrz_label, qrz_call, qrz_name
    qrzFrame = Frame(parent, bg = uc_background_color, bd = 1)
    lx = Label(qrzFrame, text="", anchor=W, bg = uc_background_color, cursor="hand2")
    lx.grid(column=1, row=1, sticky=W)
    qrz_label = lx
    qrz_label.bind("<Button-1>", clickQRZImage)

    meta_frame = Frame(qrzFrame, bg = uc_background_color, bd = 1)
    meta_frame.grid(column=2, row=1, sticky=N)

    qrz_call = Label(meta_frame, textvariable=current_call, anchor=W, fg=uc_text_color, bg = uc_background_color, font='Helvetica 18 bold')
    qrz_call.grid(column=1, row=1, sticky=EW)
    qrz_name = Label(meta_frame, textvariable=current_name, anchor=W, fg=uc_text_color, bg = uc_background_color, font='Helvetica 18 bold')
    qrz_name.grid(column=1, row=2, sticky=EW)

    return qrzFrame

###################################################################################
#
###################################################################################
def makeAppFrame( parent ):
    appFrame = Frame(parent, pady = 5, padx = 5, bg = uc_background_color, bd = 1, relief = SUNKEN)
    appFrame.grid(column=0, row=0, sticky=(N, W, E, S))
    appFrame.columnconfigure(0, weight=1)
    appFrame.rowconfigure(0, weight=1)

    makeModeSettingsFrame(appFrame).grid(column=0, row=1, sticky=(N,W), padx = 5)
    makeQRZFrame(appFrame).grid(column=0, row=2, sticky=W, padx=5)
    makeGroupFrame(appFrame).grid(column=2, row=1, sticky=N, rowspan=2)
    makeTransmitFrame(appFrame).grid(column=0, row=3, sticky=N, columnspan=3, pady = 10)

    return appFrame

###################################################################################
#
###################################################################################
def makeModeSettingsFrame( parent ):
    ypad = 4
    dmrgroup = LabelFrame(parent, text=STRING_MODE, padx=5, pady=ypad, fg=uc_text_color, bg = uc_background_color, relief = SUNKEN)
    whiteLabel(dmrgroup, "Mode").grid(column=1, row=1, sticky=W, padx = 5, pady = ypad)
    w = OptionMenu(dmrgroup, master, *servers)
    w.grid(column=2, row=1, sticky=W, padx = 5, pady = ypad)
    w.config(fg=uc_text_color, bg=uc_background_color)
    w["menu"].config(fg=uc_text_color)
    w["menu"].config(bg=uc_background_color)

    whiteLabel(dmrgroup, STRING_REPEATER_ID).grid(column=1, row=2, sticky=W, padx = 5, pady = ypad)
    Entry(dmrgroup, width = 20, bg = uc_background_color, fg=uc_text_color, textvariable = repeater_id).grid(column=2, row=2, pady = ypad)
    whiteLabel(dmrgroup, STRING_SUBSCRIBER_ID).grid(column=1, row=3, sticky=W, padx = 5, pady = ypad)
    Entry(dmrgroup, width = 20, bg = uc_background_color, fg=uc_text_color, textvariable = subscriber_id).grid(column=2, row=3, pady = ypad)

    return dmrgroup

###################################################################################
#
###################################################################################
def makeVoxSettingsFrame( parent ):
    ypad = 4
    voxSettings = LabelFrame(parent, text=STRING_VOX, padx=5, pady = ypad, fg=uc_text_color, bg = uc_background_color, relief = SUNKEN) 
    Checkbutton(voxSettings, text = STRING_DONGLE_MODE, variable=dongle_mode, command=lambda: cb(dongle_mode), fg=uc_text_color, bg = uc_background_color, bd = 0, highlightthickness = 0).grid(column=1, row=1, sticky=W)
    Checkbutton(voxSettings, text = STRING_VOX_ENABLE, variable=vox_enable, command=lambda: cb(vox_enable), fg=uc_text_color, bg = uc_background_color, bd = 0, highlightthickness = 0).grid(column=1, row=2, sticky=W)
    whiteLabel(voxSettings, STRING_VOX_THRESHOLD).grid(column=1, row=3, sticky=W, padx = 5, pady = ypad)
    Spinbox(voxSettings, from_=1, to=32767, width = 5, fg=uc_text_color, bg=uc_background_color, textvariable = vox_threshold).grid(column=2, row=3, sticky=W, pady = ypad)
    whiteLabel(voxSettings, STRING_VOX_DELAY).grid(column=1, row=4, sticky=W, padx = 5, pady = ypad)
    Spinbox(voxSettings, from_=1, to=500, width = 5, fg=uc_text_color, bg=uc_background_color, textvariable = vox_delay).grid(column=2, row=4, sticky=W, pady = ypad)

    return voxSettings

###################################################################################
#
###################################################################################
def makeIPSettingsFrame( parent ):
    ypad = 4
    ipSettings = LabelFrame(parent, text=STRING_NETWORK, padx=5, pady = ypad, fg=uc_text_color, bg = uc_background_color, relief = SUNKEN)
    Checkbutton(ipSettings, text = STRING_LOOPBACK, variable=loopback, command=lambda: cb(loopback), fg=uc_text_color, bg = uc_background_color, bd = 0, highlightthickness = 0).grid(column=1, row=1, sticky=W)
    whiteLabel(ipSettings, STRING_IP_ADDRESS).grid(column=1, row=2, sticky=W, padx = 5, pady = ypad)
    Entry(ipSettings, width = 20, fg=uc_text_color, bg=uc_background_color, textvariable = ip_address).grid(column=2, row=2, pady = ypad)
    return ipSettings

###################################################################################
#
###################################################################################
def makeSettingsFrame( parent ):
    settingsFrame = Frame(parent, width = 500, height = 500,pady = 5, padx = 5, bg = uc_background_color, bd = 1, relief = SUNKEN)
    makeModeFrame(settingsFrame).grid(column=1, row=1, sticky=(N,W), padx = 5)
    makeIPSettingsFrame(settingsFrame).grid(column=2, row=1, sticky=(N,W), padx = 5, pady = 5, columnspan=2)
    makeVoxSettingsFrame(settingsFrame).grid(column=1, row=2, sticky=(N,W), padx = 5)
    makeAudioFrame(settingsFrame).grid(column=2, row=2, sticky=(N,W), padx = 5)
    return settingsFrame

###################################################################################
#
###################################################################################
def makeAboutFrame( parent ):
    aboutFrame = Frame(parent, width = parent.winfo_width(), height = parent.winfo_height(),pady = 5, padx = 5, bg = uc_background_color, bd = 1, relief = SUNKEN)
    aboutText = "USRP Client (pyUC) Version " + UC_VERSION + "\n"
    aboutText += "(C) 2019, 2020 DVSwitch, INAD.\n"
    aboutText += "Created by Mike N4IRR and Steve N4IRS\n"
    aboutText += "pyUC comes with ABSOLUTELY NO WARRANTY\n\n"
    aboutText += "This software is for use on amateur radio networks only,\n"
    aboutText += "it is to be used for educational purposes only. Its use on\n"
    aboutText += "commercial networks is strictly prohibited.\n\n"
    aboutText += "Code improvements are encouraged, please\n"
    aboutText += "contribute to the development branch located at"
    linkText = "https://github.com/DVSwitch/USRP_Client\n"

    background = None
    try:
        image_url = "https://media.boingboing.net/wp-content/uploads/2017/06/giphy-2.gif"
        image_byt = urllib.request.urlopen(image_url).read()
        image_b64 = base64.encodebytes(image_byt)
        background = PhotoImage(data=image_b64)
        background = background.subsample(3, 3)
        lx = Label(aboutFrame, text="maz", anchor=W, image=background, cursor="hand2")
        lx.photo = background
        lx.callsign = "n4irr"
        lx.bind("<Button-1>", clickQRZImage)
        lx.grid(column=1, row=1, sticky=NW, padx = 5, pady = 5)

    except:
        logging.warning("no image:" + str(sys.exc_info()[1]))
    msg = Message(aboutFrame, text=aboutText, fg=uc_text_color, bg = uc_background_color, anchor=W, width=500)
    msg.grid(column=2, row=1, sticky=NW, padx = 5, pady = 0)

    link = Label(aboutFrame, text=linkText, bg = uc_background_color, fg='blue', anchor=W, cursor="hand2")
    link.grid(column=2, row=2, sticky=NW, padx = 5, pady = 0)
    link.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/DVSwitch/USRP_Client"))
    f = font.Font(link, link.cget("font"))
    f.configure(underline=True)
    link.configure(font=f)

    return aboutFrame

###################################################################################
# Each second this function will be called, update the status bar
###################################################################################
def update_clock(obj):
    now = strftime("%H:%M:%S")
    obj.configure(text=now)
    root.after(1000, update_clock, obj)

###################################################################################
#
###################################################################################
def makeStatusBar( parent ):
    w = 25
    statusBar = Frame(parent, pady = 5, padx = 5, bg = uc_background_color)
    Label(statusBar, fg=uc_text_color, bg = uc_background_color, textvariable=connected_msg, anchor='w', width = w).grid(column=1, row=1, sticky=W)
    Label(statusBar, fg=uc_text_color, bg = uc_background_color, textvariable=current_tx_value, anchor='center', width = w).grid(column=2, row=1, sticky=N)
    obj = Label(statusBar, fg=uc_text_color, bg = uc_background_color, text="", anchor='e', width = w)
    obj.grid(column=3, row=1, sticky=E)
    root.after(1000, update_clock, obj)
    return statusBar

def setStyles():
    style = ttk.Style(root)
    # set ttk theme to "clam" which support the fieldbackground option
    style.theme_use("clam")
    style.configure("Treeview", background=uc_background_color, fieldbackground=uc_background_color, foreground=uc_text_color)
    style.configure('TNotebook.Tab', foreground=uc_text_color, background=uc_background_color)
    style.map('TNotebook.Tab', background=[('disabled', 'magenta')])
    style.configure('TButton', foreground=uc_text_color, background=uc_background_color)
    style.configure("bar.Horizontal.TProgressbar", troughcolor=uc_background_color, bordercolor=uc_text_color, background="green", lightcolor="green", darkcolor="green")

###################################################################################
# Read an int value from the ini file.  If an error or value is Default, return the 
# valDefault passed in.
###################################################################################
def readValue( config, stanza, valName, valDefault, func ):
    try:
        val = config.get(stanza, valName).split(None)[0]
        if val.lower() == "default":  # This is a special case for the in and out index settings
            return valDefault
        return func(val)
    except:
        return valDefault

###################################################################################
# It is required that the user edit the ini file and fill in at least three values.
# The callsign, DMR Id and the USRP server address must be set to something other
# than the default values to be valid.
###################################################################################
def validateConfigInfo():
    valid = (my_call != "N0CALL")               # Make sure they set a ham radio callsign
    valid &= (subscriber_id != 3112000)         # Make sure they set a DMR/CCS7 ID
    valid &= (ip_address.get() != "1.2.3.4")    # Make sure they have a valid address for AB
    return valid

###################################################################################
# Close down the app when the main window closes.  Signal the threads to terminate
# and tell AB we are done.
###################################################################################
def on_closing():
    global done
    logging.info(STRING_EXITING)
    done = True             # Signal the threads to terminate
    if regState == True:    # If we were registered, tell AB we are done
        sleep(1)            # wait just a moment for them to die
        unregisterWithAB()
    root.destroy()

############################################################################################################
#
############################################################################################################
def get_rt_menu_call():
    iid = logList.selection()
    call = logList.item(iid)['values'][2].strip()
    is_valid = False
    if len(call) > 0:
        if call.isdigit() == False:
            is_valid = True
    return (is_valid, call)

def lookup_call_on_web( service, url):
    is_valid, call = get_rt_menu_call()
    if is_valid == True:
        logging.info("Lookup call " + call + " on service " + service)
        webbrowser.open_new_tab(url+call)

def menu1():
    lookup_call_on_web( "QRZ", "http://www.qrz.com/lookup/")
    pass
def menu2():
    lookup_call_on_web( "aprs.fi", "https://aprs.fi/#!call=a%2F")
    pass
def menu3():
    lookup_call_on_web( "Brandmeister", "https://brandmeister.network/index.php?page=profile&call=")
    pass
def menu4():
    lookup_call_on_web( "Hamdata.com", "http://hamdata.com/getcall.html?callsign=")
    pass
def menu5():
    pass

def setup_rightmouse_menu(master, tree):
    tree.aMenu = Menu(master, tearoff=0)
    tree.aMenu.add_command(label='QRZ', command=menu1)
    tree.aMenu.add_command(label='aprs.fi', command=menu2)
    tree.aMenu.add_command(label='Brandmeister', command=menu3)
    tree.aMenu.add_command(label='Hamdata lookup', command=menu4)
    tree.aMenu.add_command(label='Private Call', command=menu5)

    # attach popup to treeview widget
    tree.bind("<Button-2>", popup)
    tree.bind("<Button-3>", popup)
    tree.aMenu.bind("<FocusOut>",popupFocusOut)

def popup(event):
    iid = logList.identify_row(event.y)
    if iid:
        # mouse pointer over item
        logList.selection_set(iid)
        logList.aMenu.post(event.x_root, event.y_root)            
        logList.aMenu.focus_set()
    else:
        pass
def popupFocusOut(self,event=None):
        logList.aMenu.unpost()

############################################################################################################
# Global commands
############################################################################################################

root = Tk()
root.title(STRING_USRP_CLIENT)
root.resizable(width=FALSE, height=FALSE)
root.configure(bg=uc_background_color)

nb = ttk.Notebook(root)     # A tabbed interface container

# Load data from the config file
if len(sys.argv) > 1:
    config_file_name = sys.argv[1]      # Use the command line argument for the path to the config file
else:
    config_file_name = str(Path(sys.argv[0]).parent) + "/pyUC.ini"       # Use the default config file name in the same dir as .py file
config = configparser.ConfigParser(inline_comment_prefixes=(';',))
config.optionxform = lambda option: option
try:
    config.read(config_file_name)
    my_call = config.get('DEFAULTS', "myCall").split(None)[0]
    loopback = makeTkVar(IntVar, config.get('DEFAULTS', "loopback").split(None)[0])
    dongle_mode = makeTkVar(IntVar, config.get('DEFAULTS', "dongleMode").split(None)[0])
    vox_enable = makeTkVar(IntVar, config.get('DEFAULTS', "voxEnable").split(None)[0])
    mic_vol = makeTkVar(IntVar, config.get('DEFAULTS', "micVol").split(None)[0])
    sp_vol = makeTkVar(IntVar, config.get('DEFAULTS', "spVol").split(None)[0])
    repeater_id = makeTkVar(IntVar, config.get('DEFAULTS', "repeaterID").split(None)[0])
    subscriber_id = makeTkVar(IntVar, config.get('DEFAULTS', "subscriberID").split(None)[0])
    vox_threshold = makeTkVar(IntVar, config.get('DEFAULTS', "voxThreshold").split(None)[0])
    vox_delay = makeTkVar(IntVar, config.get('DEFAULTS', "voxDelay").split(None)[0])
    ip_address = makeTkVar(StringVar, config.get('DEFAULTS', "ipAddress").split(None)[0])
    usrp_tx_port = [int(i) for i in config.get('DEFAULTS', "usrpTxPort").split(',')]
    usrp_rx_port = int(config.get('DEFAULTS', "usrpRxPort").split(None)[0])
    slot = makeTkVar(IntVar, config.get('DEFAULTS', "slot").split(None)[0])
    defaultServer = config.get('DEFAULTS', "defaultServer").split(None)[0]
    asl_mode = makeTkVar(IntVar, config.get('DEFAULTS', "aslMode").split(None)[0])
    useQRZ = bool(readValue(config, 'DEFAULTS', 'useQRZ', True, int))
    level_every_sample = int(readValue(config, 'DEFAULTS', 'levelEverySample', 2, int))
    NAT_ping_timer = int(readValue(config, 'DEFAULTS', 'pingTimer', 0, int))

    in_index = readValue(config, 'DEFAULTS', 'in_index', None, int)
    out_index = readValue(config, 'DEFAULTS', 'out_index', None, int)

    uc_background_color = readValue(config, 'DEFAULTS', 'backgroundColor', 'gray25', str)
    uc_text_color = readValue(config, 'DEFAULTS', 'textColor', 'white', str)

    talk_groups = {}
    for sect in config.sections():
        if (sect != "DEFAULTS") and (sect != "MACROS"):
            talk_groups[sect] = config.items(sect)

    if "MACROS" in config.sections():
        for x in config.items("MACROS"):
            macros[x[1]] = x[0]

    if validateConfigInfo() == False:
        logging.error(STRING_CONFIG_NOT_EDITED)
        os._exit(1)
        
except:
    logging.error(STRING_CONFIG_FILE_ERROR + str(sys.exc_info()[1]))
    sys.exit('Configuration file \''+config_file_name+'\' is not a valid configuration file! Exiting...')

servers = sorted(talk_groups.keys())
master = makeTkVar(StringVar, defaultServer, masterChanged)
connected_msg = makeTkVar(StringVar, STRING_CONNECTED_TO)
current_tx_value = makeTkVar(StringVar, my_call)
current_call = makeTkVar(StringVar, "")
current_name = makeTkVar(StringVar, "")
audio_level = makeTkVar(IntVar, 0)

setStyles()

# Add each frame to the "notebook" (tabs)
nb.add(makeAppFrame( nb ), text=STRING_TAB_MAIN)
nb.add(makeSettingsFrame( nb ), text=STRING_TAB_SETTINGS)
nb.add(makeAboutFrame( nb ), text=STRING_TAB_ABOUT)
nb.grid(column=1, row=1, sticky='EW')

# Create the other frames
makeLogFrame(root).grid(column=1, row=2)
makeStatusBar(root).grid(column=1, row=3, sticky=W+E)

init_queue()    # Create the queue for thread to main app communications
openStream()    # Open the UDP stream to AB
with noalsaerr():
    p = pyaudio.PyAudio()
_thread.start_new_thread( rxAudioStream, () )
if in_index != -1:  # Do not launch the TX thread if the user wants RX only access
    _thread.start_new_thread( txAudioStream, () )
_thread.start_new_thread( html_thread, () )     # Start up the HTML thread for background image loads
if NAT_ping_timer > 0:
    _thread.start_new_thread( ping_thread, () )

disconnect()    # Start out in the disconnected state
start()         # Begin the handshake with AB (register)

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

