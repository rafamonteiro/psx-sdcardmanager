import concurrent
from os import listdir, scandir, mkdir, remove, rename
from os.path import exists, join, basename, splitext
from shutil import move, rmtree

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox
from pathlib2 import Path

from psio_sdcardmanager.binmerge import start_bin_merge, read_cue_file
from psio_sdcardmanager.cue2cu2 import start_cue2cu2
from psio_sdcardmanager.db import select, extract_game_cover_blob
from psio_sdcardmanager.game_files import Cuesheet, Binfile, Game
from psio_sdcardmanager.serial_finder import get_serial


class GameHandler(QObject):
    def __init__(self):
        super().__init__()
        self.MAX_GAME_NAME_LENGTH = 56
        self.REGION_CODES = ['DTLS_', 'SCES_', 'SLES_', 'SLED_', 'SCED_', 'SCUS_', 'SLUS_', 'SLPS_', 'SCAJ_', 'SLKA_',
                             'SLPM_',
                             'SCPS_', 'SCPM_', 'PCPX_', 'PAPX_', 'PTPX_', 'LSP0_', 'LSP1_', 'LSP2_', 'LSP9_', 'SIPS_',
                             'ESPM_',
                             'SCZS_', 'SPUS_', 'PBPX_', 'LSP_']

    def process_games(self, merge_bin_files, force_cu2, auto_rename, validate_game_name, add_cover_art):
        for game in game_list:
            # _print_game_details(game)

            game_id = game.id
            game_name = game.cue_sheet.game_name

            game_full_path = join(game.directory_path, game.directory_name)
            cue_full_path = game.cue_sheet.file_path

            #  #  label_progress.configure(text=f'{PROGRESS_STATUS} Processing - {game_name}')

            print(f'GAME_ID: {game_id}')
            print(f'GAME_NAME: {game_name}')
            print(f'GAME_PATH: {game_full_path}')
            print(f'CUE_PATH: {cue_full_path}')

            if merge_bin_files and len(game.cue_sheet.bin_files) > 1:
                print('MERGING BIN FILES...')
                #     #  label_progress.configure(text=f'{PROGRESS_STATUS} Merging bin files - {game_name}')
                self._merge_bin_files(game, game_name, game_full_path, cue_full_path)

            if force_cu2 and not game.cu2_present:
                print('GENERATING CU2...')
                #    #  label_progress.configure(text=f'{PROGRESS_STATUS} Generating cu2 file - {game_name}')
                start_cue2cu2(cue_full_path, f'{game_name}.bin')

            if auto_rename:
                print('RENAMING THE GAME FILES...')
                #    #  label_progress.configure(text=f'{PROGRESS_STATUS} Renaming - {game_name}')
                redump_game_name = self._game_name_validator(self.get_redump_name(game_id))
                self._rename_game(game_full_path, game_name, redump_game_name)

            if validate_game_name and not auto_rename:
                if len(game_name) > self.MAX_GAME_NAME_LENGTH or '.' in game_name:
                    print('VALIDATING THE GAME NAME...')
                    #      #  label_progress.configure(text=f'{PROGRESS_STATUS} Validating name - {game_name}')
                    new_game_name = self._game_name_validator(game)
                    print(f'new_game_name: {new_game_name}')
                    if new_game_name != game_name:
                        self._rename_game(game_full_path, game_name, new_game_name)

            if add_cover_art:
                print('ADDING THE GAME COVER ART...')
                #  #  label_progress.configure(text=f'{PROGRESS_STATUS} Adding cover art - {game_name}')
                self._copy_game_cover(game_full_path, game_id, game_name)

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to merge multi-bin files
    def _merge_bin_files(self, game, game_name, game_full_path, cue_full_path):
        # Create a temp directory to store the merged bin file
        temp_game_dir = join(game_full_path, 'temp_dir')
        if not exists(temp_game_dir):
            try:
                mkdir(temp_game_dir)
            except OSError as error:
                pass
        if exists(temp_game_dir):
            #  #  label_progress.configure(text=f'{PROGRESS_STATUS} Merging bin files')
            start_bin_merge(cue_full_path, game_name, temp_game_dir)

            # If the bin files have been merged and the new cue file has been generated
            temp_bin_path = join(temp_game_dir, f'{game_name}.bin')
            temp_cue_path = join(temp_game_dir, f'{game_name}.cue')
            if exists(temp_bin_path) and exists(temp_cue_path):
                # Delete the original cue_sheet and bin files
                remove(cue_full_path)
                for orginal_bin_file in game.cue_sheet.bin_files:
                    remove(orginal_bin_file.file_path)

                # Move the newly merged bin_file and cue_sheet back into the game directory
                move(temp_bin_path, join(game_full_path, f'{game_name}.bin'))
                move(temp_cue_path, join(game_full_path, f'{game_name}.cue'))

            rmtree(temp_game_dir)

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to rename a game and all associated files
    def _rename_game(self, game_full_path, game_name, new_game_name):
        original_bin_file = join(game_full_path, f'{game_name}.bin')
        original_cue_file = join(game_full_path, f'{game_name}.cue')
        original_cu2_file = join(game_full_path, f'{game_name}.cu2')

        # Rename bin file
        if exists(original_bin_file):
            rename(original_bin_file, join(game_full_path, f'{new_game_name}.bin'))

        # Rename cue file and edit the cue file contents to match
        if exists(original_cue_file):
            # Edit cue file content
            cue_path = Path(original_cue_file)
            cue_text = cue_path.read_text()
            cue_text = cue_text.replace(game_name, new_game_name)
            cue_path.write_text(cue_text)
            rename(original_cue_file, join(game_full_path, f'{new_game_name}.cue'))

        # Rename cu2 file
        if exists(original_cu2_file):
            rename(original_cu2_file, join(game_full_path, f'{new_game_name}.cu2'))

        # Rename bmp file
        if exists(join(game_full_path, f'{game_name}.bmp')):
            rename(join(game_full_path, f'{game_name}.bmp'), join(game_full_path, f'{new_game_name}.bmp'))
        if exists(join(game_full_path, f'{game_name}.BMP')):
            rename(join(game_full_path, f'{game_name}.BMP'), join(game_full_path, f'{new_game_name}.BMP'))

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to validate the game name (ensure irt is not too long and does not contain periods)
    def _game_name_validator(self, game):
        game_name = game.cue_sheet.game_name
        if '.' in game_name:
            game_name = game_name.replace('.', '_')

        if len(game_name) > self.MAX_GAME_NAME_LENGTH:
            game_name = game_name[:self.MAX_GAME_NAME_LENGTH]

        game.cue_sheet.new_name = game_name
        return game_name

    # *****************************************************************************************************************
    # Function to check if the game is a multi-bin game
    def _is_multi_bin(self, game):
        return len(game.cue_sheet.bin_files) > 1

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to check if all of the required bin files exist
    def _all_game_files_exist(self, game):
        for bin_file in game.cue_sheet.bin_files:
            if not exists(bin_file.file_path):
                return False
        return True

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function that generates a MULTIDISC.LST file for multi-disc games
    def _generate_multidisc_file(self, game_dir, output_path=None):
        bin_files = [f for f in listdir(join(output_path, game_dir)) if f.endswith('.bin')]

        # If there is more than 1 bin file, this should be a multi-disc game
        multi_disc_bins = []
        if len(bin_files) > 1:
            for bin_file in bin_files:
                disc_number = self._get_disc_number(self.get_game_id(join(output_path, game_dir, bin_file)))
                if disc_number > 0:
                    multi_disc_bins.insert(disc_number - 1, bin_file)

        # Create the MULTIDISC.LST file
        if len(multi_disc_bins) > 0:
            with open(join(output_path, game_dir, 'MULTIDISC.LST'), 'w') as multi_disc_file:
                for count, binfile in enumerate(multi_disc_bins):
                    if count < len(multi_disc_bins) - 1:
                        # multi_disc_file.write(f'{binfile}\n')
                        multi_disc_file.write(f'{binfile}\r')
                    else:
                        multi_disc_file.write(binfile)

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to get the game name (using names from redump and the psx data-centre)
    def get_redump_name(self, game_id, validate_game_name=None):
        response = select(f'''SELECT name FROM games WHERE game_id = "{game_id.replace('-', '_')}";''')
        if response is not None and response != []:
            game_name = response[0][0]

            # Ensure that the game name (including disc number and extension) is not more than 60 chars
            if validate_game_name.get():
                if int(line[2]) > 0:
                    if len(game_name) <= 47:
                        return f'{game_name} (Disc {line[2]})'
                    else:
                        return f'{game_name[:47]} (Disc {line[2]})'
                else:
                    if len(game_name) <= 47:
                        return game_name
                    else:
                        return f'{game_name[:47]}'
            else:
                return game_name

        return ''

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to get the game name from the cue sheet (using the binmerge script)
    def _get_game_name_from_cue(self, cue_path, include_track):
        cue_content = read_cue_file(cue_path)
        if cue_content:
            game_name = basename(cue_content[0].filename)
            if not include_track:
                if 'Track' in game_name:
                    game_name = game_name[:game_name.rfind('(', 0) - 1]
            return splitext(game_name)[0]
        return ''

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to get the unique game id from the bin file
    def get_game_id(self, bin_file_path):
        game_disc_collection = get_serial(bin_file_path).replace('.', '').strip()
        return game_disc_collection.replace('_', '-').replace('.', '').strip() if game_disc_collection else None

    # return get_serial(bin_file_path).replace('.', '').strip()
    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to get the unique game id from the bin file
    def _get_disc_collection(self, bin_file_path):
        game_disc_collection = []
        line = ''
        lines_checked = 0
        if exists(bin_file_path):
            with open(bin_file_path, 'rb') as bin_file:
                while line != None and lines_checked < 300:
                    try:
                        line = str(next(bin_file))
                        if line != None:
                            lines_checked += 1
                            for region_code in self.REGION_CODES:
                                if region_code in line:
                                    start = line.find(region_code)
                                    game_id = line[start:start + 11].replace('.', '').strip()
                                    if game_id not in game_disc_collection:
                                        game_disc_collection.append(game_id)
                                    else:
                                        raise StopIteration
                    except StopIteration:
                        break
        return game_disc_collection

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function that gets the disc number (using data from redump)
    def _get_disc_number(self, game_id):
        response = select(f'''SELECT disc_number FROM games WHERE game_id = "{game_id.replace('-', '_')}";''')
        if response is not None and response != []:
            return response[0][0]
        return 0

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to copy the game front cover if it is available
    def _copy_game_cover(self, output_path, game_id, game_name):
        response = select(f'''SELECT id FROM covers WHERE game_id = "{game_id.replace('-', '_')}";''')
        if response is not None and response != []:
            row_id = response[0][0]
            image_out_path = join(output_path, f'{game_name}.bmp')
            extract_game_cover_blob(row_id, image_out_path)

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    # Function to create the global game list
    def _create_game_list(self, selected_path):
        global game_list
        game_list = []

        # Get all of the sub-dirs from the selected directory
        subfolders = [f.name for f in scandir(selected_path) if f.is_dir() and not f.name.startswith('.')]

        # If the user has selected a single directory with no sub-dirs
        if not (subfolders):
            subfolders = [selected_path]

        for subfolder in subfolders:

            if subfolder != "System Volume Information":

                game_directory_path = join(selected_path, subfolder)

                # Get the cue_sheet for the game (there could be more than 1 game in the directory)
                #			cue_sheets = [f for f in listdir(game_directory_path) if f.lower().endswith('.cue') and not f.startswith('.')]
                game_file_list = [f for f in listdir(game_directory_path)]

                game_path = game_directory_path
                for game_record in game_file_list:
                    if "(Unl)" not in game_record:
                        if game_record.lower().endswith('.cue') or game_record.lower().endswith(
                                '.cu2') and not game_record.startswith('.'):
                            the_game = self._get_cue_sheet_data(game_directory_path, game_path, selected_path,
                                                                subfolder,
                                                                game_record)
                            # Add the game to the global game_list
                            game_list += the_game
                        if game_record.lower().endswith('.iso') and not game_record.startswith('.'):
                            the_game = self._get_iso_data(game_directory_path, game_path, selected_path, subfolder)
                            game_list.append(the_game)
                            self._print_game_details(the_game)

        game_list.sort(key=lambda game_item: game_item.cue_sheet.game_name, reverse=False)

    def rename_cue_cu2_to_bin(self, game):
        base, ext = splitext(game)
        if ext in ['.cue', '.cu2']:
            new_game = base + '.bin'
            return new_game
        return game

    # *****************************************************************************************************************
    def _get_cue_sheet_data(self, game_directory_path, game_path, selected_path, subfolder, game_record):
        game_id = None
        temp_game_list = []
        if game_record.lower().endswith('.cue') or game_record.lower().endswith('.cu2') and not game_record.startswith(
                '.'):
            cue_sheet_path = join(game_directory_path, game_record)
            game_name_from_cue = self._get_game_name_from_cue(cue_sheet_path, False)

            # Try and get the unique game_id from the first bin file
            bin_files = read_cue_file(cue_sheet_path)
            if bin_files:
                game_id = self.get_game_id(bin_files[0].filename)

            # Try and get the disc number (using data from redump)
            disc_number = 0
            disc_collection = []
            if game_id:
                disc_number = self._get_disc_number(game_id)
                disc_collection = self._get_disc_collection(join(game_directory_path, f'{game_name_from_cue}.bin'))

            # Check if the game directory already contains a cu2 file
            cu2_present = exists(join(selected_path, subfolder, f'{cue_sheet_path[-3]}cu2'))

            # Create the cue_sheet object
            the_cue_sheet = Cuesheet(game_name_from_cue, cue_sheet_path, game_name_from_cue)

            # Check if the game directory already contains a bmp cover image
            cover_art_present = self.has_cover_art(game_directory_path, cue_sheet_path)

            # Add each of the bin_file objects to the cue_sheet object
            bin_files = read_cue_file(cue_sheet_path)
            for bin_file in bin_files:
                the_cue_sheet.add_bin_file(Binfile(basename(bin_file.filename), bin_file.filename))

            the_game = Game(subfolder, selected_path, game_id, disc_number, disc_collection, the_cue_sheet,
                            cover_art_present, cu2_present)
            self._print_game_details(the_game)
            temp_game_list.append(the_game)

        return temp_game_list

    def _get_iso_data(self, game_directory_path, game_path, selected_path, subfolder, game):
        pass

    def has_cover_art(self, game_directory_path, game):
        # Check if the game directory already contains a bmp cover image
        cover_art_path = join(game_directory_path, game[:-3])
        cover_art_present = exists(f'{cover_art_path}bmp') or exists(f'{cover_art_path}BMP')
        return cover_art_present

    # *****************************************************************************************************************
    # Function to print the game details to the console for debugging purposes
    def _print_game_details(self, game):
        print(f'game directory: {game.directory_name}')
        print(f'game path: {game.directory_path}')
        print(f'game id: {game.id}')
        print(f'disc number: {game.disc_number}')

        if game.disc_collection:
            print(f'disc collection: {game.disc_collection}')

        print(f'game cover_art_present: {game.cover_art_present}')
        print(f'game cu2_present: {game.cu2_present}')
        print(f'cue_sheet file_name: {game.cue_sheet.file_name}')
        print(f'cue_sheet file_path: {game.cue_sheet.file_path}')
        print(f'cue_sheet game_name: {game.cue_sheet.game_name}')

        bin_files = game.cue_sheet.bin_files
        print(f'number of bin files: {len(bin_files)}')
        for bin_file in bin_files:
            print(f'bin_file file_name: {bin_file.file_name}')
            print(f'bin_file file_path: {bin_file.file_path}')
        print()

    # *****************************************************************************************************************
    # Function to check if the game is a multi-disc game
    def _is_multi_disc(self, game):
        return int(game.disc_number) > 0 if game.disc_number is not None else None

    # *****************************************************************************************************************
    # Function to parse the game list and displays the results in a message dialog
    def _parse_game(self, game):
        # This function processes an individual game and returns relevant information
        bin_files = game.cue_sheet.bin_files

        unidentified = game.id is None
        no_cover = not game.cover_art_present and (game.disc_number is not None and int(game.disc_number) < 2)
        is_multi_disc = self._is_multi_disc(game)
        multi_disc = is_multi_disc and int(game.disc_number) == 1
        multi_bin = len(bin_files) > 1
        invalid_name = len(game.cue_sheet.game_name) > self.MAX_GAME_NAME_LENGTH or '.' in game.cue_sheet.game_name

        return {
            'game': game,
            'unidentified': unidentified,
            'no_cover': no_cover,
            'multi_disc': multi_disc,
            'is_multi_disc': is_multi_disc,
            'multi_bin': multi_bin,
            'invalid_name': invalid_name
        }

    def parse_game_list(self, path):
        self._create_game_list(path)

        games_without_cover = []
        multi_bin_games = []
        invalid_named_games = []
        unidentified_games = []

        multi_discs = []
        multi_disc_games = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submitting tasks for each game in game_list
            future_to_game = {executor.submit(self._parse_game, game): game for game in game_list}

            for future in concurrent.futures.as_completed(future_to_game):
                game_data = future.result()
                game = game_data['game']

                if game_data['unidentified']:
                    unidentified_games.append(game)

                if game_data['no_cover']:
                    games_without_cover.append(game)

                if game_data['is_multi_disc']:
                    multi_discs.append(game)
                    if game_data['multi_disc']:
                        multi_disc_games.append(game)

                if game_data['multi_bin']:
                    multi_bin_games.append(game)

                if game_data['invalid_name']:
                    invalid_named_games.append(game)

        details = f'''Total Discs Found: {len(game_list)} \nMulti-Disc Games: {len(multi_disc_games)} \nUnidentfied Games: {len(unidentified_games)} \nMulti-bin Games: {len(multi_bin_games)} \nMissing Covers: {len(games_without_cover)} \nInvalid Game Names: {len(invalid_named_games)}'''

        msg_box = QMessageBox()
        msg_box.setWindowTitle('Game Details')
        msg_box.setText(details)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setFixedWidth(650)
        msg_box.exec()

        # if multi_bin_games:
        #  window.after(0, lambda: merge_bin_files.set(True))  # Schedule GUI update on main thread
        #  window.after(0, lambda: force_cu2.set(True))  # Schedule GUI update on main thread
        # if games_without_cover:
        #    window.after(0, lambda: add_cover_art.set(True))  # Schedule GUI update on main thread
        # if invalid_named_games:
        #   window.after(0, lambda: validate_game_name.set(True))  # Schedule GUI update on main thread

        print()
        print('multi-discs:')
        for game in multi_discs:
            print(game.id)

        print()
        print('multi-disc games:')
        for game in multi_disc_games:
            print(game.id)

        self._poo()

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    def _poo(self):
        print()
        print('checking for multi-disc games...\n')

        for game in game_list:
            if int(game.disc_number) == 1:
                print(f'game id: {game.id}')
                print(f'game name: {game.cue_sheet.game_name}')
                print(f'game disc: {game.disc_number}')
                print(f'game collection: {game.disc_collection}')

    # *****************************************************************************************************************

    # *****************************************************************************************************************
    def _display_game_list(self):
        bools = ('No', 'Yes')
        for count, game in enumerate(game_list):
            game_id = game.id
            game_name = game.cue_sheet.game_name
            disc_number = game.disc_number
            number_of_bins = len(game.cue_sheet.bin_files)
            name_valid = bools[
                len(game.cue_sheet.game_name) <= self.MAX_GAME_NAME_LENGTH and '.' not in game.cue_sheet.game_name]
            cu2_present = bools[game.cu2_present]
            bmp_present = bools[game.cover_art_present]
        # treeview_game_list.insert(parent='', index=count, iid=count, text='', values=(
        #     game_id, game_name, disc_number, number_of_bins, name_valid, cu2_present, bmp_present))

    # *****************************************************************************************************************
