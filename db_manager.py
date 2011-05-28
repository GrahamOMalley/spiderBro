#! /usr/bin/env python
import MySQLdb
import logging
import os
import sqlite3
import sys

class db_manager:
    """ A python singleton """
    class __impl:
        """ Implementation of the singleton interface """
        def __init__(self):
            """ Base Constructor"""
            self.log = logging.getLogger('spiderbro')

            self.sb_db_file = ""
            self.CREATE_SB_SCHEMA = False
            self.SB_DB_INITIALIZED = False
            
            self.XBMC_DB_INITIALIZED = False

            self.mysqlparms = {}
            self.USING_MYSQL = False

            self.xbmc_sqlite_file = ""
            self.log.info("DB Manager Initialized")

        # setup internal sqlite db
        def init_sb_db(self, filename):
            """ Create internal sqlite db if it does not already exist"""

            self.sb_db_file = filename
            self.CREATE_SB_SCHEMA = not os.path.exists(self.sb_db_file)

            if self.CREATE_SB_SCHEMA:
                conn = sqlite3.connect(self.sb_db_file)
                self.log.debug('Internal db does not exist, Creating Schema...')
                conn.execute("""create table if not exists shows (series_id INT PRIMARY KEY, showname TEXT unique, finished INT default 0, is_anime INT default 0, high_quality INT default 0)""")
                conn.execute("""create table if not exists urls_seen (showname TEXT, season INT, episode INT, url TEXT)""")
                conn.close()
            else:
                self.log.debug('Database exists, assume schema does, too.')
            
            self.SB_DB_INITIALIZED = True
        
        # get a connection to the internal db
        def sb_db_get_conn(self):
            try:
                if self.SB_DB_INITIALIZED:
                    conn = sqlite3.connect(self.sb_db_file)
                    return conn
                else:
                    self.log.error("Cannot execute, sb_db not initialized")
                    return None
            except Exception, e:
                self.log.error("SQLite Error: %s" % e)

        # perform an insert/update/etc
        def sb_db_set(self, stat):
            try:
                if self.SB_DB_INITIALIZED:
                    con = sqlite3.connect(self.sb_db_file)
                    con.execute(stat)
                    con.commit()
                    con.close()
                    #self.log.debug("\tDATABASE: %s" % stat)
                else:
                    self.log.error("Cannot execute, sb_db not initialized")
            except Exception, e:
                self.log.error("SQLite Error: %s" % e)

        # wrapper for select queries, since theres about 5-6 of them
        def sb_select(self, cols, tname, whereclause=""):
            list = []
            statement = "select " + ", ".join(cols) + " from " + tname + whereclause
            #self.log.debug("\tDATABASE: %s" % statement)
            if self.SB_DB_INITIALIZED:
                conn = sqlite3.connect(self.sb_db_file)
                cur = conn.cursor()
                cur.execute(statement)
                for c in cur:
                    list.append(c)
                cur.close()
                conn.close()
                return list
            else:
                self.log.error("SB DB has not been initialized")

        def get_show_info(self, sname):
            return self.sb_select(["series_id", "finished"], "shows", " where showname = \"%s\"" % sname)

        def get_show_high_quality(self, sname):
            res = self.sb_select(["high_quality"], "shows", " where showname = \"%s\"" % sname)
            is_hq = False
            if res:
                if res[0][0] == 1: is_hq = True
            return is_hq

        def get_ignore_list(self):
            list = self.sb_select(["showname"], "shows", " where finished = 1")
            ret_list = []
            for i in list:
                ret_list.append(i[0])
            return ret_list

        def get_eps_from_self(self, sname):
            return self.sb_select(["season", "episode"], "urls_seen", " where showname = \"%s\"" % sname)

        def mark_show_finished(self, sname):
            self.sb_db_set("""update shows set finished = 1 where showname = \"%s\" """ % sname)

        def add_show(self, sid, sname, finished):
            self.sb_db_set("""insert into shows (series_id, showname, finished) VALUES (\"%s\",\"%s\",\"%s\")""" % (sid,sname,finished))

        def add_to_urls_seen(self, sname, s, e, url):
            self.sb_db_set("""insert into urls_seen (showname,season,episode,url) VALUES (\"%s\",\"%s\",\"%s\",\"%s\")""" % (sname,s,e,url))

        def clear_cache(self, sname):
            self.sb_db_set("""delete from urls_seen where showname=\"%s\"""" % (sname))

        def set_quality(self, sname, qual):
            self.sb_db_set("""update shows set high_quality=%d where showname = \"%s\" """ % (qual, sname))

        def update_series_id(self, sname, id):
            self.sb_db_set("""insert or replace into shows (series_id, showname) values (\"%s\", \"%s\") """ % (id, sname))

        def xbmc_init_sqlite(self, filename):
            if os.path.exists(filename):
                self.xbmc_sqlite_file = filename
                self.USING_MYSQL = False
                self.XBMC_DB_INITIALIZED = True
                self.log.info("Initialized xbmc sqlite db: %s" % self.xbmc_sqlite_file)
            else:
                self.log.error("(FATAL) no xbmc db, exiting...")
                sys.exit()

        def xbmc_init_mysql(self, host, user, passw, schema):
            try:
                # test connection, throw error if not valid
                con = MySQLdb.connect(host, user, passw, schema)
                con.close()
                self.mysqlparms = {"host":host, "user":user, "passw":passw, "schema":schema}
                self.USING_MYSQL = True
                self.XBMC_DB_INITIALIZED = True
                self.log.info("MySql DB initialized on host: %s for user: %s, using schema: %s" % (host, user, schema))
            except:
                self.log.error("(Fatal) Exception connecting to mysql db, db not initialized")
                sys.exit()
        
        def xbmc_select(self, query):
            list = []
            try:
                if self.USING_MYSQL:
                    con = MySQLdb.connect(self.mysqlparms["host"], self.mysqlparms["user"], self.mysqlparms["passw"], self.mysqlparms["schema"])
                else:
                    con = sqlite3.connect(self.xbmc_sqlite_file)
                cur = con.cursor()
                cur.execute(query)
                for c in cur:
                    list.append(c)
                cur.close()
                con.close()
                #self.log.debug("\tDATABASE: %s" % query)
                return list
                    
            except Exception, e:
                    self.log.error("(FATAL) Exception: %s" % e)
                    sys.exit()

        def xbmc_get_eps_for_show(self, sname):
            return self.xbmc_select("""select c12, c13 from episodeview where strTitle = \"%s\" order by c12, c13""" % sname)
        
        def xbmc_get_showlist(self):
            return self.xbmc_select("""select distinct strTitle from episodeview order by strTitle""")

        def xbmc_get_series_id(self, sname):
            return self.xbmc_select("""select distinct c12 from tvshow where c00 = \"%s\"""" %sname)

        def get_id(self):
            """ Test method, return singleton id """
            return id(self)

    # storage for the instance reference
    __instance = None

    def __init__(self):
        """ Create singleton instance """
        # Check whether we already have an instance
        if db_manager.__instance is None:
            # Create and remember instance
            db_manager.__instance = db_manager.__impl()

        # Store instance reference as the only member in the handle
        self.__dict__['_db_manager__instance'] = db_manager.__instance

    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """ Delegate access to implementation """
        return setattr(self.__instance, attr, value)

