#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Utility functions for determining attachment type"""

import magic  # pip3 install python-magic and python-magic-bin
#import os

import rtfd_decode


def determine_attachment_type(data):
    if rtfd_decode.has_rtfd_magic(data):
        return 'application/x-nsfilewrapper-serialized'  # no official IANA MIME type for nsfilewrapper files
    
    ## DEBUGGING CODE FOR DUMPING ATTACHMENTS ##
    # 
    # filename = 'attachment'  # basename to use for attachment dumps
    # # auto-increment file names to prevent clobbering
    # i = 0
    # while os.path.exists(os.path.join('.', f'{filename}_{i}')):
    #     i += 1
    # with open(os.path.join('.', f'{filename}_{i}'), 'wb') as of:
    #     of.write(data)
    # print('Writing to file', f'{filename}_{i}')
    # 
    ## END DEBUGGING CODE ##
    
    else:
        return magic.from_buffer(data, mime=True)
