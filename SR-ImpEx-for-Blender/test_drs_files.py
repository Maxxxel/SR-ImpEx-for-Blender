from drs_definitions import DRS
import os

# Debug the file by loading it, write a main
if __name__ == "__main__":
	# Load ALL DRS files in given directory
	# Create an array sorted by the amount of bones
	# check how many duplicate bones the models have and create a ranking, like: only uniques, 2 duplicates, etc. with a counter
	unit_dir = "D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx\\units"
	## Load all DRS files in the subdirectories, not main
	files = []
	start_after = "unit_antlion"
	start = False
	for root, dirs, file in os.walk(unit_dir):
		for f in file:
			if f.endswith(".drs"):
				if start_after in f:
					start = True
				if not start:
					continue
				# Append full path
				files.append(os.path.relpath(os.path.join(root, f), unit_dir))

	models_by_bone_count = {}
	models_by_duplicate_bones = {}

	for file in files:
		print(f"Loading: {file}")
		drs_file: 'DRS' = DRS().read(os.path.join(unit_dir, file))

	print("DONE")
