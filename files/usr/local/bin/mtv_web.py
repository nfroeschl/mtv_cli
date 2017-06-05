#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# Mediathekview auf der Kommandozeile (Webinterface)
#
# Einfaches Webinterface auf Basis von Bottle
#
# Author: Bernhard Bablok
# License: GPL3
#
# Website: https://github.com/bablokb/mtv_cli
#
# ---------------------------------------------------------------------------

# --- System-Imports   ------------------------------------------------------

import os, json
from argparse import ArgumentParser
from multiprocessing import Process
import configparser

import bottle
from bottle import route

# --- eigene Imports   ------------------------------------------------------

import mtv_cli
from mtv_const    import *
from mtv_filmdb   import FilmDB as FilmDB
from mtv_msg      import Msg as Msg
from mtv_download import *

# --- Hilfsklasse für Optionen   --------------------------------------------

class Options(object):
  pass

# --- Webroot dynamisch bestimmen   -----------------------------------------

def get_webroot(pgm):
  pgm_dir = os.path.dirname(os.path.realpath(pgm))
  return os.path.realpath(os.path.join(pgm_dir,"..","lib","mtv_cli","web"))

def get_webpath(path):
  return os.path.join(WEB_ROOT,path)

# --- Statische Routen   ----------------------------------------------------

@route('/css/<filepath:path>')
def css_pages(filepath):
    print(filepath)
    return bottle.static_file(filepath, root=get_webpath('css'))
  
@route('/js/<filepath:path>')
def css_pages(filepath):
    return bottle.static_file(filepath, root=get_webpath('js'))

# --- Hauptseite   ----------------------------------------------------------

@route('/')
def main_page():
  tpl = bottle.SimpleTemplate(name="index.html",lookup=[WEB_ROOT])
  return tpl.render()

# --- Status   --------------------------------------------------------------

@route('/status')
def status():
  rows =  options.filmDB.read_status(['_akt','_anzahl'])
  result = {}
  for row in rows:
    key    = row['key']
    if key == "_akt":
      tstamp = row['Zeit'].strftime("%d.%m.%Y %H:%M:%S")
      result[key] = tstamp
    else:
      text   = row['text']
      result[key] = text
  Msg.msg("DEBUG","Status: " + str(result))
  bottle.response.content_type = 'application/json'
  return json.dumps(result)

# --- Suche   ---------------------------------------------------------------

@route('/suche',method='POST')
def suche():
  # Auslesen Request-Parameter
  such_args = []
  token = bottle.request.forms.get('global')
  if token:
    such_args.append(token)
  for arg in ['sender','thema','datum','titel','bechreibung']:
    token = bottle.request.forms.get(arg)
    if token:
      such_args.append(arg+':'+token)
  Msg.msg("DEBUG","Suchbegriffe: " + str(such_args))

  # Film-DB abfragen
  statement = options.filmDB.get_query(such_args)
  rows = options.filmDB.execute_query(statement)

  # Ergebnis aufbereiten
  result = []
  for row in rows:
    item = {}
    item['DATUM'] = row['DATUM'].strftime("%d.%m.%y")
    for key in ['SENDER','THEMA','TITEL','DAUER']:
      item[key] = row[key]
    result.append(item)

  Msg.msg("DEBUG","Anzahl Treffer: %d" % len(result))
  bottle.response.content_type = 'application/json'
  return json.dumps(result)

# --- Vormerken   -----------------------------------------------------------

@route('/vormerken',method='POST')
def vormerken():
  # Auslesen Request-Parameter
  ids = bottle.request.forms.get('ids').split(" ")
  dates = bottle.request.forms.get('dates').split(" ")
  Msg.msg("DEBUG","IDs: " + str(ids))

  inserts = []
  i = 0
  for id in ids:
    inserts.append((id,dates[i],'V'))
    i += 1
  changes = options.filmDB.save_downloads(inserts)

  bottle.response.content_type = 'application/json'
  return "{'msg':
    '%d von %d Filme vorgemerkt für den Download' % (changes,len(ids))}"

# --- Aktualisieren   -------------------------------------------------------

@route('/aktualisieren',method='GET')
def aktualisieren():
  p = Process(target=mtv_cli.do_update,args=(options,))
  p.start()
  bottle.response.content_type = 'application/json'
  return "{'msg': 'Aktualisierung angestoßen'}"

# --- Download   ------------------------------------------------------------

@route('/download',method='GET')
def download():
  p = Process(target=download_filme,args=(options,))
  p.start()
  bottle.response.content_type = 'application/json'
  return "{'msg': 'Aktualisierung angestoßen'}"

# --- Kommandozeilenparser   ------------------------------------------------

def get_parser():
  parser = ArgumentParser(add_help=False,
    description='Simpler Webserver für Mediathekview auf der Kommandozeile')

  parser.add_argument('-d', '--db', metavar='Datei',
    dest='dbfile', default=FILME_SQLITE,
    help='Datenbankdatei')
  parser.add_argument('-l', '--level', metavar='Log-Level',
    dest='level', default=None,
    help='Meldungen ab angegebenen Level ausgeben')
  parser.add_argument('-h', '--hilfe', action='help',
    help='Diese Hilfe ausgeben')
  return parser

# --- Hauptprogramm   -------------------------------------------------------

if __name__ == '__main__':
  # Konfiguration lesen
  config_parser = configparser.RawConfigParser()
  config_parser.read('/etc/mtv_cli.conf')
  config = mtv_cli.get_config(config_parser)

  # Optionen lesen
  opt_parser = get_parser()
  options = opt_parser.parse_args(namespace=Options)

  # Message-Klasse konfigurieren
  if options.level:
    Msg.level = options.level
  else:
    Msg.level = config["MSG_LEVEL"]

  if not os.path.isfile(options.dbfile):
    Msg.msg("ERROR","Datenbank %s existiert nicht!" % options.dbfile)
    sys.exit(3)

  # Globale Objekte anlegen
  options.config = config
  options.filmDB = FilmDB(options)

  # Server starten
  WEB_ROOT = get_webroot(__file__)
  Msg.msg("DEBUG","Web-Root Verzeichnis: %s" % WEB_ROOT)
  if Msg.level == "DEBUG":
    Msg.msg("DEBUG","Starte den Webserver im Debug-Modus")
    bottle.run(host='localhost', port=2626, debug=True,reloader=True)
  else:
    bottle.run(host='localhost', port=2626, debug=False,reloader=False)