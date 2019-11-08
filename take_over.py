#!/usr/bin/env python3

import argparse
import logging
import pathlib
import os
import json
import re, datetime
import shutil
import platform
import unittest



def os_case(in_str):
    sys = platform.system()
    if sys.lower() == 'windows':
        in_str = in_str.lower()
    return in_str


class sources_db():
    '''
    data base file is a json that looks like this:
    {
        database id : {
            "name" : string,
            "database id" : string,
            "original path" : a string representin a path to file or folder,
            "default database path" : a string representin a path to database folder (when creating links they will point to the item under this location),
            "symlink path" : a string representin a path where the symlink is (or should be) located. by default it is equal to "original path"
        },
    }

    example:
    {
        "20191005214789_runtime" : 
        {
            "name" : runtime,
            "database id" : 20191005214789_runtime,
            "original path" : "y:\project\DMT\simengine\",
            "default database path" : "\\192.168.201.1\c$\git\my_repo\takeover\",
            "symlink path" : "y:\project\DMT\simengine\"
        },
        "20191006235648_k" : 
            {
                "name" : k,
                "database id" : 20191006235648_k,
                "original path" : "k:\",
                "default database path" : "%simpath_dev_root%\git\my_repo\takeover\",
                "symlink path" : "\\file-server\drive_k\"
            }
    }
    '''

    def __init__(self, db_path = None):        
        self._db_dict = None
        if db_path is None:
            cwd = pathlib.Path(os.getcwd())
        else:
            cwd = pathlib.Path(db_path)
        self._db_folder_path = cwd
        self._db_file = cwd / 'takeover_db.json'


    def load(self):
        db_loaded = False
        if self._db_dict is not None:
            db_loaded = True
        else:
            if self._db_file.exists():
                try:
                    db_file = None
                    db_file = open(self._db_file, 'r')
                    if db_file:
                        try:
                            self._db_dict = json.load(db_file)
                            if isinstance(self._db_dict, dict):
                                db_loaded = True
                            else:
                                logging.error('database load error - database is corrupted')
                        except:
                            self._db_dict = None
                            logging.error('database load error - invalid database file format')
                    db_file.close()
                except: 
                    logging.fatal('database load error - couldnt open database file')
                finally:
                    pass
            else:
                logging.error('database load error - database file doesnt exist')
        return db_loaded


    def create(self):
        db_created = False
        db_file = None

        if not self._db_file.exists():
            try:
                db_file = open(self._db_file, 'w')
                if self._db_dict is not None:
                    logging.critical('database create conflict - database file doesnt exist but some data is loaded. You should seek professional help')
                else:
                    empty_db_data = {}
                    json.dump(empty_db_data, db_file)
                    db_created = True
                db_file.close()
            except: 
                logging.fatal('database create error - couldnt create database file {}'.format(self._db_file))
            finally:
                pass
        else:
            logging.debug('database create error - database file already exist')

        return db_created


    def create_or_load(self):
        self.create()
        return self.load()


    def find_item(self, item_name):
        db_entry = None
        error_found = False
        if self.load():
            # try to find exact name
            db_entry = self._db_dict.get(item_name)
            if db_entry is None:
                #try to find with partial name
                #create a list of tuples with (sort_name, original_name) eg: [('20191030050124_runtime', 'runtime'),]
                names = [(i.split('_', maxsplit = 1)[1], i) for i in self._db_dict.keys()]
                for i in names:
                    if i[0] == item_name:
                        if db_entry is not None:
                            logging.error('yuuuups, item name {} found more than once. dont kow what to do...'.format(item_name))
                            error_found = True
                            break
                        else:
                            db_entry = self._db_dict[i[1]]
        if error_found:
            item = None
        elif db_entry is None:
            logging.error('iten name {} not found. may be try something else?'.format(item_name))
            item = None
        else:
            item = db_item(db_entry, self._db_folder_path)
        return item


    def all_items(self):
        if self.load():
            for v in self._db_dict.values():
                yield db_item(v, self._db_folder_path)


    def remove_item(self, item_name, dryrun):
        '''remove 'item_name' from the database (storage and json file). 
        'item_name' is a string representing an element in the database'''
        removed_ok = True
        if self.load():
            db_item = self.find_item(item_name)
            if db_item:
                # remove the files
                item_folder = db_item.get_db_path()
                if dryrun:
                    logging.info('item folder  {} removed from database'.format(item_folder))
                else:
                    try:
                        shutil.rmtree(item_folder)
                    except:
                        logging.error('couldnt remove {}'.format(item_folder))
                        removed_ok = False
                # remove from json
                if removed_ok:
                    id = db_item.get_id()
                    if dryrun:
                        logging.info('item {} removed from json database'.format(id))
                    else:
                        self._db_dict.pop(id)
                        removed_ok = self.save()
        return removed_ok


    def save(self):
        db_saved = False
        db_file = None

        try:
            # validate the database object before writing
            json_str = json.dumps(self._db_dict)
            if not isinstance(json_str, str):
                raise
    
            try:
                db_file = open(self._db_file, 'w')
                if db_file:            
                    try:
                        # write the database object to file
                        json.dump(self._db_dict, db_file)
                        db_saved = True
                    except:
                        logging.error('database save error - invalid database format')
                db_file.close()
            except:
                db_file = None
                logging.fatal('database save error - couldnt open database file for writing')
    
        except:
            logging.error('database save validation error - invalid database format')
            logging.debug('database object structure: {}'.format(self._db_dict))

        return db_saved


    def add_dir(self, dir_path, extensions,  database_path_alias = None, dryrun = False):
        added_ok = False
        item = None
        name = pathlib.Path(dir_path).name
        id = str(datetime.datetime.now())
        id = re.sub('[- :.]', '', id)
        id += '_' + name
        
        # load a db if not loaded
        if self.load():
            storage_dir = self._db_folder_path / id
            if not dryrun:
                storage_dir.mkdir()
            else:
                logging.info('dry run - creating folder {} in database'.format(id))

            # copy filtered files to local storage
            new_entry = {
                            "name" : name,
                            "database id" : id,
                            "is file" : pathlib.Path(dir_path).is_file(),
                            "original path" : dir_path,
                            "default database path" : str(self._db_folder_path) if database_path_alias is None else database_path_alias,
                            "symlink path" : dir_path
                        }
            item = db_item(new_entry, self._db_folder_path, extensions)

            if not item.copy_original_files_to_db(dryrun) or len(list(storage_dir.glob('*'))) == 0:
                # if local storage is empty remove it and stop
                if not dryrun:
                    try:
                        shutil.rmtree(str(storage_dir))
                    except:
                        logging.error('nothing was copyed to {} but i could not remove it.'.format(storage_dir))
            else:
                # register in db dict
                if dryrun:
                    logging.info('dry run - adding new entry {} to database'.format(name))
                    added_ok = True
                else:
                    self._db_dict[new_entry['database id']] = new_entry
                    # save db dict
                    if self.save():
                        added_ok = True
                    else:
                        shutil.rmtree(str(storage_dir))

        return added_ok, item


    def add_file(self, file):
        pass


class db_item():
    def __init__(self, db_entry, database_path, suffixes = None):
        self._database_path = pathlib.Path(database_path)
        self._db_entry_data = db_entry
        self._suffixes = suffixes
        if self._suffixes is not None:
            self._suffixes = ['.'+i.lstrip('.') for i in self._suffixes]


    def get_id(self):
        return self._db_entry_data['database id']


    def is_file(self):
        return self._db_entry_data['is file']


    def get_original_location(self):
        return str(self._db_entry_data['original path'])


    def get_symlink_file_location(self):
        return str(self._db_entry_data['symlink path'])


    def get_db_path(self):
        '''return the path of the item files root in the database.'''
        root_path = self._database_path / self._db_entry_data['database id']
        return root_path


    def get_db_path_alias(self):
        '''return the path of the item files root in the database. this is the path to be set in the link'''
        root_path = pathlib.Path(self._db_entry_data['default database path']) / self._db_entry_data['database id']
        return root_path


    #def copy_to(self, dset, dryrun):
    #    # TODO remember to ignore symlinks
    #    logging.debug('db_item.copy() is not implemented yet')
    #    return False


    def _copy_files(self, src_dest_pairs, dryrun):
        '''src_dest_pairs is a list of (source, dest) tupples. both source and dest represent patht to file or directory'''
        copy_ok = True
        for p in src_dest_pairs:
            src = pathlib.Path(p[0])
            dest = pathlib.Path(p[1])
            if dryrun:
                if not dest.exists():
                    logging.info('creating missing directory {}'.format(dest))
                logging.info('copying file {} to {}'.format(src, dest))
            else:
                #create folder
                try:
                    dest.mkdir(parents = True, exist_ok = True)
                    #copy files
                    shutil.copy2(src, dest)
                except:
                    logging.error('copy file {} failed. may be a file with the same directory name already exist'.format(dest))
                    copy_ok = False
        return copy_ok


    def copy_original_files_to_db(self, dryrun):
        original_location = pathlib.Path(self.get_original_location())
        db_item_path = pathlib.Path(self.get_db_path())
        files_list = list()
        if original_location.is_dir():
            for root, dirs, files in os.walk(original_location):
                filtered_files = files
                #take only file matching the suffixs
                if self._suffixes and len(self._suffixes) > 0:
                    filtered_files = [f for f in files if os_case(pathlib.Path(f).suffix) in self._suffixes]
                for f in filtered_files:
                    src = pathlib.Path(root) / f
                    if not src.is_symlink():
                        relative_path = pathlib.Path(root).relative_to(original_location)
                        dest = db_item_path / relative_path
                        files_list.append((src, dest))
        else:
            files_list.append((original_location, db_item_path))
        return self._copy_files(files_list, dryrun)
                

    #def copy_tree_to(self, dryrun):
    #    # TODO remember to ignore symlinks
    #    logging.debug('db_item.copy() is not implemented yet')
    #    return False


    def delete_created_links(self, dryrun):
        '''remove links pointing to the database item's'''
        item_removed = True
        symlink_base_path = pathlib.Path(self.get_db_path())
        db_path_base = pathlib.Path(self.get_db_path_alias())
        if self.is_file():
            dest_file = symlink_base_path
            self._delete_symlink(dest_file, dryrun)
        else:
            for root, dirs, files in os.walk(db_path_base):
                for f in files:
                    db_file = pathlib.Path(root) / f
                    relative_dest = db_file.relative_to(db_path_base)
                    dest_file = symlink_base_path / relative_dest
                    if dest_file.is_symlink(): 
                        if not self._delete_symlink(dest_file, dryrun): 
                            item_removed = False
        return item_removed


    def delete_from_storage(self, dryrun):
        '''remove the database item's files'''
        folder_removed = True
        if dryrun:
            logging.info('removing item directory {} and all of its content'.format(self.get_db_path()))
        else:
            try:
                shutil.rmtree(self.get_db_path())
            except:
                folder_removed = False
                logging.error('couldnt remove folder {} from database'.format(self.get_db_path()))
        return folder_removed


    def _delete_file(self, file_path, dryrun):
        dest_file = pathlib.Path(file_path)
        link_removed = True
        if dest_file.exists() and not dest_file.is_dir():
            if dryrun:
                logging.info('dry run - removing file {}'.format(dest_file))
            else:
                try:
                    # only remove symlink
                    dest_file.unlink()
                except:
                    logging.error('couldnt remove symlink {}'.format(dest_file))
                    link_removed = False
        return link_removed


    def delete_original_files(self, dryrun = False):
        item_removed = True
        symlink_path = pathlib.Path(self.get_symlink_file_location())
        if symlink_path.exists() or symlink_path.is_symlink():
            if symlink_path.is_dir():
                for root, dirs, files in os.walk(symlink_path):
                    filtered_files = files
                    if self._suffixes is not None:
                        filtered_files = [i for i in files if os_case(pathlib.Path(i).suffix) in self._suffixes]
                    for f in filtered_files:
                        file_path = pathlib.Path(root) / f
                        if not file_path.is_symlink():
                            if not self._delete_file(file_path, dryrun): 
                                item_removed = False
            elif not symlink_path.is_symlink():
                if not self._delete_file(symlink_path, dryrun): 
                    item_removed = False
               
        return item_removed

    
    def copy_to_original_location(self, db_path_alias = None, force = None, dryrun = None):
        original_location = pathlib.Path(self.get_original_location())
        db_item_path = pathlib.Path(self.get_db_path_alias())
        files_list = list()
        if original_location.is_dir():
            for root, dirs, files in os.walk(db_item_path):
                filtered_files = files
                #take only file matching the suffixs
                if self._suffixes and len(self._suffixes) > 0:
                    filtered_files = [f for f in files if os_case(pathlib.Path(f).suffix) in self._suffixes]
                for f in filtered_files:
                    src = pathlib.Path(root) / f
                    if not src.is_symlink():
                        relative_path = src.relative_to(db_item_path)
                        dest = original_location / relative_path
                        if dest.exists():
                            if force:
                                dest.unlink()
                                files_list.append((src, dest.parent))
                            else:
                                logging.info('file {} already exist in destination. it will not be retored. use --force to replace the existing file'.format(dest))
                        else:
                            files_list.append((src, dest))
        else:
            if len(db_item_path.iterdir()) > 1:
                logging.error('weird shit. item {} took over one file but there are more in database'.format(str(db_item_path)))
            else:
                db_item_file = db_item_path.iterdir()[0] #assuming only one file in the directory
                files_list.append((db_item_file, original_location))
        return self._copy_files(files_list, dryrun)


    def create_all_links(self, db_path_alias = None, force = False, dryrun = False):
        '''db_path_alias is an alternative path to the database folder. eg: "\\192.168.50.1\git\database" instead of "c:\git\database" '''
        db_path = self.get_db_path()
        db_path_for_link = pathlib.Path(self.get_db_path_alias())
        symlink_root_dir = pathlib.Path(self.get_symlink_file_location())
        # if working with file, use its parent dir
        if self.is_file():
            symlink_root_dir = symlink_root_dir.parent
        if db_path_alias:
            db_path_for_link = pathlib.Path(db_path_alias) / self._db_entry_data['database id']
        for root, dirs, files in os.walk(db_path):
            for file in files:
                relative_file_path = pathlib.Path(root).relative_to(db_path)
                symlink_file_location = symlink_root_dir / relative_file_path / file
                db_file_location = db_path_for_link / relative_file_path / file
                self._create_link(symlink_file_location, db_file_location, force, dryrun)


    def _create_link(self, symlink_file_location, db_file_location, force = False, dryrun = False):
        ''' 
        symlink_file_location - pathlike object, representing location to put the symbolic link
        db_file_location - pathlike object, representing location where the actual file is
        The fuction creates a link in 'symlink_file_location' pointing to 'db_file_location'.
        If 'symlink_file_location' file already exists, return False.
        If 'symlink_file_location' file already exists and force is True, 
        'symlink_file_location' will be deleted and a new link will be created
        Return True on success, False on failure'''
        link_created = False
        ready_to_link = True
        symlink_file = pathlib.Path(symlink_file_location)
        db_file = pathlib.Path(db_file_location)
        # check if file exists with the same name as the required link
        if symlink_file.exists() or symlink_file.is_symlink():
            if symlink_file.is_dir():
                logging.error('link creation from {} to {} failed. both must not be directories'.format(db_file, symlink_file))
                ready_to_link = False
            elif symlink_file.is_file():
                # remove the existing file if requested
                if not force:
                    logging.error('link creation in {} failed, a file with the same name already exist. use "force" to remove the existing file'.format(symlink_file))
                    ready_to_link = False
                else:
                    symlink_file.unlink()
        if ready_to_link:
            if dryrun:
                if not symlink_file.parent.exists(): 
                    logging.info('dry run - creating missing directories tree: {}'.format(symlink_file.parent))
                logging.info('dry run - creating a link in {} pointinh to {}'.format(symlink_file, db_file))
            else:
                #create directories tree if needed
                if not symlink_file.parent.exists(): 
                    symlink_file.parent.mkdir(parents = True, exist_ok = True)
                symlink_file.symlink_to(db_file)
                link_created = True
        return link_created


# sub-command functions
def take_over(args):
    if args.extensions is not None:
        args.extensions = [os_case(e) for e in args.extensions]
    dest_path = pathlib.Path(args.path)
    if dest_path.exists() and not dest_path.is_symlink():
        db = sources_db()
        added, db_item = db.add_dir(args.path, args.extensions, args.target, args.dryrun)
        if added:
            # remove original file
            db_item.delete_original_files(args.dryrun)
            # link from required dest to local storage
            db_item.create_all_links(None, True, args.dryrun)
    else:  
        logging.error('couldnt take over {}. Path doesnt exist, or it is a symbolik link'.format(dest_path))        
        

def restore_source(args):
    db = sources_db()
    if args.name is not None:
        db_item = db.find_item(args.name)
        if db_item:
            db_item.copy_to_original_location(None, args.force, args.dryrun)        
            if args.remove:
                db.remove_item(args.name, args.dryrun)
    else:
        # using list instead of iterator because removing items from the directory changes the list during iteration
        for i in list(db.all_items()): 
            i.copy_to_original_location(None, args.force, args.dryrun)
            if args.remove:
                db.remove_item(i.get_id(), args.dryrun)


def init(args):
    db = sources_db()
    db.create()


def set_links(args):
    db = sources_db()
    if args.name is not None:
        item = db.find_item(args.name)
        if item:
            # link from required dest to local storage
            item.create_all_links(None, args.force, args.dryrun)        
            
    else:
        for item in db.all_items():
            item.create_all_links(None, args.force, args.dryrun)


def remove_source(args):
    db = sources_db()
    if args.name is not None:
        db_item = db.find_item(args.name)
        if db_item:
            if db_item.delete_from_storage(args.dryrun):
                db.remove_item(args.name, args.dryrun)


def list_sources(args):
    cellsize = 20
    db = sources_db()

    for i in db.all_items():
        id = i.get_id()
        name = id.split('_')[1]
        if args.veryverbose:
            print('not supported yet')
        elif args.verbose:
            print(name + ' '*(cellsize - len(name)+2) + id)
        else:
            print(i.get_id().split('_')[1])


def update(args):
    #TODO:
    logging.critical('Not implement yet')


def init(args):
    db = sources_db()
    db.create()


def handle_args():
    # create the top-level parser
    msg = '''This program is used to take over files (usually config files), 
    manage them in a single location and replace original files with links'''
    parser = argparse.ArgumentParser(description = msg, )
    parser.add_argument('--version', action='version', version = '0.1b')
    parser.set_defaults(func = lambda args : parser.print_help())
    subparsers = parser.add_subparsers(title = 'Allowed commands', help = 'Try "take_over COMMAND -h"')
    
    # create the parser for the "init" command
    parser_init = subparsers.add_parser('init', description = 'initialize a database in the current directory')
    parser_init.set_defaults(func = init)

    # create the parser for the "takeover" command
    parser_takeover = subparsers.add_parser('takeover', description = 'Takeover a file or folder, and store them localy as a source.')
    parser_takeover.add_argument('path', help = 'Path to file or folder to takeover')
    parser_takeover.add_argument('-t', '--target', default = None, help = 'A default path for the link to point to. If not set, original (local) path will be used')
    parser_takeover.add_argument('-e', '--extensions', nargs = '+', default = None, help = 'A list of file extensions to take over. If not set all files are taken ove eg: -t xml ini')
    parser_takeover.add_argument('-d', '--dryrun', action = 'store_true', default = False, help = 'Actions will only be printed out. There will be no effect on the file system')
    parser_takeover.set_defaults(func = take_over)
    
    # create the parser for the "set_links" command
    parser_set_links = subparsers.add_parser('set_links', description = 'Set links for the managed sources')
    parser_set_links.add_argument('-n', '--name', default = None, help = 'Name of database source to use (see "list" command). If not set, all sources will be used')
    parser_set_links.add_argument('-t', '--target', default = None, help = 'Path for the link to point to. If not set, the default path will be used')
    #TODO: parser_set_links.add_argument('-l', '--link-path', default = None, help = 'Base path for where to put the links. If not set, the default (original path) path will be used')
    parser_set_links.add_argument('-d', '--dryrun', action = 'store_true', default = False, help = 'Actions will only be printed out. There will be no effect on the file system')
    parser_set_links.add_argument('-f', '--force', action = 'store_true', default = False, help = 'New links will remove existing file or links')
    parser_set_links.set_defaults(func = set_links)

    # create the parser for the "restore" command
    parser_restore = subparsers.add_parser('restore_source', description = 'Remove created links, and copy the source back to its original path')
    parser_restore.add_argument('-n', '--name', default = None, help = 'Name of source to use (see "list" command). If not set, all sources will be used')
    parser_restore.add_argument('-r', '--remove', action = 'store_true', default = False, help = 'If set, the source will be forgotten. It will be removed from the database, and will no longer be managed')
    parser_restore.add_argument('-d', '--dryrun', action = 'store_true', default = False, help = 'Actions will only be printed out. There will be no effect on the file system')
    parser_restore.add_argument('-f', '--force', action = 'store_true', default = False, help = 'Restored files will remove existing file or links')
    parser_restore.set_defaults(func = restore_source)

    # create the parser for the "remove" command - remove entry from database
    parser_remove = subparsers.add_parser('remove_source', description = 'Remove a source from database')
    parser_remove.add_argument('-n', '--name', required = True, default = None, help = 'Name of source to use (see "list" command).')
    parser_remove.add_argument('-d', '--dryrun', action = 'store_true', default = False, help = 'Actions will only be printed out. There will be no effect on the file system')
    parser_remove.set_defaults(func = remove_source)

    # create the parser for the "update" command - update database entry with newly created files
    parser_update = subparsers.add_parser('update', description = 'update database items')
    parser_update.add_argument('-n', '--name', required = True, default = None, help = 'Name of source to use (see "list" command).')
    parser_update.add_argument('-e', '--extensions', nargs = '+', default = None, help = 'A list of file extensions to to consider when updating. If not set all files are considered eg: -t xml ini')
    parser_update.add_argument('-d', '--dryrun', action = 'store_true', default = False, help = 'Actions will only be printed out. There will be no effect on the file system')
    parser_update.set_defaults(func = update)

    # create the parser for the "list" command
    parser_list = subparsers.add_parser('list', description = 'List the managed files and folders')
    parser_list.add_argument('-v', '--verbose', action = 'store_true', default = False, help = 'print more details')
    parser_list.add_argument('--very_verbose', action = 'store_true', default = False, help = 'print even more details')
    parser_list.set_defaults(func = list_sources)

    #if system.platform != "win32":
        #logging.debug('A linux machine detected. This is not yet supported')
        #parser.error('Currently only windows is supported')
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)    
    handle_args() 
    

