from io import BufferedReader
import os

def read_drs_header(reader: BufferedReader) -> dict:
	header = {
		"magic": reader.read(4),
		"number_of_models": int.from_bytes(reader.read(4), byteorder='little'),
		"node_information_offset": int.from_bytes(reader.read(4), byteorder='little'),
		"node_hierarchy_offset": int.from_bytes(reader.read(4), byteorder='little'),
		"node_count": int.from_bytes(reader.read(4), byteorder='little'),
	}

	return header

def read_drs_file(reader: BufferedReader, header: dict) -> dict:
	# Move to the node information offset
	reader.seek(header["node_information_offset"])
	node_information = []

	# Read the root Node: 32 bytes
	rote_node = {
		"zeroes": reader.read(16),
		"neg_one": int.from_bytes(reader.read(4), byteorder='little'),
		"one": int.from_bytes(reader.read(4), byteorder='little'),
		"node_information_count": int.from_bytes(reader.read(4), byteorder='little'),
		"zero": int.from_bytes(reader.read(4), byteorder='little'),
	}

	# Read the node information
	for _ in range(rote_node["node_information_count"]):
		node = {
			"magic": int.from_bytes(reader.read(4), byteorder='little'),
			"identifier": int.from_bytes(reader.read(4), byteorder='little'),
			"offset": int.from_bytes(reader.read(4), byteorder='little'),
			"node_size": int.from_bytes(reader.read(4), byteorder='little'),
			"spacer": reader.read(16),
		}

		node_information.append(node)

	# Move to the node hierarchy offset
	reader.seek(header["node_hierarchy_offset"])
	node_hierarchy = []

	# Read the root Node: 21 bytes
	root_node = {
		"identifier": int.from_bytes(reader.read(4), byteorder='little'),
		"unknown": int.from_bytes(reader.read(4), byteorder='little'),
		"length": int.from_bytes(reader.read(4), byteorder='little'),
	}

	# Read the name of the root node as a string
	root_node["name"] = reader.read(root_node["length"]).decode("utf-8")

	# Read the node hierarchy
	for _ in range(header["node_count"]):
		node = {
			"info_index": int.from_bytes(reader.read(4), byteorder='little'),
			"length": int.from_bytes(reader.read(4), byteorder='little'),
		}

		# Read the name of the node as a string
		node["name"] = reader.read(node["length"]).decode("utf-8")

		# Read the Spacer 0
		node["spacer"] = reader.read(4)

		node_hierarchy.append(node)

	# Return the DRS file
	return {
		"node_information": node_information,
		"node_hierarchy": node_hierarchy,
	}

def compare_node_infos(original: dict, modified: dict):
	if len(original["node_information"]) != len(modified["node_information"]):
		print(f"[ERROR] The number of node information is different: {len(original['node_information'])} != {len(modified['node_information'])}")
		return False

	for i in range(len(original["node_information"])):
		node_info = original["node_information"][i]
		# as we changed order in the modified file, we need to find the corresponding node info by magic
		modified_node_info = next((x for x in modified["node_information"] if x["magic"] == node_info["magic"]), None)

		if modified_node_info is None:
			print(f"[ERROR] The node information with magic {node_info['magic']} was not found in the modified file.")
			# Show the node infos
			print(f"Original: {node_info}")
			print(f"Modified: {modified['node_information']}")
			return False

		if node_info["identifier"] != modified_node_info["identifier"]:
			# print(f"[ERROR] The identifier of the node information with magic {node_info['magic']} is different: {node_info['identifier']} != {modified_node_info['identifier']}")
			pass

		if node_info["offset"] != modified_node_info["offset"]:
			# print(f"[ERROR] The offset of the node information with magic {node_info['magic']} is different: {node_info['offset']} != {modified_node_info['offset']}")
			pass

		if node_info["node_size"] != modified_node_info["node_size"]:
			print(f"[ERROR] The node size of the node information with magic {node_info['magic']} is different: {node_info['node_size']} != {modified_node_info['node_size']}")

	if len(original["node_hierarchy"]) != len(modified["node_hierarchy"]):
		print(f"[ERROR] The number of node hierarchy is different: {len(original['node_hierarchy'])} != {len(modified['node_hierarchy'])}")

def compare_nodes(original: dict, modified: dict):
	if len(original["node_hierarchy"]) != len(modified["node_hierarchy"]):
		print(f"[ERROR] The number of nodes is different: {len(original['node_hierarchy'])} != {len(modified['node_hierarchy'])}")
		return False

	for i in range(len(original["node_hierarchy"])):
		node = original["node_hierarchy"][i]
		# as we changed order in the modified file, we need to find the corresponding node by name
		modified_node = next((x for x in modified["node_hierarchy"] if x["name"] == node["name"]), None)

		if modified_node is None:
			print(f"[ERROR] The node with info index {node['info_index']} was not found in the modified file.")
			# Show the nodes
			print(f"Original: {node}")
			print(f"Modified: {modified['node_hierarchy']}")
			return False

		if node["info_index"] != modified_node["info_index"]:
			# print(f"[ERROR] The info index of the node with info index {node['info_index']} is different: {node['info_index']} != {modified_node['info_index']}")
			pass

		if node["spacer"] != modified_node["spacer"]:
			print(f"[ERROR] The spacer of the node with info index {node['info_index']} is different: {node['spacer']} != {modified_node['spacer']}")

def compare_data(original: dict, modified: dict, _original_reader: BufferedReader, _modified_reader: BufferedReader):
	for i in range(len(original["node_information"])):
		node_info = original["node_information"][i]
		# as we changed order in the modified file, we need to find the corresponding node info by magic
		modified_node_info = next((x for x in modified["node_information"] if x["magic"] == node_info["magic"]), None)

		# Original Data
		_original_reader.seek(node_info["offset"])
		original_data = _original_reader.read(node_info["node_size"])

		# Modified Data
		_modified_reader.seek(modified_node_info["offset"])
		modified_data = _modified_reader.read(modified_node_info["node_size"])

		if original_data != modified_data:
			print(f"[ERROR] The data of the node information with magic {node_info['magic']} is different.")
			# Show the data
			print(f"Original: {original_data}")
			print(f"Modified: {modified_data}")
			return False

		# byte by byte comparison
		for j in range(len(original_data)):
			if original_data[j] != modified_data[j]:
				print(f"[ERROR] The data of the node information with magic {node_info['magic']} is different at byte {j}.")
				# Show the data
				print(f"Original: {original_data}")
				print(f"Modified: {modified_data}")
				return False

def compare_files():
	files_to_compare = [
		"D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx\\units\\skel_dragon\\unit_skyfire_drake.drs", # Original
		"D:\\Games\\Skylords Reborn\\bf1\\gfx\\units\\skel_dragon\\unit_skyfire_drake.drs", # Modified
	]

	# We will compare the two files Datablock by Datablock. First we would need to parse the DRS files though.
	original_reader: BufferedReader = open(files_to_compare[0], 'rb')
	modified_reader: BufferedReader = open(files_to_compare[1], 'rb')

	# Read the header of the DRS files
	original_drs_header = read_drs_header(original_reader)
	modified_drs_header = read_drs_header(modified_reader)

	# Read the DRS files
	original_drs_data = read_drs_file(original_reader, original_drs_header)
	modified_drs_data = read_drs_file(modified_reader, modified_drs_header)

	# Compare the DRS files value by value (not in header)
	print("Comparing the node information")
	compare_node_infos(original_drs_data, modified_drs_data)
	print("Comparing the nodes")
	compare_nodes(original_drs_data, modified_drs_data)
	print("Comparing the data")
	compare_data(original_drs_data, modified_drs_data, original_reader, modified_reader)

	# Close the files
	original_reader.close()
	modified_reader.close()

def get_all_drs_files(root_folder: str) -> list:
	drs_files = []
	for dirpath, _, filenames in os.walk(root_folder):
		for file in filenames:
			if file.endswith(".drs"):
				drs_files.append(os.path.join(dirpath, file))
	return drs_files

def extract_type_from_path(file_path: str) -> str:
	# Extract type from the path (e.g., "buildings", "effects", etc.)
	base_parts = file_path.split(os.sep)
	for part in base_parts:
		if part in ["buildings", "editor", "effects", "fortification", "generator", "monument", "movies", "objects", "terrain", "ui", "units", "vis"]:
			return part
	return "unknown"

def create_statistics(drs_data_list: list):
	node_combination_stats = {}
	
	for drs_data in drs_data_list:
		node_hierarchy = drs_data["node_hierarchy"]
		file_type = extract_type_from_path(drs_data["file_path"])

		# Track combinations of node names
		combination = [file_type]
		for node in node_hierarchy:
			combination.append(node["name"] + str(node["info_index"]))
		combination = tuple(combination)
		if combination in node_combination_stats:
			node_combination_stats[combination] += 1
		else:
			node_combination_stats[combination] = 1

	# Sort the statistics by this order: "buildings", "editor", "effects", "fortification", "generator", "monument", "movies", "objects", "terrain", "ui", "units", "vis"
	node_combination_stats = dict(sorted(node_combination_stats.items(), key=lambda item: item[0][0]))

	# Print statistics about node combinations
	for combination, count in node_combination_stats.items():
		print(f"{combination}, Count: {count}")

def read_and_analyze_drs_files(root_folder: str):
	drs_files = get_all_drs_files(root_folder)
	drs_data_list = []

	for file_path in drs_files:
		with open(file_path, 'rb') as reader:
			header = read_drs_header(reader)
			drs_data = read_drs_file(reader, header)
			drs_data["file_path"] = file_path
			drs_data_list.append(drs_data)

	# Create statistics about the order of nodes
	create_statistics(drs_data_list)

if __name__ == "__main__":
	# compare_files()
	root_folder = "D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx"
	read_and_analyze_drs_files(root_folder)
