import os
import time
from debug_ska_definitions import SKA

ska_parent_folder = "D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx"

# Find all *ska files in all subfolders of ska_parent_folder
ska_files = []

for root, dirs, files in os.walk(ska_parent_folder):
    for file in files:
        if file.endswith(".ska"):
            ska_files.append(os.path.join(root, file))

print(f"Found {len(ska_files)} SKA files.")

for i, file in enumerate(ska_files):
    ska = SKA().read(file)
    if ska.type != 7:
        print(file, f"Type: {ska.type}")
