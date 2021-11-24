#!/usr/bin/env bash
# Wrapper script for ichat_to_eml.py

destdir=~/Desktop/iChats_converted

mkdir -p "$destdir"

for f in ~/Documents/iChats/*chat;
do ./ichat_to_eml.py --no-background --attach-original "$f" "$destdir" ;
done
