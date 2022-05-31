#!/usr/bin/python3.8 -u

# ----------------------------------------------------------------------------------------------------------------------
#
# ethernetLink.py
# Author: Mike Schoonover
# Date: 07/09/21
#
# Purpose:
#
# This class handles the link to a remote device via Ethernet connections. The remote device is expected to initiate the
# connection; this class watches for and accepts requests to connect.
#
# Open Source Policy:
#
# This source code is Public Domain and free to any interested party.  Any
# person, company, or organization may do with it as they please.
#
# ----------------------------------------------------------------------------------------------------------------------

import select
import socket

from typing import Final, List, Tuple  # also available: Set, Dict, Tuple, Optional

from .spudLinkExceptions import SocketBroken
from .circularBuffer import CircularBuffer

# https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html

RECEIVE_BUFFER_SIZE: Final[int] = 50    # debug mks ~ increase this to 1024 or so

# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# class EthernetLink
#
# This class handles the link to a remote device via Ethernet connections.
#


class EthernetLink:

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::__init__
    #

    def __init__(self, pRemoteDescriptiveName: str):

        """
            EthernetLink initializer.

            :param pRemoteDescriptiveName: a human friendly name for the connected remote device
            :type pRemoteDescriptiveName: str
        """

        self.remoteDescriptiveName = pRemoteDescriptiveName
        self.connected: bool = False

        self.receiveBuf = CircularBuffer(RECEIVE_BUFFER_SIZE)

        self.clientSocket: socket = None
        self.clientSocketList: List[socket] = []

        # remoteAddress -> (remote Address, remote port)
        self.remoteAddress: Tuple[str, int] = ("", 0)

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', 4242))
        self.server_socket.listen(1)
        self.server_socket_list: List[socket] = [self.server_socket]

        print("Listening for Ethernet connection request on port 4242.")

    # end of EthernetLink::__init__
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::doRunTimeTasks
    #

    def doRunTimeTasks(self) -> int:

        """
            Handles ongoing tasks associated with the socket stream such as reading data and storing in a buffer.

            :return: 0 on success, -1 on error
            :rtype: int

        """

        if not self.connected:
            return 0

        self.handleReceive()

        return 0

    # end of EthernetLink::doRunTimeTasks
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::handleReceive
    #
    # This function reads all available bytes from the stream and stores them in a circular buffer.
    #
    # Strangely (and stupidly) enough, Python does not have a simple method to check if bytes are available in the
    # socket (such as Java's bytesAvailable). Thus, attempting to read an empty blocking socket will hang until data is
    # ready or until a timeout value is reached.
    #
    # This issue is handled here by calling select.select which will return a list containing socket(s) with data ready.
    # For this program, the socket is left as blocking and the normally blocking call to select is made non-blocking by
    # specifying a timeout of 1. This will allow for a quick check to see if at least one byte is ready.
    #

    def handleReceive(self):

        inputs = [self.clientSocket]
        outputs = [self.clientSocket]
        errors = [self.clientSocket]

        # inError: List[socket] = []

        try:
            readReady, writeReady, inError = select.select(inputs, outputs, errors, 0)
        except select.error:
            print("Ethernet Connection Error in select.select")
            return

        if inError:
            print("Ethernet Connection Error")
            return

        while readReady:  # {

            data = self.clientSocket.recv(1)

            if data == b'':
                raise SocketBroken("Error 135: Ethernet Socket Connection Broken!")

            self.receiveBuf.append(int.from_bytes(data, byteorder='big'))

            readReady, writeReady, in_error = select.select(inputs, outputs, errors, 0)

        # }

    # EthernetLink::handleReceive
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::connectToRemoteIfRequestPending
    #

        """
            Checks for pending connection requests and accepts one if present. Only one connection at a time is allowed.
            The remote device is expected to initiate the connection.

            If a new connection is accepted, returns 1.
            
            Python also has epoll, poll, and kqueue implementations for platforms that support them. They are more
            efficient versions of select. But perhaps select is more universally supported?
            
            https://stackoverflow.com/questions/5308080/python-socket-accept-nonblocking

            :return: 0 on no new connection, 1 if new connection accepted, -1 on error
            :rtype: int
        """

    def connectToRemoteIfRequestPending(self) -> int:

        if not self.connected:

            readable, writable, error = select.select(self.server_socket_list, [], [], 0)

            if not readable:
                return 0

            for s in readable:

                if s is self.server_socket:

                    self.clientSocket, self.remoteAddress = self.server_socket.accept()
                    self.clientSocketList.append(self.clientSocket)
                    print("\n\nConnection accepted from " + self.remoteDescriptiveName + " at " +
                          self.remoteAddress[0] + "\n")

                    self.connected = True

                    return 1

                # else:
                #
                #     data = s.recv(1024)
                #
                #     if data:
                #         s.send(data)
                #     else:
                #         s.close()
                #         self.client_socket_list.remove(s)

        return 0

    # end of EthernetLink::connectToRemoteIfRequestPending
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::getConnected
    #

    def getConnected(self) -> bool:

        """
            Returns the 'connected' flag which is true if connected to remote and false otherwise.
           :return: 'connected' flag
           :rtype: int
        """

        return self.connected

    # end of EthernetLink::getConnected
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::disconnect
    #

    def disconnect(self) -> int:

        """
            Disconnects from the remote device by performing shutdown() and close() on the socket.
            Sets self.connected to False.

            Resets the receive buffer so that any existing data will not affect future operations.

            :return: 0 if successful, -1 on error
            :rtype: int
        """

        self.receiveBuf.reset()

        self.connected = False

        try:
            self.clientSocket.shutdown(socket.SHUT_RDWR)
        except OSError:
            print("OSError on socket shutdown...will attempt to close anyway...")
            print("  this is usually OSError: [Errno 107] Transport endpoint is not connected...")
            print("***************************************************************************************")
        try:
            self.clientSocket.close()
        except OSError:
            raise SocketBroken("Error 252: Ethernet Socket Connection Broken!")

        print("Disconnected from " + self.remoteDescriptiveName + " at " + self.remoteAddress[0])

        return 0

    # end of EthernetLink::disconnect
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::getInputStream
    #

    def getInputStream(self) -> CircularBuffer:

        """
            Returns an "InputStream" for the remote device. For the Python version of this function, actually returns a
            CircularBuffer which the EthernetLink uses to buffer the input stream.
            
            :return: reference to a CircularBuffer used to buffer the input stream for the remote device
            :rtype: CircularBuffer
        """

        return self.receiveBuf

    # end of EthernetLink::getInputStream
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::getOutputStream
    #

    def getOutputStream(self) -> socket:

        """
            Returns a socket for the remote device. For Python, a socket is returned rather than a Stream as might be
            done for Java (yay Java!).

            :return: reference to a socket for the remote device
            :rtype: socket
        """

        return self.clientSocket

    # end of EthernetLink::getOutputStream
    # --------------------------------------------------------------------------------------------------


# end of class EthernetLink
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

# package backpackDevice;
#
# //-----------------------------------------------------------------------------
#
#
# //-----------------------------------------------------------------------------
# // class RS232Link
# //
# //
# //
#
# public class RS232Link implements Communications{
#
# 	SerialPort comPort;
#
# 	int numBytesRead;
#
#     byte[] inBuffer = new byte[10];
#     byte[] outBuffer = new byte[10];
#
# 	StringBuilder inString = new StringBuilder(1024);
#
# 	boolean simulate = false;
#
# 	ThreadSafeLogger tsLog;
#
# 	//the timeout used for reading and writing of the serial port
# 	static final int SERIAL_PORT_TIMEOUT = 500; //debug mks -- set back to 250
#
# 	//multiply SERIAL_PORT_READ_TIMEOUT * SERIAL_PORT_READ_SLEEP_MS to get time out in milliseconds
# 	//these values are used in a loop
# 	static final int SERIAL_PORT_READ_TIMEOUT = 50;
# 	static final int SERIAL_PORT_READ_SLEEP_MS = 10;
#
# 	static final int LINE_TERMINATOR = 0x0a;
#
# 	static final int READ_BYTES_LIMIT = 10000;
#
# 	static final int NUM_BYTES_TO_READ_FOR_CLEARING = 100000;
#
# 	static final int DEVICE_RESPONSE_TIMEOUT = 5000;
#
# //-----------------------------------------------------------------------------
# // RS232Link::RS232Link (constructor)
# //
#
# public RS232Link()
# {
#
# }//end of RS232Link::RS232Link (constructor)
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::init
# //
# // Initializes the object.  Must be called immediately after instantiation.
# //
#
# @Override
# public void init(ThreadSafeLogger pThreadSafeLogger)
# {
#
#     tsLog = pThreadSafeLogger; comPort = null; numBytesRead = 0;
#
# }// end of RS232Link::init
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::connectToRemote
# //
# /**
#  * Establishes a connection with the remote device.
#  *
#  *
#  * @param pSelectedCOMPort	the name of the Serial COM port to be used for the connection
#  * @param pBaudRate			baud rate for the connection
#  * @return					1 on success, -1 on failure to connect with device
#  *
#  */
#
# public int connectToRemote(String pSelectedCOMPort, int pBaudRate)
# {
#
# 	closeConnectionToRemote();
#
# 	int portIndex = getIndexOfSerialPortSpecifiedByName(pSelectedCOMPort);
#
# 	if(portIndex == -1){ return(-1); }
#
# 	comPort = SerialPort.getCommPorts()[portIndex];
#
# 	if(comPort == null){
# 		tsLog.appendLine("");
# 		tsLog.appendLine("ERROR: cannot open COM Port!!!");
# 		tsLog.appendLine("");
# 		return(-1);
# 	}
#
# 	setPortOptions(pBaudRate);
#
# 	comPort.setDTR(); //establishes connection with device's com port
#
# 	boolean status = comPort.openPort();
#
# /*
#
# 	long markTime = System.currentTimeMillis();
#
# 	while(comPort.bytesAvailable() <= 0){
# 		if ((System.currentTimeMillis() - markTime) > DEVICE_RESPONSE_TIMEOUT){
# 			comPort.closePort();
# 			tsLog.appendLine("ERROR: Connection failed as device did not respond.");
# 			return(-1);
# 		}
# 	}
#
# 	comPort.readBytes(inBuffer, 1);
#
# 	if(inBuffer[0] != 'A'){
# 		comPort.closePort();
# 		tsLog.appendLine("ERROR: Connection failed as device did not return proper greeting.");
# 		return(-1);
# 	}
#
# */
#
# 	tsLog.appendLine("Baud Rate = " + pBaudRate + "...");
#
# 	tsLog.appendLine("Device is connected.\n");
#
# 	return(1);
#
# }// end of RS232Link::connectToRemote
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::closeConnectionToRemote
# //
# /**
#  * Closes the com port connection. Also sets the DTR line low.
#  *
#  * @return	true if port successfully closed, false if not
#  *
#  */
#
# public boolean closeConnectionToRemote()
# {
#
# 	if(comPort == null || !comPort.isOpen()) { return(true); }
#
# 	comPort.clearDTR(); //breaks connection with device's com port
#
# 	return(comPort.closePort());
#
# }// end of RS232Link::closeConnectionToRemote
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::setPortOptions
# //
# /**
#  * Sets various options for comPort such as timeouts, baud rate, stop bit, parity, flow control.
#  *
#  * @param pBaudRate		the baud rate for the serial com port
#  *
#  */
#
# void setPortOptions(int pBaudRate)
# {
#
# 	comPort.setComPortTimeouts(SerialPort.TIMEOUT_NONBLOCKING, 0, 0);
#
# 	comPort.setComPortParameters(pBaudRate, 8, SerialPort.ONE_STOP_BIT, SerialPort.NO_PARITY);
#
# 	comPort.setFlowControl(SerialPort.FLOW_CONTROL_DISABLED);
#
# }// end of RS232Link::setPortOptions
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::closeConnection
# //
# // Closes the serial port connected to the remote device.
# //
#
# public void closeConnection(){
#
#
# 	if(comPort == null){ return; }
#
# 	comPort.closePort();
#
# }// end of RS232Link::closeConnection
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::sendString
# //
# // Sends a String to the remote device. A LINE_TERMINATOR value is sent as the last byte, so it
# // should not be added to the String.
# //
#
# public void sendString(String pString)
# {
#
# 	if(comPort == null){ return; }
#
# 	try {
#
# 		byte tempBuffer[] = pString.getBytes();
#
# 		comPort.writeBytes(tempBuffer, tempBuffer.length);
#
# 		outBuffer[0] = LINE_TERMINATOR;
# 		comPort.writeBytes(outBuffer, 1);
#
# 	} catch (Exception e) { /* debug mks log this */}
#
# }// end of RS232Link::sendString
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::readResponse
# //
# // Calls readResponse(READ_BYTES_LIMIT).
# //
# // See readResponse readResponse(int pMaxNumBytes) for details.
# //
#
# public String readResponse()
# {
#
# 	return(readResponse(READ_BYTES_LIMIT));
#
# }// end of RS232Link::readResponse
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::readResponse
# //
# // Reads a character response from the remote device. Characters will be read until pMaxNumBytes
# // have been read, LINE_TERMINATOR is received to indicate the end of the response, or timeout
# // occurs.
# //
# // The response will be returned as a String. If timeout before any characters received, the
# // String will have length of 0. If timeout before LINE_TERMINATOR is received, the last character
# // of the String will not be LINE_TERMINATOR.
# //
# // timeout in milliseconds ~= SERIAL_PORT_READ_TIMEOUT * SERIAL_PORT_READ_SLEEP_MS
# //
#
# public String readResponse(int pMaxNumBytes)
# {
#
# 	if(comPort == null){ return(""); }
#
# 	int timeoutLoopCounter = 0;
# 	boolean done = false;
# 	byte[] inByte = new byte[1];
#
# 	inString.setLength(0);
#
# 	try {
#
# 		while (!done && timeoutLoopCounter++ < SERIAL_PORT_READ_TIMEOUT){
#
# 			while(!done && comPort.bytesAvailable() != 0){
#
# 				comPort.readBytes(inByte, 1);
#
# 				inString.append((char)inByte[0]);
#
# 				timeoutLoopCounter = 0;
#
# 				if(inString.length() == pMaxNumBytes){ done = true; break; }
#
# 				if(inByte[0] == LINE_TERMINATOR){ done = true; }
# 			}
#
# 			if(!done) { Thread.sleep(SERIAL_PORT_READ_SLEEP_MS); }
#
# 		}
# 	} catch (InterruptedException e) { /* debug mks log this */}
#
# 	return(inString.toString());
#
# }// end of RS232Link::readResponse
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::clearCOMPortReceiveBuffer
# //
# // Clears the COM port receive buffer by reading NUM_BYTES_TO_READ_FOR_CLEARING
# // bytes or until a timeout occurs.
# //
# // If bytesAvailable() returns <=0, returns with no action.
# //
# // Returns the number of bytes read.
# //
#
# public int clearCOMPortSendBuffer()
# {
#
# 	if(comPort.bytesAvailable() <= 0){ return(0); }
#
# 	readBytesResponse(NUM_BYTES_TO_READ_FOR_CLEARING);
#
# 	return(numBytesRead);
#
# }// end of RS232Link::clearCOMPortReceiveBuffer
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::readBytesResponse
# //
# // Reads a byte response from the remote device. Characters will be read until pMaxNumBytes have
# // been read or timeout occurs.
# //
# // The response will be returned as a byte array. If timeout before any characters received, the
# // byte array will be empty.
# //
# // The number of bytes read will be stored in class variable numBytesRead.
# //
# // timeout in milliseconds ~= SERIAL_PORT_READ_TIMEOUT * SERIAL_PORT_READ_SLEEP_MS
# //
#
# public byte[] readBytesResponse(int pMaxNumBytes)
# {
#
# 	if(comPort == null){ return(null); }
#
# 	int timeoutLoopCounter = 0;
# 	boolean done = false;
# 	byte[] inByte = new byte[1];
# 	byte[] inBytes = new byte[pMaxNumBytes];
#
# 	int i = 0;
#
# 	try {
#
# 		while (!done && timeoutLoopCounter++ < SERIAL_PORT_READ_TIMEOUT){
#
# 			while(!done && comPort.bytesAvailable() != 0){
#
# 				comPort.readBytes(inByte, 1);
#
# 				inBytes[i++] = inByte[0];
#
# 				timeoutLoopCounter = 0;
#
# 				if(i == pMaxNumBytes){ done = true; break; }
#
# 			}
#
# 			if(!done) { Thread.sleep(SERIAL_PORT_READ_SLEEP_MS); }
#
# 		}
# 	} catch (InterruptedException e) { /* debug mks log this */}
#
# 	numBytesRead = i;
#
# 	return(inBytes);
#
# }// end of RS232Link::readBytesResponse
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::convertBytesToCommaDelimitedDecimalString
# //
# // Returns the bytes in pBuffer as a comma-delimited string of decimal numbers.
# //
#
# public String convertBytesToCommaDelimitedDecimalString(byte[] pBuffer)
# {
#
# 	inString.setLength(0);
#
# 	for(byte b : pBuffer){
# 		inString.append(b);
# 		inString.append(',');
# 	}
#
# 	return(inString.toString());
#
# }// end of RS232Link::convertBytesToCommaDelimitedDecimalString
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::getListOfSerialComPorts
# //
# // Retrieves from the operating system a list of the available serial com ports.
# //
# // Returns an array of SerialPort objects.
# //
#
# public SerialPort[] getListOfSerialComPorts()
# {
#
# 	return(SerialPort.getCommPorts());
#
# }// end of RS232Link::getListOfSerialComPorts
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::getListOfSerialComPortNames
# //
# // Retrieves from the operating system a list of names of the available serial com ports. These
# // will be in the form of "COM1", "COM25", etc.
# //
# // Returns a ListArray<String> object.
# //
#
# public ArrayList<String> getListOfSerialComPortNames()
# {
#
# 	SerialPort[] serialPorts = getListOfSerialComPorts();
#
# 	ArrayList<String> names = new ArrayList<>(serialPorts.length);
#
# 	for(SerialPort port : serialPorts){ names.add(port.getSystemPortName()); }
#
# 	return(names);
#
# }// end of RS232Link::getListOfSerialComPortNames
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::getIndexOfSerialPortSpecifiedByName
# //
# // Finds the index of the serial port with a name matching pName
# //
# // Returns the index of the port.
# // If no match is found, returns -1.
# //
#
# protected int getIndexOfSerialPortSpecifiedByName(String pName)
# {
#
# 	ArrayList<String> ports =  getListOfSerialComPortNames();
#
# 	if(ports.isEmpty()){
# 		tsLog.appendLine("no serial port found!");
# 		return(-1);
# 	}
#
# 	if(!ports.contains(pName)){
# 		tsLog.appendLine(pName + " serial port not found!");
# 		return(-1);
# 	}
#
# 	return(ports.indexOf(pName));
#
# }// end of RS232Link::getIndexOfSerialPortSpecifiedByName
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::sendInitCommands
# //
#
# public void sendInitCommands(){
#
#
#
# }// end of RS232Link::sendInitCommands
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // RS232Link::waitSleep
# //
# // Sleeps for pTime milliseconds.
# //
#
# public void waitSleep(int pTime)
# {
#
#     try {Thread.sleep(pTime);} catch (InterruptedException e) { }
#
# }//end of RS232Link::waitSleep
# //-----------------------------------------------------------------------------
#
# 	@Override
# 	public void open() {
# 		throw new UnsupportedOperationException("Not supported yet."); //To change body of generated methods,
# 		choose Tools | Templates.
# 	}
#
# 	@Override
# 	public void close() {
# 		throw new UnsupportedOperationException("Not supported yet."); //To change body of generated methods,
# 		choose Tools | Templates.
# 	}
#
# 	@Override
# 	public byte readByte() {
# 		throw new UnsupportedOperationException("Not supported yet."); //To change body of generated methods,
# 		choose Tools | Templates.
# 	}
#
# 	@Override
# 	public byte[] readBytes(int pNumBytes) {
# 		throw new UnsupportedOperationException("Not supported yet."); //To change body of generated methods,
# 		choose Tools | Templates.
# 	}
#
# 	@Override
# 	public byte peek() {
# 		throw new UnsupportedOperationException("Not supported yet."); //To change body of generated methods,
# 		choose Tools | Templates.
# 	}
#
# }//end of class RS232Link
# //-----------------------------------------------------------------------------
# //-----------------------------------------------------------------------------
