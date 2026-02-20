import pygame
import os
from os import path
import getpass
import time
from pyvidplayer2 import Video
from pycaw.pycaw import AudioUtilities
from math import log10

import json
from importlib.resources import files



pygame.joystick.init()
pygame.font.init()

BACKGROUND_COLOUR = (10, 0, 10)
FOREGROUND_COLOUR = (50, 255, 80)
FOREGROUND_COLOUR_2 = (50, 180, 80)


class Key:
	def __init__(
		self,
		action,
		on_just_pressed=True,
		repeat_with_delay=True,
		delay_time=0.2,
		start_repeat_delay=0.5,
	):
		self.pressed_time = 0
		self.action = action
		self.on_just_pressed = on_just_pressed
		self.repeat_with_delay = repeat_with_delay
		self.delay_time = delay_time
		self.start_repeat_delay = start_repeat_delay
		self.times_repeated = 0
		self.repressed = False
		self.replay_time = 0

	def press(self, delta, j=None):
		if not self.on_just_pressed and not self.repeat_with_delay:
			self.action()
		elif not self.on_just_pressed and self.repeat_with_delay:
			if not self.repressed:
				self.action()
				self.repressed = True
			else:
				self.replay_time += delta
				if self.replay_time >= self.delay_time:
					self.repressed = False
					self.replay_time = 0
		else:
			if not self.repressed:
				self.action()
				self.repressed = True
				self.times_repeated += 1
				if j:
					j.rumble(0.5, 0.1, 100)
			elif self.repeat_with_delay:
				self.replay_time += delta
				if (
					self.times_repeated != 1 and self.replay_time >= self.delay_time
				) or self.replay_time >= self.start_repeat_delay:
					self.repressed = False
					self.replay_time = 0

	def release(self):
		self.repressed = False
		self.replay_time = 0
		self.times_repeated = 0


class Main:
	def __init__(self):
		self.win = pygame.display.set_mode(flags=pygame.FULLSCREEN)

		self.alive = True

		self.video_name = None
		self.video = None
		self.video_surface = pygame.surface.Surface((0, 0))
		self.video_position = (0, 0)
		self.video_times = {}
		self.video_lengths = {}

		### CONTROLS ###
		self.joysticks = [
			pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())
		]

		self.joystick_threshold = 0.5
		self.delay_time = 100

		self.up = Key(self.decr_selected, delay_time=0.05)
		self.down = Key(self.incr_selected, delay_time=0.05)
		self.left = Key(self.do_nothing)
		self.right = Key(self.do_nothing)
		self.back = Key(self.go_parent_folder)
		self.enter = Key(self.enter_directory)

		self.r2 = Key(self.incr_tab)
		self.l2 = Key(self.decr_tab)

		self.device = AudioUtilities.GetSpeakers()
		print("Audio control: ", self.device.FriendlyName)

		self.current_menu_function = self.run_search
		self.tab_bar = {
			"Settings": self.start_settings_menu,
			"Search": self.start_search_menu,
			"Video": self.start_video_menu,
		}

		self.selected_tab = 1
		self.last_tab = 1
		self.selected = 0
		self.last_selected = 0
		self.selected_setting = 0

		self.selected_volume_setting = 0
		self.selected_text_setting = 0

		#################

		self.valid_extensions = ["mkv", "mp4"]
		self.current_font = 0
		self.font_size = 20
		
		self.font = None
		self.big_font = None
		self.load_fonts()

		self.offset_list = {}
		self.folders = []
		self.files = []

		self.settings_options = {
			"Volume": self.start_volume_control, 
			"Text": self.start_text_control,
			"Exit": self.quit
			}

		self.text_control_options = {
			"Font Size": (self.decr_font_size, self.incr_font_size),
			"Change Font": self.flick_font,
			"Back": self.return_to_settings_menu,
		}
		
		self.volume_options = {
			"Master Volume": (
				self.get_master_volume,
				self.decr_master_volume,
				self.incr_master_volume,
			),
			"Video Volume": (
				self.get_video_volume,
				self.decr_video_volume,
				self.incr_video_volume,
			),
			"Back": self.return_to_settings_menu,
		}

		self.video_volume = 1.0
		self.video_volume_step = 0.05
		self.master_volume = 0.5
		self.master_volume_step = 0.05
		self.watched_percentages = {}

		self.offset = 0
		self.tab_offset = 0
		self.settings_offset = 0
		self.current_folder = ""
		self.save_file = None

		self.max_font_size = 32
		self.min_font_size = 12


		self.setup()
		self.load_fonts()
		self.on_change_directory()

	def load_fonts(self):
		loaded_font = os.listdir(files("pelevision").joinpath("fonts"))[self.current_font]
		self.font = pygame.font.Font(files("pelevision").joinpath("fonts/" + loaded_font), self.font_size)
		self.big_font = pygame.font.Font(files("pelevision").joinpath("fonts/" + loaded_font), self.font_size+4)

	def start_text_control(self):
		self.up = Key(self.decr_selected_text)
		self.down = Key(self.incr_selected_text)
		self.left = Key(self.text_control_left)
		self.right = Key(self.text_control_right)
		self.back = Key(self.start_settings_menu)
		self.current_menu_function = self.run_text_control
	
	def incr_font_size(self):
		self.font_size += 1
		self.font_size = min(self.max_font_size, self.font_size)
		self.load_fonts()
	def decr_font_size(self):
		self.font_size -= 1
		self.font_size = max(self.min_font_size, self.font_size)
		self.load_fonts()
	
	def text_control_left(self):
		opt = self.text_control_options[
			list(self.text_control_options.keys())[self.selected_text_setting]
		]
		if type(opt) == tuple:
			opt[0]()

	def text_control_right(self):
		
		opt = self.text_control_options[
			list(self.text_control_options.keys())[self.selected_text_setting]
		]
		if type(opt) == tuple:
			opt[1]()

	def flick_font(self):
		self.current_font += 1
		self.current_font %= len(os.listdir("fonts"))
		self.load_fonts()

	def incr_selected_text(self):
		self.selected_text_setting += 1
	def decr_selected_text(self):
		self.selected_text_setting -= 1
	def sanitize_selected_text(self):
		self.selected_text_setting = min(len(self.text_control_options)-1,max(0, self.selected_text_setting))

	def run_text_control(self, elapsed, surface):
		current_selection = self.big_font.render(
			list(self.text_control_options.keys())[self.selected_text_setting],
			True,
			FOREGROUND_COLOUR,
			BACKGROUND_COLOUR,
		)
		max_height = surface.get_height() - current_selection.get_height()

		for i, option in enumerate(list(self.text_control_options.keys())):

			background = BACKGROUND_COLOUR
			foreground = FOREGROUND_COLOUR
			if i == self.selected_text_setting:
				background = foreground
				foreground = BACKGROUND_COLOUR
			text_surface = self.font.render(option, True, foreground, background)

			y = i * text_surface.get_height() + self.settings_offset
			if i == self.selected_text_setting:
				if y - 10 < 0:
					dist = 10 - y
					self.settings_offset += elapsed * 10 * dist
				elif y + text_surface.get_height() + 10 > max_height:
					dist = y + text_surface.get_height() + 10 - max_height
					self.settings_offset -= elapsed * 10 * dist

			if y < -text_surface.get_height():
				continue
			if y > max_height and i >= self.selected:
				break

			surface.blit(text_surface, (30, y))

			opt = self.text_control_options[option]
			if type(opt) == tuple:
				pygame.draw.rect(
					surface,
					FOREGROUND_COLOUR_2,
					(
						surface.get_width() / 3 + 1,
						y + 1,
						surface.get_width()/ 4 - 2,
						text_surface.get_height() - 2,
					),
				)
				percentage = abs(self.font_size-self.min_font_size)/abs(self.max_font_size-self.min_font_size)
				pygame.draw.rect(
					surface,
					FOREGROUND_COLOUR,
					(
						surface.get_width() / 3 + 2,
						y + 2,
						surface.get_width() * percentage / 4 - 4,
						text_surface.get_height() - 4,
					),
				)

		surface.blit(current_selection, (10, max_height))
		

	def incr_volume_select(self):
		self.selected_volume_setting += 1
		self.sanitise_volume_select()

	def decr_volume_select(self):
		self.selected_volume_setting -= 1
		self.sanitise_volume_select()

	def sanitise_volume_select(self):
		self.selected_volume_setting = min(
			max(0, self.selected_volume_setting), len(self.volume_options) - 1
		)

	def incr_video_volume(self):
		self.video_volume += self.video_volume_step
		self.video_volume = min(1.0, self.video_volume)

	def decr_video_volume(self):
		self.video_volume -= self.video_volume_step
		self.video_volume = max(0.0, self.video_volume)

	def get_video_volume(self):
		return self.video_volume

	def incr_master_volume(self):
		before = self.get_master_volume()
		self.set_master_volume(min(1.0, before + self.master_volume_step))

	def decr_master_volume(self):
		before = self.get_master_volume()
		self.set_master_volume(max(0, before - self.master_volume_step))

	def get_master_volume(self):
		volume = self.device.EndpointVolume
		vol_range = volume.GetVolumeRange()
		current_volume = volume.GetMasterVolumeLevel()
		# percentage = (self.db_to_linear(current_volume) + abs(self.db_to_linear(vol_range[0])))/abs(self.db_to_linear(vol_range[1])-self.db_to_linear(vol_range[0]))
		return self.db_to_linear(current_volume)

	def set_master_volume(self, level):
		volume = self.device.EndpointVolume
		vol_range = volume.GetVolumeRange()
		level = max(vol_range[0], min(vol_range[1], self.linear_to_db(level)))
		volume.SetMasterVolumeLevel(level, None)

	def db_to_linear(self, db):
		return pow(10, db / 34)

	def linear_to_db(self, ln):
		if ln == 0:
			return -120
		return 34 * log10(ln)

	def toggle_fullscreen(self):
		pygame.display.toggle_fullscreen()
		pygame.display.set_window_position((10, 10))

	def start_search_menu(self):
		self.up = Key(self.decr_selected, delay_time=0.02)
		self.down = Key(self.incr_selected, delay_time=0.02)
		self.left = Key(self.do_nothing)
		self.right = Key(self.do_nothing)
		self.back = Key(self.go_parent_folder)
		self.enter = Key(self.enter_directory)
		self.current_menu_function = self.run_search

	def start_settings_menu(self):
		self.up = Key(self.decr_setting)
		self.down = Key(self.incr_setting)
		self.left = Key(self.do_nothing)
		self.right = Key(self.do_nothing)
		self.back = Key(self.do_nothing)
		self.enter = Key(self.click_setting)
		self.current_menu_function = self.run_settings

	def return_to_settings_menu(self):
		self.up = Key(self.decr_setting)
		self.down = Key(self.incr_setting)
		self.left = Key(self.do_nothing)
		self.right = Key(self.do_nothing)
		self.back = Key(self.do_nothing)
		self.current_menu_function = self.run_settings

	def start_video_menu(self):
		self.up = Key(self.incr_master_volume, delay_time=0.5)
		self.down = Key(self.decr_master_volume, delay_time=0.5)
		self.left = Key(self.rewind_video, delay_time=0.01)
		self.right = Key(self.wind_video, delay_time=0.01)
		self.back = Key(self.do_nothing)
		self.enter = Key(self.toggle_pause)
		self.current_menu_function = self.run_video
		self.resize_video()
		if self.video != None:
			self.video.seek(self.video_times[self.video_name], False)

	def resize_video(self):
		self.video_surface.fill(BACKGROUND_COLOUR)
		if self.video != None:
			original_size = self.video.get_metadata()["original_size"]
			screen_size = self.video_surface.get_size()
			scale = (
				screen_size[0] / original_size[0],
				screen_size[1] / original_size[1],
			)
			new_size = (
				int(original_size[0] * min(scale)),
				int(original_size[1] * min(scale)),
			)
			self.video.resize(new_size)

			self.video_position = (
				(screen_size[0] - new_size[0]) / 2,
				(screen_size[1] - new_size[1]) / 2,
			)

	def start_nothing(self):
		self.up = Key(self.do_nothing)
		self.down = Key(self.do_nothing)
		self.left = Key(self.do_nothing)
		self.right = Key(self.do_nothing)
		self.back = Key(self.do_nothing)
		self.enter = Key(self.do_nothing)
		self.current_menu_function = self.do_nothing

	def start_volume_control(self):
		self.up = Key(self.decr_volume_select, delay_time=0.05)
		self.down = Key(self.incr_volume_select, delay_time=0.05)
		self.left = Key(self.decr_selected_volume)
		self.right = Key(self.incr_selected_volume)
		self.back = Key(self.start_settings_menu)

		self.current_menu_function = self.run_volume_control

	def incr_selected_volume(self):
		opt = self.volume_options[
			list(self.volume_options.keys())[self.selected_volume_setting]
		]
		if type(opt) != tuple:
			return
		opt[2]()

	def decr_selected_volume(self):
		opt = self.volume_options[
			list(self.volume_options.keys())[self.selected_volume_setting]
		]
		if type(opt) != tuple:
			return
		opt[1]()

	def run_volume_control(self, elapsed, surface):

		current_selection = self.big_font.render(
			list(self.volume_options.keys())[self.selected_volume_setting],
			True,
			FOREGROUND_COLOUR,
			BACKGROUND_COLOUR,
		)
		max_height = surface.get_height() - current_selection.get_height()

		for i, option in enumerate(list(self.volume_options.keys())):

			background = BACKGROUND_COLOUR
			foreground = FOREGROUND_COLOUR
			if i == self.selected_volume_setting:
				background = foreground
				foreground = BACKGROUND_COLOUR
			text_surface = self.font.render(option, True, foreground, background)

			y = i * text_surface.get_height() + self.settings_offset
			if i == self.selected_volume_setting:
				if y - 10 < 0:
					dist = 10 - y
					self.settings_offset += elapsed * 10 * dist
				elif y + text_surface.get_height() + 10 > max_height:
					dist = y + text_surface.get_height() + 10 - max_height
					self.settings_offset -= elapsed * 10 * dist

			if y < -text_surface.get_height():
				continue
			if y > max_height and i >= self.selected:
				break

			surface.blit(text_surface, (30, y))

			opt = self.volume_options[option]
			if type(opt) == tuple:
				percentage = opt[0]()
				pygame.draw.rect(
					surface,
					FOREGROUND_COLOUR,
					(
						surface.get_width() / 3,
						y + 2,
						surface.get_width() * percentage / 4,
						text_surface.get_height() - 2,
					),
				)
		surface.blit(current_selection, (10, max_height))

	def rewind_video(self):
		if self.video != None:
			self.video.seek(-5)

	def wind_video(self):
		if self.video != None:
			self.video.seek(5)

	def toggle_pause(self):
		if self.video != None:
			if not self.video.active:
				self.video.play()
			else:
				self.video.toggle_pause()
			# print("Video pause toggled")

	def run_video(self, elapsed, surface):
		if self.video_surface.get_size() != surface.get_size():
			self.video_surface = surface
			self.resize_video()

		if self.video != None:
			self.video.set_volume(self.video_volume)
			self.video.draw(self.video_surface, self.video_position, force_draw=False)
			self.video_times[self.video_name] = self.video.get_pos()

		if self.video == None:
			surface.blit(self.video_surface, (0,0))
		else:
			surface.blit(self.video_surface)

	def incr_setting(self):
		self.selected_setting += 1
		self.selected_setting = min(
			len(self.settings_options) - 1, self.selected_setting
		)

	def decr_setting(self):
		self.selected_setting -= 1
		self.selected_setting = max(0, self.selected_setting)

	def click_setting(self):
		if self.current_menu_function == self.run_settings:
			self.settings_options[
				list(self.settings_options.keys())[self.selected_setting]
			]()
		elif self.current_menu_function == self.run_volume_control:
			opt = self.volume_options[
				list(self.volume_options.keys())[self.selected_volume_setting]
			]
			if type(opt) == tuple:
				return
			opt()
		elif self.current_menu_function == self.run_text_control:
			opt = self.text_control_options[
				list(self.text_control_options.keys())[self.selected_text_setting]
			]
			if type(opt) == tuple:
				return
			opt()


	def setup(self):
		username = getpass.getuser()
		localappdata = f"C:/Users/{username}/AppData/Local"
		tvfolder = localappdata + "/pyvision"
		if not path.exists(tvfolder):
			os.makedirs(tvfolder)

		self.current_folder = tvfolder
		self.save_file = tvfolder + "/session_info.json"
		if not path.exists(self.save_file):
			with open(self.save_file, "w") as f:
				f.write("{}")

		else:
			with open(self.save_file, "r") as f:
				last_session_data = json.load(f)
				if "current_folder" in last_session_data.keys():
					self.current_folder = last_session_data["current_folder"]
				if "offset_list" in last_session_data.keys():
					self.offset_list = last_session_data["offset_list"]
				if "video_times" in last_session_data.keys():
					self.video_times = last_session_data["video_times"]
				if "selected" in last_session_data.keys():
					self.selected = last_session_data["selected"]
				if "video_lengths" in last_session_data.keys():
					self.video_lengths = last_session_data["video_lengths"]
				if "font_size" in last_session_data.keys():
					self.font_size = last_session_data["font_size"]
				if "current_font" in last_session_data.keys():
					self.current_font = last_session_data["current_font"]

	def do_nothing(self, *args):
		pass

	def incr_selected(self):
		self.selected += 1
		self.secure_selected_index()

	def decr_selected(self):
		self.selected -= 1
		self.secure_selected_index()

	def go_parent_folder(self):
		self.current_folder += "/.."
		self.on_change_directory()

	def secure_selected_index(self):
		self.selected = max(0, self.selected)
		self.selected = min(
			len(self.get_options(self.current_folder)) - 1, self.selected
		)

	def enter_directory(self):
		opt = self.get_options(self.current_folder)
		if len(opt) == 0:
			return
		new_file = opt[self.selected]
		new_dir = self.current_folder + "/" + new_file
		if not os.path.isdir(new_dir):
			self.video = Video(new_dir)
			self.video_name = new_file
			if not self.video_name in list(self.video_times.keys()):
				self.video_times[self.video_name] = 0
			if not self.video_name in list(self.video_lengths.keys()):
				self.video_lengths[self.video_name] = self.video.get_metadata()[
					"duration"
				]
			return

		self.current_folder = new_dir
		self.on_change_directory()

	def on_change_directory(self):
		self.current_folder = path.normpath(self.current_folder)
		if self.current_folder in list(self.offset_list.keys()):
			self.offset = self.offset_list[self.current_folder][0]
			self.selected = self.offset_list[self.current_folder][1]
		else:
			self.offset = 0
			self.selected = 0
		self.files.clear()
		self.folders.clear()
		self.watched_percentages.clear()

		self.list_dir(self.current_folder, scan=True)
		self.secure_selected_index()

	def incr_tab(self):
		self.selected_tab += 1
		self.sanitise_selected_tab()
		for j in self.joysticks:
			if not j.rumble(0.5, 0.0, 70):
				print("Error rumbling")

	def decr_tab(self):
		self.selected_tab -= 1
		self.sanitise_selected_tab()
		for j in self.joysticks:
			if not j.rumble(0.5, 0.0, 70):
				print("Error rumbling")

	def sanitise_selected_tab(self):
		self.selected_tab = max(0, min(len(self.tab_bar) - 1, self.selected_tab))
		if self.selected_tab != self.last_tab:
			self.tab_bar[list(self.tab_bar.keys())[self.selected_tab]]()
			self.last_tab = self.selected_tab
			if self.video != None:
				self.video.pause()

	def handle_joystick(self, delta):
		for j in self.joysticks:
			h = j.get_axis(0)
			v = j.get_axis(1)

			if abs(h) >= self.joystick_threshold:
				if h < 0:
					self.left.press(delta, j)
				else:
					self.right.press(delta, j)
			else:
				self.left.release()
				self.right.release()

			if abs(v) >= self.joystick_threshold:
				if v < 0:
					self.up.press(delta, j)
				else:
					self.down.press(delta, j)
			else:
				self.up.release()
				self.down.release()

			if j.get_button(1):
				self.back.press(delta)
			else:
				self.back.release()
			if j.get_button(0):

				self.enter.press(delta)
			else:
				self.enter.release()

			# print(j.get_axis(5), j.get_axis(4))

			if abs(j.get_axis(5) + 1) > self.joystick_threshold:
				self.r2.press(delta)
			else:
				self.r2.release()
			if abs(j.get_axis(4) + 1) > self.joystick_threshold:
				self.l2.press(delta)
			else:
				self.l2.release()

	def list_dir(self, dir, scan=False):
		if scan:
			complete = os.listdir(dir)
			for sub in complete:
				subpath = dir + "/" + sub
				if sub[0] == ".":
					continue
				if path.isfile(subpath) and os.access(subpath, os.R_OK):
					self.files.append(sub)
				elif path.isdir(subpath):
					try:
						os.listdir(subpath)
					except PermissionError:
						continue
					self.folders.append(sub)
		accessible = self.folders + self.files

		return accessible

	def get_options(self, dir):
		folder = self.list_dir(dir)
		q = []
		for sub in folder:
			subpath = dir + "/" + sub
			if sub in self.files:
				if self.is_valid_file(subpath):
					q.append(sub)
			else:
				q.append(sub)
		return q

	def contains_video(self, dir):

		folder = self.list_dir(dir)
		if len(folder) > 10:
			return True

		for sub in folder:
			subpath = dir + "/" + sub
			if path.isfile(subpath):
				if self.is_valid_file(subpath):
					return True
			elif path.isdir(subpath):
				if self.contains_video(subpath):
					return True

		self.no_access_list.append(dir)
		return False

	def is_valid_file(self, dir):
		if path.isfile(dir):
			if "." not in dir:
				return False
			split = dir.split(".")
			if len(split) <= 1:
				return False
			extension = split[len(split) - 1]
			return extension in self.valid_extensions
		return False

	def run_search(self, elapsed, surface):
		files = self.get_options(self.current_folder)

		current_path_surface = self.big_font.render(
			self.current_folder, True, FOREGROUND_COLOUR, BACKGROUND_COLOUR
		)
		max_height = surface.get_height() - current_path_surface.get_height()

		for i, file in enumerate(files):
			background = BACKGROUND_COLOUR
			foreground = FOREGROUND_COLOUR
			if i == self.selected:
				background = foreground
				foreground = BACKGROUND_COLOUR
			text_surface = self.font.render(file, True, foreground, background)

			y = i * text_surface.get_height() + self.offset
			if i == self.selected:
				if y - 10 < 0:
					dist = 10 - y
					self.offset += elapsed * 10 * dist
				elif y + text_surface.get_height() + 10 > max_height:
					dist = y + text_surface.get_height() + 10 - max_height
					self.offset -= elapsed * 10 * dist

				self.offset_list[self.current_folder] = (int(self.offset), i)

			if y < -text_surface.get_height():
				continue
			if y > max_height and i >= self.selected:
				break

			surface.blit(text_surface, (15, y))
			if file in self.files:
				if file in self.video_times.keys():
					percentage = self.video_times[file] / self.video_lengths[file]

					pygame.draw.rect(
						surface,
						FOREGROUND_COLOUR_2,
						(
							surface.get_width() / 3 + 1,
							y + 1,
							surface.get_width() / 4 - 2,
							text_surface.get_height() - 2,
						),
					)
					pygame.draw.rect(
						surface,
						FOREGROUND_COLOUR,
						(
							surface.get_width() / 3 + 2,
							y + 2,
							surface.get_width() * percentage / 4 - 4,
							text_surface.get_height() - 4,
						),
					)

		surface.blit(current_path_surface, (10, max_height))

	def run_settings(self, elapsed, surface):

		current_selection = self.big_font.render(
			list(self.settings_options.keys())[self.selected_setting],
			True,
			FOREGROUND_COLOUR,
			BACKGROUND_COLOUR,
		)
		max_height = surface.get_height() - current_selection.get_height()

		for i, option in enumerate(list(self.settings_options.keys())):

			background = BACKGROUND_COLOUR
			foreground = FOREGROUND_COLOUR
			if i == self.selected_setting:
				background = foreground
				foreground = BACKGROUND_COLOUR
			text_surface = self.font.render(option, True, foreground, background)

			y = i * text_surface.get_height() + self.settings_offset
			if i == self.selected_setting:
				if y - 10 < 0:
					dist = 10 - y
					self.settings_offset += elapsed * 10 * dist
				elif y + text_surface.get_height() + 10 > max_height:
					dist = y + text_surface.get_height() + 10 - max_height
					self.settings_offset -= elapsed * 10 * dist

			if y < -text_surface.get_height():
				continue
			if y > max_height and i >= self.selected:
				break

			surface.blit(text_surface, (15, y))
		surface.blit(current_selection, (10, max_height))

	def display_tab(self, elapsed, surface):
		max_width = -1
		char_length = -1
		for file in list(self.tab_bar.keys()):
			text_surface = self.big_font.render(
				file + "  ", True, BACKGROUND_COLOUR, BACKGROUND_COLOUR
			)
			if text_surface.get_width() > max_width:
				max_width = text_surface.get_width()
				char_length = len(file) + 2

		x = self.tab_offset
		for i, file in enumerate(list(self.tab_bar.keys())):
			while len(file) < char_length:
				file = " " + file + " "
			if len(file) > char_length:
				file = file[1:]
			background = BACKGROUND_COLOUR
			foreground = FOREGROUND_COLOUR
			if i == self.selected_tab:
				background = foreground
				foreground = BACKGROUND_COLOUR
			text_surface = self.big_font.render(file, True, foreground, background)

			if i == self.selected_tab:
				if x - 10 < 0:
					dist = 10 - x
					self.tab_offset += elapsed * 10 * dist
				elif x + text_surface.get_width() + 10 > surface.get_width():
					dist = x + text_surface.get_width() + 10 - surface.get_width()
					self.tab_offset -= elapsed * 10 * dist

			surface.blit(text_surface, (x, 0))
			x += max_width + 10
			pygame.draw.line(
				surface,
				FOREGROUND_COLOUR,
				(x - 5, 0),
				(x - 5, text_surface.get_height()),
			)
		return text_surface.get_height()

	def run(self):
		then = time.time()
		now = then

		while self.alive:
			# self.set_master_volume(self.master_volume)
			now = time.time()
			elapsed = now - then
			if elapsed != 0:
				pygame.display.set_caption(str(int(1 / elapsed)))

			self.handle_joystick(elapsed)
			self.win.fill(BACKGROUND_COLOUR)

			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					self.quit()

			n = self.display_tab(elapsed, self.win)

			menu_surface = pygame.surface.Surface(
				(self.win.get_width(), self.win.get_height() - n)
			)
			self.current_menu_function(elapsed, menu_surface)
			self.win.blit(
				menu_surface, (0, n, self.win.get_width(), self.win.get_height() - n)
			)

			pygame.display.update()

			then = now

	def quit(self):
		with open(self.save_file, "w") as f:
			session_data = {
				"current_folder": self.current_folder,
				"offset_list": self.offset_list,
				"video_times": self.video_times,
				"selected": self.selected,
				"video_lengths": self.video_lengths,
				"font_size": self.font_size,
				"current_font": self.current_font,
			}
			json.dump(session_data, f)
		self.alive = False

def run():
	g = Main()
	g.run()

# if __name__ == "__main__":
# 	run()
