# exif-headliner
Update default image metadata based on directory structure using exif-tool

Purpose

exif-headliner is a python application custom designed to walk through a directory and update IPTC core metadata.
Background is that I want to use the Adobe Bridge batch rename function which requires that a headline will exist.
Legacy photos did not alway have a headline so one does need to be created.

Funtionality

Expectation is that a directory name consists of a valid year or date (e.g. 2013 or 2013-02-15).
If the directory name contains text as well as the year or date, then the text is presumed to be the headline.
The script utilizes an opensource application called Exiftool which reads and writes from the files and/or sidecar xmp files.
The Exiftool only works with media files, so the python script is limited to those files. 
If a media file already contains IPTC Core metadata, then that will remain unchanged. 
If on the other hand any metadata contained in the metadata_template file is empty, then the script will update that metadata.

Dependencies

Exiftool must be installed.  On MacOS, you can run homebrew as follows - 

