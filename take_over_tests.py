import unittest
import os
import pathlib
import shutil
import json
import platform
import take_over


class Cargs():
    pass


class Test_take_over(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwd = os.getcwd()
        self.cwd = pathlib.Path(self.cwd) / 'test_dir'
        self.db_dir = self.cwd / 'db'
        self.files_dir = self.cwd / 'files'
        self.args = Cargs()
        self.FILES_NUM = 5


    def setUp(self):
        temp_cwd = self.cwd / '..'
        if temp_cwd.exists():
            os.chdir(temp_cwd)
            shutil.rmtree(self.cwd, ignore_errors = True)

        setattr(self.args, 'path', str(self.files_dir))
        setattr(self.args, 'target', None)
        setattr(self.args, 'extensions', None)
        setattr(self.args, 'dryrun', False)

        self.db_dir.mkdir(parents = True, exist_ok = True)
        self.files_dir.mkdir(parents = True, exist_ok = True)
        for i in range(self.FILES_NUM):
            file = self.files_dir / 'file_{}.txt'.format(i)
            file.touch()
        os.chdir(self.db_dir)


    def tearDown(self):
        os.chdir(self.cwd / '..')
        shutil.rmtree(self.cwd, ignore_errors = True)


    def get_single_item_db_path(self):
        '''return the path of the item in the database. Only single item is assumed to be in the database'''
        dirs_in_db = [i for i in self.db_dir.iterdir() if i.is_dir()]
        self.assertEqual(len(dirs_in_db), 1)
        return dirs_in_db[0]


    def test_links_created(self):
        '''make sure links are created inplace of original files during takeover'''
        take_over.init(self.args)
        take_over.take_over(self.args)
        # make sure db direcotry exists
        db = self.db_dir / 'takeover_db.json'
        self.assertEqual(db.exists(), True)
        file_count = 0
        for i in self.files_dir.iterdir():
            #make sure all links were created
            self.assertTrue(i.is_symlink())
            #make sure all links point to valid locations
            self.assertTrue(i.resolve().exists())
            file_count += 1
        self.assertEqual(file_count, self.FILES_NUM)


    def test_files_extensions_filter(self):
        '''takeover with extensions filter'''
        for i in range(self.FILES_NUM):
            file = self.files_dir / 'file_{}.py'.format(i)
            file.touch()
            file = self.files_dir / 'file_{}.xml'.format(i)
            file.touch()
            file = self.files_dir / 'file_{}.ini'.format(i)
            file.touch()
        # check extensions with and without preceding '.'
        self.args.extensions = ['xml', '.py']
        take_over.init(self.args)
        take_over.take_over(self.args)
        for i in self.files_dir.iterdir():
            if i.suffix in ['.' + e.lstrip('.') for e in self.args.extensions]:
                self.assertTrue(i.is_symlink())
            else:
                self.assertFalse(i.is_symlink())
        #assume only one dir in database, so lets check the first one
        extensions = ['.' + i.strip('.') for i in self.args.extensions]
        for i in self.get_single_item_db_path().iterdir():
            self.assertIn(i.suffix, extensions, 'file {} should not be in database. Its suffix is not in the extensions list'.format(i))


    def test_symlinks_not_taken(self):
        ''' make sure symlinks are not touched during takeover'''
        test_suffix = '.py'
        resolved_path = '/home/test_bla/file_{}'.format(test_suffix)
        for i in range(self.FILES_NUM):
            file = self.files_dir / 'file_{}{}'.format(test_suffix, i)
            file.symlink_to(resolved_path)
        # check extensions with and without preceding '.'
        take_over.init(self.args)
        take_over.take_over(self.args)
        for i in self.files_dir.iterdir():
            if i.suffix == test_suffix:
                self.assertEqual(str(i.resolve), resolved_path)
            else:
                self.assertNotEqual(str(i.resolve), resolved_path)
        #assume only one dir in database, so lets check the first one
        for i in self.get_single_item_db_path().iterdir():
            self.assertFalse(i.is_symlink())


    def test_single_file_takeover(self):
        ''' takeover only a single file'''
        file_name = 'file_1.txt'
        self.args.path = str(self.files_dir / file_name)
        file = self.files_dir / file_name

        #check file before take over
        self.assertFalse(file.is_symlink())
        #take over
        take_over.init(self.args)
        take_over.take_over(self.args)
        #check file after take over
        self.assertTrue(file.is_symlink())
        self.assertEqual(len(list(self.get_single_item_db_path().iterdir())), 1)


    @unittest.skip('Not implemented yet')
    def test_mixed_dir_and_file_take_over(self):
        ''' takeover both files and folders with mixed and overlapping locations'''
        self.assertTrue(False)


    def test_dryrun(self):
        '''takeover with dryrun flag on - nothing should be writen to disk'''
        # make sure nothing is added to the database
        self.args.dryrun = True
        take_over.init(self.args)
        take_over.take_over(self.args)

        db_items = list(self.db_dir.iterdir())
        db_file_name = 'takeover_db.json'
        f = open('takeover_db.json', 'r')
        db = json.load(f)
        f.close()
        
        self.assertEqual(len(db_items), 1) # only one file
        self.assertEqual(db_items[0].name, db_file_name) # the single file is the database file
        self.assertDictEqual(db, dict()) # the database file is empty

    
    def test_env_var_target(self):
        ''' takeover and set database folder alias with an env var. currently only tested in linux''' 
        env_var_name = 'DB_DIR'
        if platform.system().lower() == 'linux':
            os.environ[env_var_name] = str(self.db_dir)
            self.args.target = '$'+env_var_name
            take_over.init(self.args)
            take_over.take_over(self.args)
            for i in self.files_dir.iterdir():
                #make sure all links were created
                self.assertTrue(i.is_symlink())
                #make sure the link uses the new target (databese directory alias)
                self.assertTrue(os.readlink(str(i)).startswith('$'+env_var_name), 'link {} with target: {} should start with {}'.format(str(i), os.readlink(str(i)), env_var_name))
                #make sure link points to the correct directory
                link_target = os.path.expandvars(os.readlink(str(i)))
                link_target = pathlib.Path(link_target)
                self.assertEqual(str(self.get_single_item_db_path()), str(link_target.parent)) #str(i.resolve().parent))
                #make sure the link points to the correct file
                self.assertTrue(link_target.samefile(self.get_single_item_db_path() / i.name))
        else:
            self.assertFalse(True, 'cuurently test is only implemented for linux')


class Test_set_links(unittest.TestCase):
    @unittest.skip('Not implemented yet')
    def test_exact_name(self):
        '''test that links are created when given the exact item name.
        Existing files should not be replace by links'''
        self.assertTrue(False)


    @unittest.skip('Not implemented yet')
    def test_dryrun(self):
        '''make sure nothing is changed when using the dryrun flag'''
        self.assertTrue(False)


    @unittest.skip('Not implemented yet')
    def test_force(self):
        '''test that all links are created when given the force flag.
        Existing files should be replace by links'''
        self.assertTrue(False)


    @unittest.skip('Not implemented yet')
    def test_partial_name(self):
        '''test that links are created when given a partial item name that exists once in database'''
        self.assertTrue(False)


    @unittest.skip('Not implemented yet')
    def test_duplicate_partial_name(self):
        '''test that links are created when given a partial item name that exists more than once in database'''
        self.assertTrue(False)


class Test_restore_source(unittest.TestCase):
    #TODO
    pass


class Test_remove_source(unittest.TestCase):
    #TODO
    pass


if __name__ == '__main__':
    unittest.main()
