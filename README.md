# iChat to EML Converter

by Kadin2048 <kadin@sdf.org>

A conversion program to convert old Apple iChat logs into RFC-compliant
email message files (MIME text files), suitable for importation into a
mail program or for archival storage.

Tested using Python 3.9 on Mac OS X.

Acknowledgements:
* `python-typedstream`: Created by ["dgelessus" on Github](https://github.com/dgelessus/python-typedstream) (MIT License)
* `ccl-bplist` Created by [Alex Caithness of CCL Solutions Group Ltd.](https://github.com/cclgroupltd/ccl-bplist) (MIT-style License)

Except as marked, all other code is Copyright 2021 by Kadin2048 and made available under the 
GNU General Public License (GPL) version 3 or later.

## Usage (Direct)

```
usage: ichat_to_eml.py [-h] [-v] [--debug] [--no-background]
                       [--attach-original]
                       inputname [outputdir]

Convert iChat logs to MIME text (.eml) files.

positional arguments:
  inputname          Input file to process
  outputdir          Output directory to write EML files to (uses stdout if
                     not given)

optional arguments:
  -h, --help         show this help message and exit
  -v, --verbose      Increase stderr output verbosity
  --debug            Enable debugging mode (implies --verbose)
  --no-background    Strips background color from message text
  --attach-original  Attach original log files to output as application/octet-
                     stream
```

## Usage (Wrapper Script)

To process multiple iChat logs at once, a simple wrapper script can be used
(assuming your system has a Bash-type shell):

### Process old .chat files only

    for f in ~/Documents/iChats/*.chat;
    do ./ichat_to_eml.py --no-background --attach-original "$f" destdir/ ;
    done

### Process newer .ichat files only

    for f in ~/Documents/iChats/*.ichat;
    do ./ichat_to_eml.py --no-background --attach-original "$f" destdir/ ;
    done

### Process everything

    for f in ~/Documents/iChats/*chat;
    do ./ichat_to_eml.py --no-background --attach-original "$f" destdir/ ;
    done

## Known Issues / Warnings

### AttributeError Debug Warning

When running the .chat parser/converter in Debug mode, you may see a large number of messages similar to
`AttributeError encountered while parsing message contents; skipping message`.
This is normal behavior; it just means that the parser has encountered an object in the file
at the same level that `InstantMessage` objects are normally found at, which lacks the normal object
structure of an actual InstantMessage.  Due to the way the parser works (it inspects every object),
this is expected and does not mean that actual chat messages were not found.

You should probably spot-check files that produce many of these messages just for safety, though.

### Performance

It's pretty slow.  Luckily, you should only have to run it once.

## Conversation Data Model

This is pseudocode, not actual Python:

    conversation = {}
      conversation['participants'] = []
        list of unique message['from'] values
      conversation['userids'] = []
        list of account names or phone numbers
      conversation['names'] = []
        list of human readable names
      conversation['startobj'] = base_obj['metadata']['StartTime']
      conversation['endobj'] = base_obj['metadata']['EndTime']
      conversation['protocol'] = base_obj['metadata']['Service']
      conversation['messages'] = []
        message = {}
          message['guid']
          message['from']
          message['fromguid']
          message['dateobj']
          message['text']
          message['textfont']
          message['textsize']
          message['attachment']
            attachment = {}
