#!/usr/bin/env python3
#
#  binmerge
#
#  Takes a cue sheet with multiple binary track files and merges them together,
#  generating a corrected cue sheet in the process.
#
#  Copyright (C) 2024 Chris Putnam
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#
#  Please report any bugs on GitHub: https://github.com/putnam/binmerge
#
#
import argparse, re, os, subprocess, sys, textwrap, traceback
from os.path import exists, join

from psio_sdcardmanager.cue2cu2 import _log_error

VERBOSE = False
VERSION_STRING = "1.0.3"

def print_license():
  print(textwrap.dedent(f"""
    binmerge {VERSION_STRING}
    Copyright (C) 2024 Chris Putnam

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

    Source code available at: https://github.com/putnam/binmerge
  """))

def d(s):
  if VERBOSE:
    print("[DEBUG]\t%s" % s)

def e(s):
  print("[ERROR]\t%s" % s)

def p(s):
  print("[INFO]\t%s" % s)

class Track:
  globalBlocksize = None

  def __init__(self, num, track_type):
    self.num = num
    self.indexes = []
    self.track_type = track_type
    self.sectors = None
    self.file_offset = None

    # All possible blocksize types. You cannot mix types on a disc, so we will use the first one we see and lock it in.
    #
    # AUDIO – Audio/Music (2352)
    # CDG – Karaoke CD+G (2448)
    # MODE1/2048 – CDROM Mode1 Data (cooked)
    # MODE1/2352 – CDROM Mode1 Data (raw)
    # MODE2/2336 – CDROM-XA Mode2 Data
    # MODE2/2352 – CDROM-XA Mode2 Data
    # CDI/2336 – CDI Mode2 Data
    # CDI/2352 – CDI Mode2 Data
    if not Track.globalBlocksize:
      if track_type in ['AUDIO', 'MODE1/2352', 'MODE2/2352', 'CDI/2352']:
        Track.globalBlocksize = 2352
      elif track_type == 'CDG':
        Track.globalBlocksize = 2448
      elif track_type == 'MODE1/2048':
        Track.globalBlocksize = 2048
      elif track_type in ['MODE2/2336', 'CDI/2336']:
        Track.globalBlocksize = 2336
      d("Locked blocksize to %d" % Track.globalBlocksize)

class File:
  def __init__(self, filename):
    self.filename = filename
    self.tracks = []
    self.size = os.path.getsize(filename)

class ZeroBinFilesException(Exception):
  pass

class BinFilesMissingException(Exception):
  pass

def read_cue_file(cue_path):
  files = []
  this_track = None
  this_file = None
  bin_files_missing = False

  f = open(cue_path, 'r')
  for line in f:
    m = re.search(r'FILE "?(.*?)"? BINARY', line)
    if m:
      this_path = os.path.join(os.path.dirname(cue_path), m.group(1))
      if not (os.path.isfile(this_path) or os.access(this_path, os.R_OK)):
        e("Bin file not found or not readable: %s" % this_path)
        bin_files_missing = True
      else:
        this_file = File(this_path)
        files.append(this_file)
      continue

    m = re.search(r'TRACK (\d+) ([^\s]*)', line)
    if m and this_file:
      this_track = Track(int(m.group(1)), m.group(2))
      this_file.tracks.append(this_track)
      continue

    m = re.search(r'INDEX (\d+) (\d+:\d+:\d+)', line)
    if m and this_track:
      this_track.indexes.append({'id': int(m.group(1)), 'stamp': m.group(2), 'file_offset':cuestamp_to_sectors(m.group(2))})
      continue

  if bin_files_missing:
    raise BinFilesMissingException

  if not len(files):
    raise ZeroBinFilesException

  if len(files) == 1:
    # only 1 file, assume splitting, calc sectors of each
    next_item_offset = files[0].size // Track.globalBlocksize
    for t in reversed(files[0].tracks):
      t.sectors = next_item_offset - t.indexes[0]["file_offset"]
      next_item_offset = t.indexes[0]["file_offset"]

  for f in files:
    d("-- File --")
    d("Filename: %s" % f.filename)
    d("Size: %d" % f.size)
    d("Tracks:")

    for t in f.tracks:
      d("  -- Track --")
      d("  Num: %d" % t.num)
      d("  Type: %s" % t.track_type)
      if t.sectors: d("  Sectors: %s" % t.sectors)
      d("  Indexes: %s" % repr(t.indexes))

  return files


def sectors_to_cuestamp(sectors):
  # 75 sectors per second
  minutes = sectors / 4500
  fields = sectors % 4500
  seconds = fields / 75
  fields = sectors % 75
  return '%02d:%02d:%02d' % (minutes, seconds, fields)

def cuestamp_to_sectors(stamp):
  # 75 sectors per second
  m = re.match(r"(\d+):(\d+):(\d+)", stamp)
  minutes = int(m.group(1))
  seconds = int(m.group(2))
  fields = int(m.group(3))
  return fields + (seconds * 75) + (minutes * 60 * 75)

# Generates track filename based on redump naming convention
# (Note: prefix should NEVER contain a path; this function deals only in filenames)
def track_filename(prefix, track_num, track_count):
  # Redump is strangely inconsistent in their datfiles and cuesheets when it
  # comes to track numbers. The naming convention currently seems to be:
  # If there is exactly one track: "" (nothing)
  # If there are less than 10 tracks: "Track 1", "Track 2", etc.
  # If there are more than 10 tracks: "Track 01", "Track 02", etc.
  #
  # It'd be nice if it were consistently %02d!
  #
  # TODO: Migrate everything to pathlib
  if track_count == 1:
    return "%s.bin" % (prefix)
  if track_count > 9:
    return "%s (Track %02d).bin" % (prefix, track_num)
  return "%s (Track %d).bin" % (prefix, track_num)

# Generates a 'merged' cuesheet, that is, one bin file with tracks indexed within.
def gen_merged_cuesheet(basename, files):
  cuesheet = 'FILE "%s.bin" BINARY\n' % basename
  # One sector is (BLOCKSIZE) bytes
  sector_pos = 0
  for f in files:
    for t in f.tracks:
      cuesheet += '  TRACK %02d %s\n' % (t.num, t.track_type)
      for i in t.indexes:
        cuesheet += '    INDEX %02d %s\n' % (i['id'], sectors_to_cuestamp(sector_pos + i['file_offset']))
    sector_pos += f.size / Track.globalBlocksize
  return cuesheet

# Generates a 'split' cuesheet, that is, with one bin file for every track.
def gen_split_cuesheet(basename, merged_file):
  cuesheet = ""
  for t in merged_file.tracks:
    track_fn = track_filename(basename, t.num, len(merged_file.tracks))
    cuesheet += 'FILE "%s" BINARY\n' % track_fn
    cuesheet += '  TRACK %02d %s\n' % (t.num, t.track_type)
    for i in t.indexes:
      sector_pos = i['file_offset'] - t.indexes[0]['file_offset']
      cuesheet += '    INDEX %02d %s\n' % (i['id'], sectors_to_cuestamp(sector_pos))
  return cuesheet

# Merges files together to new file `merged_filename`, in listed order.
def merge_files(merged_filename, files):
  if os.path.exists(merged_filename):
    e('Target merged bin path already exists: %s' % merged_filename)
    return False

  # cat is actually a bit faster, but this is multi-platform and no special-casing
  chunksize = 1024 * 1024
  with open(merged_filename, 'wb') as outfile:
    for f in files:
      with open(f.filename, 'rb') as infile:
        while True:
          chunk = infile.read(chunksize)
          if not chunk:
            break
          outfile.write(chunk)
  return True

# Writes each track in a File to a new file
def split_files(new_basename, merged_file, outdir):
  with open(merged_file.filename, 'rb') as infile:
    # Check all tracks for potential file-clobbering first before writing anything
    for t in merged_file.tracks:
      out_basename = track_filename(new_basename, t.num, len(merged_file.tracks))
      out_path = os.path.join(outdir, out_basename)
      if os.path.exists(out_path):
        e('Target bin path already exists: %s' % out_path)
        return False

    for t in merged_file.tracks:
      chunksize = 1024 * 1024
      out_basename = track_filename(new_basename, t.num, len(merged_file.tracks))
      out_path = os.path.join(outdir, out_basename)
      tracksize = t.sectors * Track.globalBlocksize
      written = 0
      with open(out_path, 'wb') as outfile:
        d('Writing bin file: %s' % out_path)
        while True:
          if chunksize + written > tracksize:
            chunksize = tracksize - written
          chunk = infile.read(chunksize)
          outfile.write(chunk)
          written += chunksize
          if written == tracksize:
            break
  return True

# **********************************************************************************************************


# **********************************************************************************************************
def start_bin_merge(cuefile, game_name, outdir):
	cue_map = read_cue_file(cuefile)
	cuesheet = gen_merged_cuesheet(game_name, cue_map)

	if not exists(outdir):
		_log_error('ERROR', 'Output dir does not exist')
		return False

	new_cue_fn = join(outdir, game_name + '.cue')
	if exists(new_cue_fn):
		_log_error('ERROR', f'Output cue file already exists. Quitting. Path: {new_cue_fn}')
		return False

	if not merge_files(join(outdir, game_name + '.bin'), cue_map):
		return False

	with open(new_cue_fn, 'w', newline='\r\n') as f:
		f.write(cuesheet)

	return True
# **********************************************************************************************************
