# Takeover
This program is used to take over files (usually config files), manage them in a single location and replace original files with links

## Requirements
- python 

Tested on python 3.7.4 may work on older versions as well
Tested on Linux. should work in Windows as well

## Usage
Execute:
> python take_over.py COMMAND

To get help run :
> python take_over.py -h 

To run all tests run:
> python take_over_tests.py -v

Exaples:
1. Take over all files in a directory. Replace its original conent with symlinks a local database:
    > python  take_over.py take_over ~/path/to/some/dir
2. Take over all xml and ini files in a directory
    > python  take_over.py take_over ~/path/to/some/dir -e xml .ini
3. Take over all xml and ini files in a directory, but only print what will happen without writing anything to disk
    > python  take_over.py take_over ~/path/to/some/dir -e xml .ini --dryrun
4. List all available sources in the database, with verbose output
    > python take_over.py list -v
5. Restore directory from database to its original location and remove stored files
    > python  take_over.py restore SOURCE --remove
6. Set links for all items in the database. Replace existing files with new links to the files in the database
    > python take_over.py set-links --force