#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Helper functions for decoding "rtfd" serialized file structures

    See also https://gist.github.com/bortels/1422256
    and http://blog.simonrodriguez.fr/articles/2015/09/nsfilewrapper_serializedrepresentation.html
"""

# rtfd header structure:
#  Offset 0x0 to 0x4  (4 bytes) = 'rtfd'
#  Offset 0x4 to 0x8  (4 bytes) = null padding?
#  Offset 0x8 to 0xC  (4 bytes) = version as unsigned long int?
#  Offset 0xC to 0x10 (4 bytes) = number of parts/chunks in the file

import sys
import os
import struct


# DEBUG MODE - READ BEFORE ENABLING
#  Debug mode will cause more verbose console output AND will cause
#  "raw" and "trimmed" dump files to be written to current working dir
debug = False


def has_rtfd_magic(data):
    if not isinstance(data, bytes):  # data must be a 'bytes' object
        raise TypeError('Input data must be of type "bytes"')
    if data[:4] == b'rtfd':
        return True
    else:
        return False


def decode_rtfd(data):
    parts = []
    
    if not has_rtfd_magic(data):
        raise TypeError('Input data does not begin with "rtfd" header')
    padding = struct.unpack('<i',data[4:8])[0]  # all 0x00 (nulls)
    version = struct.unpack('<i',data[8:12])[0]  # always == 3?
    numberparts = struct.unpack('<i',data[12:16])[0]
    
    # Each part name begins with 32-bit length, then the bytes
    #  Repeats for as many parts as there are
    offset = 16  # start position in bytes
    for i in range(numberparts):
        p = {}
        partnamelen = struct.unpack('<l',data[offset:(offset+4)])[0]
        offset += 4
        fmt = str(partnamelen)+'c'  # 2c, 23c, 56c, etc.
        nametuple = struct.unpack(fmt, data[offset:offset+partnamelen])
        offset += partnamelen
        name = b''.join(nametuple)
        p['index'] = i
        p['name'] = name
        parts.append(p)
        i += 1
    
    # Then there is a 4-byte length field for each file
    #  Do not sort/reorder the parts between last loop and this one!
    for p in parts:
        size = struct.unpack('<l',data[offset:offset+4])[0]
        offset += 4
        p['size'] = size
    
    # Then the actual part content
    for p in parts:
        fmt = str(p['size']) + 'c'
        contenttuple = struct.unpack(fmt, data[offset:offset+p['size']])
        offset += p['size']
        p['contentbytes'] = b''.join(contenttuple)
    
    # Inside each part's content section there are also headers and padding
    for p in parts:
        contentbytes = p['contentbytes']
        content_header = struct.unpack('<l',contentbytes[0:4])[0]  # always 1 ?
        content_size = struct.unpack('<l',contentbytes[4:8])[0]
        content_start = 8  # this seems to be the default for small parts
        # HOWEVER... for some reason...
        if content_size == -2147483648:
            # if the second 4 bytes are -2147483648, then 8-12 are size
            content_size = struct.unpack('<l',contentbytes[8:12])[0]
            # and the next 4 bytes (12-16) are the amount of null padding
            # null padding + 16 bytes (header length) is starting offset
            content_start = struct.unpack('<l',contentbytes[12:16])[0] + 16
        fmt = str(content_size)+'c'
        filetuple = struct.unpack(fmt, contentbytes[content_start:])
        p['filebytes'] = b''.join(filetuple)
    
    # Construct a single output object to return
    outdict = {}
    
    # Determine file name from specially-named parts, if they exist
    for p in parts:
        if p['name'] == b'__@UTF8PreferredName@__':
            outdict['filename'] = p['filebytes'].decode('utf-8')
            break
        elif p['name'] == b'__@PreferredName@__':
            outdict['filename'] = p['filebytes'].decode('ascii')
            break
    
    # Get content from the '..' part if it exists, else use '.' part
    #  No idea what these names mean; might be safer to use larger one?
    for p in parts:
        if p['name'] == b'..':
            outdict['data'] = p['filebytes']
            break
        elif p['name'] == b'.':
            outdict['data'] = p['filebytes']
            break
    
    # DEBUG & DUMP 
    if debug:
        for p in parts:
            print('Index:', p['index'])
            print('Part name:', p['name'])
            print('Size:', p['size'])
            print('Raw bytes:\n', p['contentbytes'])
            print('Trimmed bytes:\n', p['filebytes'])
            print()
            index = p['index']
            with open(f'rtfd_raw_part{index}.bin', 'wb') as fo:
                fo.write(p['contentbytes'])
                with open(f'rtfd_trim_part{index}.bin', 'wb') as fo:
                    fo.write(p['filebytes'])
    
    # Return the outdict object with {'filename': string, 'data': bytes}
    return outdict


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('Unexpected number of arguments; input file and output dir required.\n')
    sys.stderr.write('Attempting to decode: ' + sys.argv[1] + '\n')
    sys.stderr.write('Writing output to: ' + sys.argv[2] + '\n')
    with open(sys.argv[1],'rb') as fh:
        data = fh.read()
        if has_rtfd_magic(data) == True:
            outdict = decode_rtfd(data)
            with open(os.path.join(sys.argv[2], outdict['filename']),'wb') as fo:
                fo.write(outdict['data'])
    sys.exit(0)
