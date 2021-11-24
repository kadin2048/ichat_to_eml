#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Convert iChat log files from the ~/Documents/iChats folder to MIME-based EML files.

    For usage info, run with -h option
    Further information provided in README.md
"""

__author__ = 'Kadin2048 <kadin@sdf.org>'
__copyright__ = 'Copyright 2021, Kadin2048'
__license__ = 'GPLv3 or later'

import sys
import os
import argparse
import datetime
import pytz
import copy
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.mime.nonmultipart import MIMENonMultipart
from email import encoders
from email import charset
import hashlib

import typedstream  # provided, refer to: https://causlayer.orgs.hk/dgelessus/python-typedstream
import rtfd_decode  # provided
import bplist_decode  # provided
import attachment_type  # provided

debug = ''
verbose = ''
args = ''

# Specify local timezone for timestamps in chat logs
localtz = 'America/New_York'

# CSS for styling the HTML part of the message
css = '''<style type = text/css>
.screenname {
  font-weight: bold; 
}
.timestamp {
  font-size: 10pt;
  color: grey;
}
</style>'''


def main():
    # Parse command line arguments w/ argparse library
    argparser = argparse.ArgumentParser(description='Convert iChat logs to MIME text (.eml) files.')
    argparser.add_argument('inputname', help='Input file to process')
    argparser.add_argument('outputdir', nargs='?', default=False,
                           help='Output directory to write EML files to (uses stdout if not given)')
    argparser.add_argument('-v', '--verbose', help='Increase stderr output verbosity', action='store_true')
    argparser.add_argument('--debug', help='Enable debugging mode (implies --verbose)', action='store_true')
    argparser.add_argument('--no-background', help='Strips background color from message text', action='store_true')
    argparser.add_argument('--attach-original', help='Attach original log files to output as application/octet-stream',
                           action='store_true')

    global args
    args = argparser.parse_args()

    user_msg('Processing: "' + args.inputname.split(os.path.sep)[-1] + '"')

    # Files ending in .chat are usually old TypedStream binary files from iChat.app < 2004
    if args.inputname.split('.')[-1] == 'chat':
        try:
            tschat = typedstream.unarchive_from_file(args.inputname)
            conversation = parse_typedstream_chat(tschat)
        except:
            raise

    # Files ending in .ichat are usually newer Binary PLIST files from Messages.app and iChat.app > 2004
    if args.inputname.split('.')[-1] == 'ichat':
        try:
            with open(args.inputname, 'rb') as f:
                conversation = bplist_decode.bplist_to_conv(f)
        except:
            raise

    # Strip background colors if the '--no-background' option is selected
    if args.no_background:
        for message in conversation['messages']:
            if 'bgcolor' in message:
                del (message['bgcolor'])

    # Process conversations into MIME format email messages
    eml = eml_from_conv(conversation, args.inputname)

    # If --attach-original option is specified, add the input file as a MIMEApplication item
    if args.attach_original:
        with open(args.inputname, 'rb') as infile:
            chatpart = MIMEApplication(infile.read(), 'octet-stream')
            chatpart.add_header('Content-Disposition', 'attachment', filename=os.path.basename(args.inputname))
            eml.attach(chatpart)

    # Additional runtime headers to add...
    eml['X-Original-File'] = args.inputname

    if not args.outputdir:  # if user does not specify output dir for file, write to stdout
        sys.stdout.write(eml.as_string())

    if args.outputdir:  # if an output directory is specified, create a file name and write to it
        filename = os.path.splitext(os.path.basename(args.inputname))[0]  # basename without extension
        extension = '.eml'  # alternately: .mhtml, .mht
        with open(os.path.join(args.outputdir, (filename + extension)), 'w') as fo:
            fo.write(eml.as_string())

    return 0  # Exit successfully


def parse_typedstream_chat(tschat):
    # Data structures to hold messages...
    conversation = {}  # is a single conversation (all occurred at same time)
    conversation['messages'] = []  # Ordered list for the message content back and forth
    conversation['participants'] = []  # is a list of participants
    conversation['protocol'] = ''
    conversation['hasattachments'] = False  # default value
    message = {}

    # Determine protocol, stored in tschat.elements[0]
    conversation['protocol'] = tschat.elements[0].value

    # tschat.elements[1] is an empty string, not sure what it's for...

    # tschat.elements[2] should be an NSMutableArray holding multiple GenericArchivedObjects
    for msgobj in tschat.elements[2].elements:
        if msgobj.clazz.name.decode('utf-8') == 'InstantMessage':  # We care only about InstantMessage objects here
            # Most InstantMessage objects seem to have 3 parts:
            # (0) Presentity, (1) date object, (2) NSAttributedString
            for i in msgobj.contents:
                try:
                    if i.value.clazz.name.decode('utf-8') == 'Presentity':
                        if i.value.contents[1].value.value not in conversation['participants']:
                            conversation['participants'].append(i.value.contents[1].value.value)
                        message['from'] = i.value.contents[1].value.value
                except AttributeError:
                    pass
                try:
                    if isinstance(i.value.value, datetime.datetime):
                        message['dateobj'] = i.value.value  # Appears that .chat time objects are tz-aware and in UTC
                except AttributeError:
                    pass
                try:
                    if i.value.clazz.name.decode('utf-8') == 'NSAttributedString':
                        message['text'] = i.value.contents[0].value.value
                        for j in list(i.value.contents[2].value.contents.items()):
                            # some possible values for list(j)[0].value include 'NSColor', 'NSBackgroundColor', 'NSFont', 'NSAttachment'
                            if list(j)[0].value == 'NSFont':
                                textfontobj = list(j)[
                                    1]  # list(j)[1] should be <class 'typedstream.types.appkit.NSFont'>
                                message['textfont'] = textfontobj.name
                                message['textsize'] = textfontobj.size
                            if list(j)[0].value == 'NSColor':
                                textcolorobj = list(j)[
                                    1].value  # list(j)[1].value should be <class 'typedstream.types.appkit.NSColor.RGBAValue'>
                                message['textcolor'] = ('rgba(' +
                                                        str(int(textcolorobj.red * 255)) + ', ' +
                                                        str(int(textcolorobj.green * 255)) + ', ' +
                                                        str(int(textcolorobj.blue * 255)) + ', ' +
                                                        str(textcolorobj.alpha) + ')')
                            if list(j)[0].value == 'NSBackgroundColor':
                                bgcolorobj = list(j)[1].value
                                message['bgcolor'] = ('rgba(' +
                                                      str(int(bgcolorobj.red * 255)) + ',' +
                                                      str(int(bgcolorobj.green * 255)) + ',' +
                                                      str(int(bgcolorobj.blue * 255)) + ',' +
                                                      str(bgcolorobj.alpha) + ')')
                            if list(j)[0].value == 'NSAttachment':
                                attachment = {}
                                attachmentdataobj = list(j)[1].contents[0].values[1].contents[
                                    0].value  # should be <class 'typedstream.types.foundation.NSMutableData'>
                                attachment['data'] = attachmentdataobj.data  # usually NSFileWrapper serialized object
                                attachment['type'] = attachment_type.determine_attachment_type(attachment['data'])
                                attachment['name'] = 'Unnamed Attachment'
                                # Special handling for NSFileWrapper serialized files, which are hard to open/view
                                #  See rtfd_decode.py for details
                                if attachment['type'] == 'application/x-nsfilewrapper-serialized':
                                    attachment = rtfd_decode.decode_rtfd(attachment['data'])
                                    attachment['name'] = attachment['filename']  # Use filename as logical name
                                    attachment['type'] = attachment_type.determine_attachment_type(attachment['data'])
                                attachment['Content-ID'] = hashlib.md5(attachment['data']).hexdigest()
                                message['attachment'] = attachment
                                conversation['hasattachments'] = True
                except AttributeError:
                    debug_msg('AttributeError encountered while parsing message contents; skipping message')
                    pass
                except IndexError:
                    debug_msg('IndexError encountered while parsing message contents; skipping message')
                    pass

            conversation['messages'].append(copy.deepcopy(message))
            message = {}  # clear contents of message

    # tschat.elements[2:] is the remainder of the file and can contain various items
    for l1 in tschat.elements[2:]:
        # tschat.elements[3] in test file is a NSMutableArray (maybe always last?)
        try:
            for l2 in l1.elements:
                try:
                    if l2.clazz.name.decode(
                            'utf-8') == 'Presentity':  # Look for Presentity objects not inside an InstantMessage
                        for l3 in l2.contents:
                            if (l3.value.value not in conversation['participants']) and (
                                    l3.value.value not in conversation['protocol']):
                                conversation['participants'].append(l3.value.value)
                except AttributeError:
                    pass
        except AttributeError:
            pass

    # Set overall date/time on conversation to the last message timestamp
    #  because iChat maintains timestamps per message, not per conversation
    conversation['dateobj'] = conversation['messages'][-1]['dateobj']

    # If there aren't at least 2 participants in the conversation, set to a default 'Unknown' value
    #  because we need two values for email 'To' and 'From' fields
    if len(conversation['participants']) < 2:
        conversation['participants'].append('UNKNOWN')  # TODO maybe set a default value in environment var?

    return conversation


def eml_from_conv(conv, infilename):
    """ Takes a conversation and processes it into an RFC-compliant email.

        Returns a MIMEMultipart object.
        Based on aolim_to_eml.py
    """

    global localtz
    tz = pytz.timezone(localtz)

    # Create a fake domain-like string for constructing URL-like identifiers such as Message-ID
    fakedomain = conv['protocol'] + '.ichat.invalid'

    eml = MIMEMultipart('related')  # related is used if there are attachments
    emlalt = MIMEMultipart('alternative')  # alternative is for text and HTML portions

    cs_ = charset.Charset('utf-8')
    cs_.header_encoding = charset.SHORTEST  # https://docs.python.org/3/library/email.charset.html
    cs_.body_encoding = charset.QP
    eml.set_charset(cs_)
    emlalt.set_charset(cs_)

    # Build email subject from original file name, since it's the only place the person's real name is stored
    #  iChat used two file naming conventions over time...
    #  The original (until late 2003) was numbered, e.g.: 'John Doe #7.chat'
    #  Then Apple changed to date/time stamp: 'John Doe on 2004-07-06 at 01.35.chat'
    if ' #' in infilename.split(os.path.sep)[-1]:
        # A '#' in the name means we are using the old .chat numbered filename convention
        eml['Subject'] = ('iChat with ' + os.path.basename(infilename).split(' on ')[0].split(' #')[0] +
                          ' on ' + conv['dateobj'].astimezone(tz).strftime('%a, %b %d %Y'))
    elif ' on ' in infilename.split(os.path.sep)[-1]:
        # This means we're using the newer .chat and .ichat convention with a date/time
        eml['Subject'] = ('iChat with ' + os.path.basename(infilename).split(' on ')[0] +
                          ' on ' + conv['dateobj'].astimezone(tz).strftime('%a, %b %d %Y'))
    else:
        # Special case for first chat with new person using old .chat name convention (no #0, just their name)
        eml['Subject'] = ('iChat with ' + os.path.basename(infilename).split('.chat')[0] +
                          ' on ' + conv['dateobj'].astimezone(tz).strftime('%a, %b %d %Y'))

    # Set headers for email message
    #  The originator (first message) of the conversation is 'From'
    #  and the first other participant to send a msg is the 'To'
    eml['From'] = ('"' + conv['participants'][0] + '" ' + '<' + conv['participants'][
        0] + '@' + fakedomain + '>')  # pseudo domain for From
    eml['To'] = ('"' + conv['participants'][1] + '" ' + '<' + conv['participants'][
        1] + '@' + fakedomain + '>')  # pseudo domain for To
    eml['Date'] = conv['dateobj'].astimezone(tz).strftime('%a, %d %b %Y %T %z')  # RFC2822 format

    # Generate the plaintext view of the conversation (text/text)
    text_lines = []
    for message in conv['messages']:  # each message is a dict with 'from' and 'text' keys
        line = []
        if 'dateobj' in message:
            line.append('(' + message['dateobj'].astimezone(tz).strftime('%r') + ')&nbsp;')
        if 'from' in message:
            line.append(message['from'] + ':\t')
        if 'text' in message:
            line.append(message['text'])
        text_lines.append(''.join(line))
        if 'attachment' in message:
            text_lines.append(
                '\tAttachment: <' + message['attachment']['Content-ID'] + '> "' + message['attachment']['name'] + '"')
    text_part = MIMENonMultipart('text', 'plain',
                                 charset='utf-8')  # can't use MIMEText because it always uses BASE64 for UTF8, ugh
    text_part.set_payload(u'\n'.join(text_lines), charset=cs_)
    emlalt.attach(text_part)

    # And also an HTML view (text/html)
    html_lines = []
    html_lines.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">')
    html_lines.append('<html>')
    html_lines.append('<head>\n' + css + '\n</head>')  # see css at top of file
    html_lines.append('<body>')
    for message in conv['messages']:
        line = []
        line.append('<p class="message">')
        if 'dateobj' in message:
            line.append('<span class="timestamp">')
            line.append('(' + message['dateobj'].astimezone(tz).strftime('%r') + ')&nbsp;')
            line.append('</span>')
        if 'from' in message:
            line.append('<span class="screenname">')
            line.append(message['from'] + ':&ensp;')
            line.append('</span>')
        if 'text' in message:
            line.append('<span')
            if ('textfont' in message) or ('textsize' in message) or ('textcolor' in message) or ('bgcolor' in message):
                # only if needed, we add a style attribute to the message text...
                line.append(' style="')
                if 'textfont' in message:
                    line.append('font-family: ' + message['textfont'] + '; ')
                if 'textsize' in message:
                    line.append('font-size: ' + str(int(message['textsize'])) + 'pt; ')
                if 'textcolor' in message:
                    line.append('color: ' + message['textcolor'] + '; ')
                if 'bgcolor' in message:
                    line.append('background-color: ' + message['bgcolor'] + '; ')
                line.append('"')
            line.append(' class="message_text">')
            line.append(message['text'].replace('\n', '<br>'))
            line.append('</span>')
        if 'attachment' in message:
            line.append('\n<br><span class="attachment">Attachment:&nbsp;<a href="cid:' + message['attachment'][
                'Content-ID'] + '">' + message['attachment']['name'] + '</a></span>')
            if message['attachment']['data']:
                attachment_part = MIMEBase('application', message['attachment']['type'].split('/')[-1])
                attachment_part.set_payload(message['attachment']['data'])
                encoders.encode_base64(attachment_part)  # BASE64 for all attachments (still needed as of 2021)
                attachment_part.add_header('Content-Disposition', 'attachment', filename=message['attachment']['name'])
                attachment_part['Content-ID'] = '<' + message['attachment']['Content-ID'] + '>'
                eml.attach(attachment_part)  # attach to the top-level object, multipart/related
        line.append('</p>')
        html_lines.append(''.join(line))
    html_lines.append('</body>')
    html_lines.append('</html>')
    html_part = MIMENonMultipart('text', 'html', charset='utf-8')
    html_part.set_payload(u'\n'.join(html_lines), charset=cs_)
    emlalt.attach(html_part)

    eml.attach(emlalt)  # Put multipart/alternative sections as subpart of main message (multipart/related)

    # Build a References header using a hash of the participants
    #  This will allow MTA to group all conversations with the same person in a thread
    #  Note that participants are sorted() and lower()ed so conversations will be grouped regardless of initiator
    eml['References'] = ('<' + hashlib.md5(
        ' '.join(sorted(conv['participants'])).lower().encode('utf-8')).hexdigest() + '@' + fakedomain + '>')

    # Create unique Message-ID by hashing the content (allows for duplicate detection)
    eml['Message-ID'] = ('<' + hashlib.md5(
        (eml['Date'] + eml['Subject'] + str(text_part)).encode('utf-8')).hexdigest() + '@' + fakedomain + '>')

    # Other headers as desired
    eml['X-Converted-By'] = sys.argv[0].lstrip('./')
    eml['X-Converted-Date'] = datetime.datetime.now().strftime('%a, %d %b %Y %T %z')  # useful for dupe removal

    return eml  # Return MIMEMultipart object


def debug_msg(text):
    if args.debug:
        sys.stderr.write('DEBUG: [' + args.inputname.split(os.path.sep)[-1] + '] ' + text + '\n')


def user_msg(text):
    if args.verbose or args.debug:  # debug implies verbose
        sys.stderr.write(text + '\n')


if __name__ == "__main__":
    sys.exit(main())
