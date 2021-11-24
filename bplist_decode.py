#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Decoder for iChat message logs encoded in Apple's Binary Propery List (BPList) format.

    To test, run ./bplist_decode.py inputfile.ichat and decoded output will be produced on stdout.
    Error messages are produced on stderr.
"""

import sys
import os
from pprint import pprint
import copy
import hashlib
import pytz

import attachment_type
import rtfd_decode
from ccl_bplist import ccl_bplist  # https://github.com/cclgroupltd/ccl-bplist


# Debug toggle
debug = False

# Specify local timezone for timestamps in chat logs
localtz = 'America/New_York'

def main(args):
    """When run directly, parse and dump the contents of the specified file to stdout.

    This is mostly for development/test/debugging purposes.
    """
    with open(args[1],'rb') as f:
        conv = bplist_to_conv(f)
    
    pprint(conv)  # pretty print and write to stdout for testing/development
    
    return 0


def bplist_to_conv(plistfile):
    """Take a byte stream from an iChat BPList log (.ichat) and produce a 'conversation' dictionary."""
    debug_msg('Starting parsing of binary plist')
    
    conversation = {}
    conversation['participants'] = []
    conversation['userids'] = []
    conversation['names'] = []
    conversation['messages'] = []
    
    ccl_bplist.set_object_converter(ccl_bplist.NSKeyedArchiver_common_objects_convertor)  # enable object conversion
    pdict = ccl_bplist.load(plistfile)  # parse the binary plist file
    
    base_obj = ccl_bplist.deserialise_NsKeyedArchiver(pdict, parse_whole_structure=True)  # parse base element
    root_obj = base_obj['root']  # root of object tree
    
    # Conversation-level metadata (seem to always be present)
    conversation['startobj'] = pytz.UTC.localize(base_obj['metadata']['StartTime'])
    
    conversation['endobj'] = pytz.UTC.localize(base_obj['metadata']['EndTime'])
    conversation['dateobj'] = conversation['endobj']  # to maintain same format as typedstream decoder
    
    if base_obj['metadata']['Service'] == 'AOL Instant Messenger':
        conversation['protocol'] = 'AIM'  # for consistency with old typedstream logs
    else:
        conversation['protocol'] = base_obj['metadata']['Service']
    
    # Human-readable names
    if isinstance(base_obj['metadata']['Participants'], str):  # should always be at least 1 participant
        conversation['names'].append(base_obj['metadata']['Participants'].strip())
    if isinstance(base_obj['metadata']['Participants'], list):  # more commonly there are 2 in a list
        for u in base_obj['metadata']['Participants']:
            conversation['names'].append(u.strip())
    
    # Presentity object (if included)
    if 'PresentityIDs' in base_obj['metadata']:
        for u in base_obj['metadata']['PresentityIDs']:
            if u.split(':')[-1] not in conversation['userids']:
                conversation['userids'].append(u.split(':')[-1])  # account names or phone numbers
    
    if 'LastMessageID' in base_obj['metadata']:
        conversation['totalmessages'] = base_obj['metadata']['LastMessageID']  # only on iMessages?
    
    i = 0  # TODO for debugging
    # root_obj[2] is the list of messages
    for msg_obj in root_obj[2]:
        if msg_obj['$class']['$classname'] == 'InstantMessage':
            debug_msg("Processing message " + str(i))  # TODO uses debug variable
            
            message = {}
            
            if 'GUID' in msg_obj:
                message['guid'] = msg_obj['GUID']
            
            if 'Sender' in msg_obj:
                if msg_obj['Sender'] is None:  # special case where Sender is NoneType
                    message['from'] = ''
                elif 'ID' in msg_obj['Sender']:
                    message['from'] = msg_obj['Sender']['ID'].split(':')[-1]
                    if message['from'] not in conversation['participants']:
                        conversation['participants'].append(message['from'])
                elif 'AccountID' in msg_obj['Sender']:
                    message['fromguid'] = msg_obj['Sender']['AccountID']
            
            if 'Time' in msg_obj:
                message['dateobj'] = pytz.UTC.localize(msg_obj['Time'])
            
            if 'MessageText' in msg_obj:
                message['text'] = msg_obj['MessageText']['NSString']
                if 'NSAttributes' in msg_obj['MessageText']:
                    if 'NSFont' in msg_obj['MessageText']['NSAttributes']:  # this is the most common arrangement
                        message['textfont'] = msg_obj['MessageText']['NSAttributes']['NSFont']['NSName']
                        message['textsize'] = msg_obj['MessageText']['NSAttributes']['NSFont']['NSSize']
                    elif isinstance(msg_obj['MessageText']['NSAttributes'], list):  # but sometimes there's an intermediate list
                        if 'NSFont' in msg_obj['MessageText']['NSAttributes'][0]:
                            message['textfont'] = msg_obj['MessageText']['NSAttributes'][0]['NSFont']['NSName']
                            message['textsize'] = msg_obj['MessageText']['NSAttributes'][0]['NSFont']['NSSize']
                    if 'NSAttachment' in msg_obj['MessageText']['NSAttributes']:  # indicates an attachment
                        if 'NSFileWrapper' in msg_obj['MessageText']['NSAttributes']['NSAttachment']:  # file attachment
                            attachment = {}
                            if msg_obj['MessageText']['NSAttributes']['NSAttachment']['NSFileWrapper']:  # if FileWrapper isn't null...
                                attachment['data'] = msg_obj['MessageText']['NSAttributes']['NSAttachment']['NSFileWrapper']['NSFileWrapperData']['NS.data']
                                if rtfd_decode.has_rtfd_magic(attachment['data']):
                                    # special handling for RTFD attachments (most attachments are RTFDed)
                                    attachment = rtfd_decode.decode_rtfd(attachment['data'])
                                    attachment['name'] = attachment['filename']
                                    attachment['type'] = attachment_type.determine_attachment_type(attachment['data'])
                                    attachment['Content-ID'] = hashlib.md5(attachment['data']).hexdigest()
                                    message['attachment'] = attachment
                            else:  # covers case when NSFileWrapper is None
                                attachment['data'] = ''
                                attachment['name'] = 'Empty Attachment'
                                #attachment['Content-ID'] = hashlib.md5(attachment['data']).hexdigest()  # shouldn't be needed?
                            conversation['hasattachments'] = True
            conversation['messages'].append(copy.deepcopy(message))
            i += 1  # TODO for debugging
    
    # If there aren't at least 2 participants in the conversation, set to a default 'Unknown' value
    #  because we need two values for email 'To' and 'From' fields
    if len(conversation['participants']) < 2:
        conversation['participants'].append('UNKNOWN')  # TODO maybe set a default value in environment var?
    
    return conversation


def debug_msg(text):
    if debug:
        sys.stderr.write('DEBUG: [' + sys.argv[1].split(os.path.sep)[-1] + '] ' + text + '\n')

def user_msg(text):
        sys.stderr.write(text + '\n')


if __name__ == "__main__":
    sys.exit( main(sys.argv) )
