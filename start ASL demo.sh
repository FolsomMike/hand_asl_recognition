#!/bin/bash

#
# Oak-D-Lite Cortic Technologies ASL Recognition Demo Launcher
#
# Company:	Folsom Institute of Artificial Intelligence and Robotics
# Author:	Mike Schoonover
# Date:		5/27/2022
#

#
# This program will set up and launch the Cortic Technologies ASL
# Recognition Demo program for the Oak camera series.
#
# Before launching, it will start systemd-udevd daemon if it is not
# running and instruct the user to unplug the camera. This daemon
# controls access to devices such as USB and must be running.
# After starting, the affected USB devices must be unplugged/plugged.
# 
# On normal Linux systems, this daemon is started automatically. In
# WSL, it is often not started since systemd does not function in WSL
# as of 5/27/2022.
#


echo
echo This script must be run using the 'source' command!
echo
echo source 'start ASL demo.sh'
echo

source startUDEVD.sh

cd oak/asl
source virtual.sh
cd hand_asl_recognition
python3 hand_tracker_asl.py

cd ~
