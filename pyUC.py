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
from time import time, sleep, clock, localtime, strftime
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

UC_VERSION = "1.1.0"

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
empty_photo = ("photo", "", "")     # instance of a blank photo
SAMPLE_RATE = 48000                 # Default audio sample rate for pyaudio (will be resampled to 8K)
toast_frame = None                  # A toplevel window used to display toast messages
ipc_queue = None                    # Queue used to pass info to main hread (UI)
ptt = False                         # Current ptt state
tx_start_time = 0                   # TX timer
done = False                        # Thread stop flag
transmit_enable = True              # Make sure that UC is half duplex

listbox = None                      # tk object (talkgroup)
transmitButton = None               # tk object
logList = None                      # tk object

###################################################################################
# HTML/QRZ import libraries
try:
    from urllib.request import urlopen
    from bs4 import BeautifulSoup
    from PIL import Image, ImageTk
    import requests
except:
    print("fatal error, python package not found: " + str(sys.exc_info()[1]))
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
            callsign = html_queue.get(0)        # wait forever for a message to be placed in the queue (a callsign)
            photo = getQRZImage( callsign )     # lookup the call and return an image     
            ipc_queue.put(("photo", callsign, photo))
        except queue.Empty:
            pass
        sleep(0.1)

# Return the URL of an image associated with the callsign.  The URL may be cached or scraped from QRZ    
def getImgUrl( callsign ):
    img = ""
    if callsign in qrz_cache:
        return qrz_cache[callsign]['url']

    # specify the url
    quote_page = 'https://qrz.com/lookup/' + callsign

    # query the website and return the html to the variable ‘page’
    page = urlopen(quote_page).read()

    # parse the html using beautiful soup and store in variable `soup`
    soup = BeautifulSoup(page, 'html.parser')
    try:
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
            image = Image.open(resp)
            image.thumbnail((170,110), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            qrz_cache[callsign]['image'] = photo
    return photo

# Run on the main thread, show the image in the passed UI element (label)
def showQRZImage( msg, in_label ):
    photo = msg[2]
    in_label.configure(image=photo)
    in_label.image = photo
    in_label.callsign = msg[1]

###################################################################################


###################################################################################
# Log output to console
###################################################################################
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

###################################################################################
# Manage a popup dialog for on the fly TGs
###################################################################################
class MyDialog:
    
    def __init__(self, parent):
        
        top = self.top = Toplevel(parent)
        
        Label(top, text="Talk Group").pack()
        
        self.e = Entry(top)
        self.e.pack(padx=5)
        
        b = Button(top, text="OK", command=self.ok)
        b.pack(pady=5)
    
    def ok(self):
        
        logging.info( "value is %s", self.e.get() )
        item = self.e.get()
        if len(item):
            mode = master.get()
            talk_groups[mode].append((item, item))
            fillTalkgroupList(master.get())
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
        logging.info("On Windows, ignore the port reuse")
        pass
    udp.bind(('', usrp_rx_port))

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
# RX thread, collect audio and metadata from AB
###################################################################################
def rxAudioStream():
    global ip_address
    global noTrace
    global regState
    global transmit_enable
    logging.info('Start rx audio thread')
    USRP = bytes("USRP", 'ASCII')
    REG = bytes("REG:", 'ASCII')
    UNREG = bytes("UNREG", 'ASCII')
    OK = bytes("OK", 'ASCII')
    INFO = bytes("INFO:", 'ASCII')
    EXITING = bytes("EXITING", 'ASCII')

    FORMAT = pyaudio.paInt16
    CHUNK = 160
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
        logging.critical("fatal error, can not open output audio stream" + str(sys.exc_info()[1]))
        messagebox.showinfo("USRP Client", "Output stream  open error")
        os._exit(1)

    _i = p.get_default_output_device_info().get('index') if out_index == None else out_index
    logging.info("Output Device: {} Index: {}".format(p.get_device_info_by_host_api_device_index(0, _i).get('name'), _i))

    lastKey = -1
    start_time = time()
    call = ''
    tg = ''
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
                        stream.write(bytes(audio48), 160 * 6)
                    else:
                        stream.write(audio, 160)
                if (keyup != lastKey):
                    logging.debug('key' if keyup else 'unkey')
                    if keyup:
                        start_time = time()
                    if keyup == False:
                        logging.info('End TX:   {} {} {} {} {:.2f}s'.format(call, rxslot, tg, loss, time() - start_time))
                        logList.see(logList.insert('', 'end', None, values=(
                                                                            strftime(" %m/%d/%y", localtime(start_time)),
                                                                            strftime("%H:%M:%S", localtime(start_time)),
                                                                            call.ljust(10), rxslot, tg, loss, '{:.2f}s'.format(time() - start_time))))
                        root.after(1000, logList.yview_moveto, 1)
                        current_tx_value.set(my_call)
                        ipc_queue.put(empty_photo)
                        transmit_enable = True  # Idle state, allow local transmit
                lastKey = keyup
            elif (type == USRP_TYPE_TEXT): #metadata
                if (audio[0:4] == REG):
                    if (audio[4:6] == OK):
                        connected_msg.set( "Registered" )
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
                        tmp = audio[:audio.find('\x00')] # C string
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
                    elif (_json[0:6] == "MACRO:"):  # Ignore macros for now.
                        pass
                    else:
                        obj=json.loads(audio[5:audio.find(b'\x00')].decode('ASCII'))
                        noTrace = True  # ignore the event generated by setting the combo box
                        if (obj["tlv"]["ambe_mode"][:3] == "YSF"):
                            master.set("YSF")
                        else:
                            master.set(obj["tlv"]["ambe_mode"])
                        noTrace = False
                        logging.info(audio[:audio.find(b'\x00')].decode('ASCII'))
                        connected_msg.set( "Connected to " + obj["last_tune"] )
                        selectTGByValue(obj["last_tune"])
                else:
                    if audio[0] == TLV_TAG_SET_INFO:
                        rid = (audio[2] << 16) + (audio[3] << 8) + audio[4] # Source
                        tg = (audio[9] << 16) + (audio[10] << 8) + audio[11] # Dest
                        rxslot = audio[12]
                        rxcc = audio[13]
                        mode = "Private" if (rxcc  & 0x80) else "Group"
                        if audio[14] == 0: # C string termintor for call
                            call = str(rid)
                        else:
                            call = audio[14:audio.find(b'\x00', 14)].decode('ASCII')
                        listName = master.get()
                        for item in talk_groups[listName]:
                            if item[1] == str(tg):
                                tg = item[0]    # Found the TG number in the list, so we can use its friendly name
                        current_tx_value.set('{} -> {}'.format(call, tg))
                        logging.info('Begin TX: {} {} {} {}'.format(call, rxslot, tg, mode))
                        transmit_enable = False # Transmission from network will disable local transmit
                        if call.isdigit() == False:
                            html_queue.put(call)
                        if ((rxcc  & 0x80) and (rid > 10000)): 
#                            logging.info('rid {} ctg {}'.format(rid, getCurrentTG()))
                            # a dial string with a pound is a private call, see if the current TG matches
                            privateTG = str(rid) + '#'
                            if (privateTG != getCurrentTG()):
                                #Tune to tg
                                sendRemoteControlCommandASCII("txTg=" + privateTG)
                                talk_groups[listName].append((call + " Private", privateTG))
                                fillTalkgroupList(listName)
                            selectTGByValue(privateTG)
            elif (type == USRP_TYPE_PING):
#                logging.debug(audio[:audio.find('\x00')])
                pass
    
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
        logging.critical("fatal error, can not open input audio stream" + str(sys.exc_info()[1]))
        messagebox.showinfo("USRP Client", "Input stream  open error")
        os._exit(1)

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

            ###### Vox processing #####
            if vox_enable.get():
                rms = audioop.rms(audio, 2)     # Get a relative power value for the sample
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
                udp.sendto(usrp, (ip_address.get(), usrp_tx_port))
                usrpSeq = usrpSeq + 1
            lastPtt = ptt
            if ptt:
                usrp = 'USRP'.encode('ASCII') + struct.pack('>iiiiiii',usrpSeq, 0, ptt, 0, USRP_TYPE_VOICE, 0, 0) + audio
                udp.sendto(usrp, (ip_address.get(), usrp_tx_port))
                usrpSeq = usrpSeq + 1
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
    connected_msg.set( "Connection failure" )
    logging.error("Socket failure")

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
        udp.sendto(usrp, (ip_address.get(), usrp_tx_port))
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
        connected_msg.set( "Connected to ")
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
def connect():
    if regState == False:
        start()
    tg = getCurrentTG()
    connected_msg.set( "Connected to " + getCurrentTGName() )
#    transmitButton.configure(state='normal')
    
    setRemoteNetwork(master.get())
    setRemoteTS(slot.get())
    setRemoteTG(tg)

###################################################################################
# Mute all TS/TGs
###################################################################################
def disconnect():
    connected_msg.set( "Disconnected ")
#    transmitButton.configure(state='disabled')

###################################################################################
# Create a toast popup and begin the display and fade out
###################################################################################
def popup_toast(msg):
    global toast_frame
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
    alpha = toast_frame.attributes("-alpha")
    if alpha > 0:
        alpha -= .1
        toast_frame.attributes("-alpha", alpha)
        toast_frame.after(100, toast_fade_away)
    else:
        toast_frame.destroy()
 
def process_queue():
    try:
        msg = ipc_queue.get(0)      # wait forever for a message to be placed in the queue
        if msg[0] == "toast":   # a toast is a tupple of title and text
            popup_toast(msg)
        if msg[0] == "photo":    # an image is just a string containing the call to display
            showQRZImage(msg, qrz_label)        
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
    connected_msg.set("Connected to")    #current TG
    
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
        tx_start_time = time()
        current_tx_value.set('{} -> {}'.format(my_call, getCurrentTG()))
        html_queue.put(my_call)     # Show my own pic when I transmit
        logging.info("PTT ON")
    else:
        transmitButton.configure(highlightbackground='white')
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
    messagebox.showinfo("USRP Client", "This is just a prototype")

###################################################################################
# Used for debug
###################################################################################
def cb(value):
    logging.info("value = %s", value.get())

###################################################################################
# Create a simple while label 
###################################################################################
def whiteLabel(parent, textVal):
    l = Label(parent, text=textVal, background = "white", anchor=W)
    return l

###################################################################################
# Popup the Talkgroup dialog.  This dialog lets the user enter a custom TG into the list
###################################################################################
def tgDialog():
    d = MyDialog(root)
    root.wait_window(d.top)

###################################################################################
# 
###################################################################################
def makeModeFrame( parent ):
    modeFrame = LabelFrame(parent, text = "Server", pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    ttk.Button(modeFrame, text="Read", command=getValuesFromServer).grid(column=1, row=1, sticky=W)
    ttk.Button(modeFrame, text="Write", command=sendValuesToServer).grid(column=1, row=2, sticky=W)
    return modeFrame

###################################################################################
#
###################################################################################
def makeAudioFrame( parent ):
    audioFrame = LabelFrame(parent, text = "Audio", pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    whiteLabel(audioFrame, "Mic").grid(column=1, row=1, sticky=W, padx = 5, pady=1)
    whiteLabel(audioFrame, "Speaker").grid(column=1, row=2, sticky=W, padx = 5, pady=1)
    ttk.Scale(audioFrame, from_=0, to=100, orient=HORIZONTAL, variable=mic_vol,
              command=lambda x: cb(mic_vol)).grid(column=2, row=1, sticky=(W,E), pady=1)
    ttk.Scale(audioFrame, from_=0, to=100, orient=HORIZONTAL, variable=sp_vol,
              command=lambda x: cb(sp_vol)).grid(column=2, row=2, sticky=(W,E), pady=1)

    devices = listAudioDevices(True)
    if len(devices) > 0:
        whiteLabel(audioFrame, "Input").grid(column=1, row=3, sticky=W, padx = 5)
        invar = StringVar(root)
        invar.set(devices[0]) # default value
        inp = OptionMenu(audioFrame, invar, *devices)
        inp.config(width=20)
        inp.grid(column=2, row=3, sticky=W)

    whiteLabel(audioFrame, "Output").grid(column=1, row=4, sticky=W, padx = 5)
    devices = listAudioDevices(False)
    outvar = StringVar(root)
    outvar.set(devices[0]) # default value
    out = OptionMenu(audioFrame, outvar, *devices)
    out.config(width=20)
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
    dmrFrame = LabelFrame(parent, text = "Talk Groups", pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    whiteLabel(dmrFrame, "TS").grid(column=1, row=1, sticky=W, padx = 5)
    Spinbox(dmrFrame, from_=1, to=2, width = 5, textvariable = slot).grid(column=2, row=1, sticky=W)
    whiteLabel(dmrFrame, "TG").grid(column=1, row=2, sticky=(N, W), padx = 5)

    listFrame = Frame(dmrFrame, bd=1, highlightbackground="black", highlightcolor="black", highlightthickness=1)
    listFrame.grid(column=2, row=2, sticky=W, columnspan=2)
    listbox = Listbox(listFrame, selectmode=EXTENDED, bd=0)
    listbox.configure(exportselection=False)
    listbox.grid(column=1, row=1, sticky=W)

    scrollbar = Scrollbar(listFrame, orient="vertical")
    scrollbar.config(command=listbox.yview)
    scrollbar.grid(column=3, row=1, sticky=(N,S))
    listbox.config(yscrollcommand=scrollbar.set)

    fillTalkgroupList(defaultServer)
    ttk.Button(dmrFrame, text="TG", command=tgDialog, width = 3).grid(column=1, row=3, sticky=W)
    ttk.Button(dmrFrame, text="Connect", command=connect).grid(column=2, row=3, sticky=W)
    ttk.Button(dmrFrame, text="Disconnect", command=disconnectButton).grid(column=3, row=3, sticky=W)
    return dmrFrame

###################################################################################
#
###################################################################################
def makeLogFrame( parent ):
    global logList
    logFrame = Frame(parent, pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)


    logList = ttk.Treeview(logFrame)
    logList.grid(column=1, row=2, sticky=W, columnspan=5)
    
    cols = ('Date', 'Time', 'Call', 'Slot', 'TG', 'Loss', 'Duration')
    widths = [85, 85, 80, 55, 150, 70, 95]
    logList.config(columns=cols)
    logList.column("#0", width=1 )
    i = 0
    for item in cols:
        a = 'w' if i < 6 else 'e'
        logList.column(item, width=widths[i], anchor=a )
        logList.heading(item, text=item)
        i += 1

    return logFrame

###################################################################################
#
###################################################################################
def makeTransmitFrame(parent):
    global transmitButton
    transmitFrame = Frame(parent, pady = 5, padx = 5, bg = "white", bd = 1)
    transmitButton = Button(transmitFrame, text="Transmit", command=transmit, width = 40, state='disabled')
    transmitButton.grid(column=1, row=1, sticky=W)
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
    global qrz_label
    qrzFrame = Frame(parent, bg = "white", bd = 1)
    lx = Label(qrzFrame, text="", anchor=W, background = "white", cursor="hand2")
    lx.grid(column=1, row=1, sticky=W)
    qrz_label = lx
    qrz_label.bind("<Button-1>", clickQRZImage)
    return qrzFrame

###################################################################################
#
###################################################################################
def makeAppFrame( parent ):
    appFrame = Frame(parent, pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
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
    dmrgroup = LabelFrame(parent, text="MODE", padx=5, pady=ypad, bg = "white")
    whiteLabel(dmrgroup, "Mode").grid(column=1, row=1, sticky=W, padx = 5, pady = ypad)
    w = OptionMenu(dmrgroup, master, *servers)
    w.grid(column=2, row=1, sticky=W, padx = 5, pady = ypad)

    whiteLabel(dmrgroup, "Repeater ID").grid(column=1, row=2, sticky=W, padx = 5, pady = ypad)
    Entry(dmrgroup, width = 20, textvariable = repeater_id).grid(column=2, row=2, pady = ypad)
    whiteLabel(dmrgroup, "Subscriber ID").grid(column=1, row=3, sticky=W, padx = 5, pady = ypad)
    Entry(dmrgroup, width = 20, textvariable = subscriber_id).grid(column=2, row=3, pady = ypad)

    return dmrgroup

###################################################################################
#
###################################################################################
def makeVoxSettingsFrame( parent ):
    ypad = 4
    voxSettings = LabelFrame(parent, text="Vox", padx=5, pady = ypad, bg = "white")
    Checkbutton(voxSettings, text = "Dongle Mode", variable=dongle_mode, command=lambda: cb(dongle_mode), background = "white").grid(column=1, row=1, sticky=W)
    Checkbutton(voxSettings, text = "Vox Enable", variable=vox_enable, command=lambda: cb(vox_enable), background = "white").grid(column=1, row=2, sticky=W)
    whiteLabel(voxSettings, "Threshold").grid(column=1, row=3, sticky=W, padx = 5, pady = ypad)
    Spinbox(voxSettings, from_=1, to=32767, width = 5, textvariable = vox_threshold).grid(column=2, row=3, sticky=W, pady = ypad)
    whiteLabel(voxSettings, "Delay").grid(column=1, row=4, sticky=W, padx = 5, pady = ypad)
    Spinbox(voxSettings, from_=1, to=500, width = 5, textvariable = vox_delay).grid(column=2, row=4, sticky=W, pady = ypad)

    return voxSettings

###################################################################################
#
###################################################################################
def makeIPSettingsFrame( parent ):
    ypad = 4
    ipSettings = LabelFrame(parent, text="Network", padx=5, pady = ypad, bg = "white")
    Checkbutton(ipSettings, text = "Loopback", variable=loopback, command=lambda: cb(loopback), background = "white").grid(column=1, row=1, sticky=W)
    whiteLabel(ipSettings, "IP Address").grid(column=1, row=2, sticky=W, padx = 5, pady = ypad)
    Entry(ipSettings, width = 20, textvariable = ip_address).grid(column=2, row=2, pady = ypad)
    return ipSettings

###################################################################################
#
###################################################################################
def makeSettingsFrame( parent ):
    settingsFrame = Frame(parent, width = 500, height = 500,pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    makeModeFrame(settingsFrame).grid(column=1, row=1, sticky=(N,W), padx = 5)
    makeIPSettingsFrame(settingsFrame).grid(column=2, row=1, sticky=(N,W), padx = 5, pady = 5, columnspan=2)
    makeVoxSettingsFrame(settingsFrame).grid(column=1, row=2, sticky=(N,W), padx = 5)
    makeAudioFrame(settingsFrame).grid(column=2, row=2, sticky=(N,W), padx = 5)
    return settingsFrame

###################################################################################
#
###################################################################################
def makeAboutFrame( parent ):
    aboutFrame = Frame(parent, width = parent.winfo_width(), height = parent.winfo_height(),pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    aboutText = "USRP Client (pyUC) Version " + UC_VERSION + "\n"
    aboutText += "(C) 2019, 2020 DVSwitch, INAD.\n"
    aboutText += "Created by Mike N4IRR and Steve N4IRS\n"
    aboutText += "pyUC comes with ABSOLUTELY NO WARRANTY\n\n"
    aboutText += "This software is for use on amateur radio networks only,\n"
    aboutText += "it is to be used for educational purposes only. Its use on\n"
    aboutText += "commercial networks is strictly prohibited.\n"

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
        lx.grid(column=1, row=1, sticky=W, padx = 5, pady = 5)

    except:
        logging.warning("no image:" + str(sys.exc_info()[1]))
    Message(aboutFrame, text=aboutText, background = "white", anchor=W, width=500).grid(column=2, row=1, sticky=NW, padx = 5, pady = 5)
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
    w = 22
    statusBar = Frame(parent, pady = 5, padx = 5)
    Label(statusBar, textvariable=connected_msg, anchor=W, width = w).grid(column=1, row=1, sticky=W)
    Label(statusBar, textvariable=current_tx_value, anchor=CENTER, width = w).grid(column=2, row=1, sticky=N)
    obj = Label(statusBar, text="", anchor=E, width = w)
    obj.grid(column=3, row=1, sticky=E)
    root.after(1000, update_clock, obj)
    return statusBar

###################################################################################
# Read an int value from the ini file.  If an error or value is Default, return the 
# valDefault passed in.
###################################################################################
def readValue( config, stanza, valName, valDefault ):
    try:
        val = config.get(stanza, valName).split(None)[0]
        if val.lower() == "default":  # This is a special case for the in and out index settings
            return valDefault
        return int(val)
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
    logging.info("Exiting pyUC...")
    done = True             # Signal the threads to terminate
    if regState == True:    # If we were registered, tell AB we are done
        sleep(1)            # wait just a moment for them to die
        unregisterWithAB()
    root.destroy()

############################################################################################################
# Global commands
############################################################################################################

root = Tk()
root.title("USRP Client")
root.resizable(width=FALSE, height=FALSE)

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
    usrp_tx_port = int(config.get('DEFAULTS', "usrpTxPort").split(None)[0])
    usrp_rx_port = int(config.get('DEFAULTS', "usrpRxPort").split(None)[0])
    slot = makeTkVar(IntVar, config.get('DEFAULTS', "slot").split(None)[0])
    defaultServer = config.get('DEFAULTS', "defaultServer").split(None)[0]
    asl_mode = makeTkVar(IntVar, config.get('DEFAULTS', "aslMode").split(None)[0])

    in_index = readValue(config, 'DEFAULTS', 'in_index', None)
    out_index = readValue(config, 'DEFAULTS', 'out_index', None)

    talk_groups = {}
    for sect in config.sections():
        if (sect != "DEFAULTS"):
            talk_groups[sect] = config.items(sect)

    if validateConfigInfo() == False:
        logging.error('Please edit the configuration file and set it up correctly. Exiting...')
        os._exit(1)
        
except:
    logging.error("Config (ini) file error: " + str(sys.exc_info()[1]))
    sys.exit('Configuration file \''+config_file_name+'\' is not a valid configuration file! Exiting...')

servers = sorted(talk_groups.keys())
master = makeTkVar(StringVar, defaultServer, masterChanged)
connected_msg = makeTkVar(StringVar, "Connected to")
current_tx_value = makeTkVar(StringVar, my_call)

# Add each frame to the "notebook" (tabs)
nb.add(makeAppFrame( nb ), text='Main')
nb.add(makeSettingsFrame( nb ), text='Settings')
nb.add(makeAboutFrame( nb ), text='About')
nb.grid(column=1, row=1)

# Create the other frames
makeLogFrame(root).grid(column=1, row=2)
makeStatusBar(root).grid(column=1, row=3)

init_queue()    # Create the queue for thread to main app communications
openStream()    # Open the UDP stream to AB
with noalsaerr():
    p = pyaudio.PyAudio()
_thread.start_new_thread( rxAudioStream, () )
if in_index != -1:  # Do not launch the TX thread if the user wants RX only access
    _thread.start_new_thread( txAudioStream, () )
_thread.start_new_thread( html_thread, () )     # Start up the HTML thread for background image loads

disconnect()    # Start out in the disconnecte state
start()         # Begin the handshake with AB (register)

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

