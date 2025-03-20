from io import BufferedReader
import os


def read_drs_header(reader: BufferedReader) -> dict:
    header = {
        "magic": reader.read(4),
        "number_of_models": int.from_bytes(reader.read(4), byteorder="little"),
        "node_information_offset": int.from_bytes(reader.read(4), byteorder="little"),
        "node_hierarchy_offset": int.from_bytes(reader.read(4), byteorder="little"),
        "node_count": int.from_bytes(reader.read(4), byteorder="little"),
    }

    return header


def read_cdrw_locator(reader: BufferedReader) -> dict:
    magic: int = int.from_bytes(reader.read(4), byteorder="little", signed=True)
    version: int = int.from_bytes(reader.read(4), byteorder="little")
    length: int = int.from_bytes(reader.read(4), byteorder="little")
    slocators = []
    if magic != 281702437:
        print(f"CDRW Locator magic is not correct: {magic}")
        return None

    for _ in range(length):
        cmat_coordinate_system = int.from_bytes(reader.read(48), byteorder="little")
        class_id: int = int.from_bytes(reader.read(4), byteorder="little")
        sub_id: int = int.from_bytes(reader.read(4), byteorder="little", signed=True)
        if sub_id < 0:
            sub_id = 1000
        file_name_length: int = int.from_bytes(reader.read(4), byteorder="little")
        file_name: str = reader.read(file_name_length).decode("utf-8")
        uk_int: int = int.from_bytes(reader.read(4), byteorder="little")

        slocator = {
            "cmat_coordinate_system": cmat_coordinate_system,
            "class_id": class_id,
            "sub_id": sub_id,
            "file_name": file_name,
        }
        if version == 5:
            slocator["uk_int"] = uk_int
        slocators.append(slocator)

    return {
        "magic": magic,
        "version": version,
        "length": length,
        "slocators": slocators,
    }


def read_drs_file(reader: BufferedReader, header: dict) -> dict:
    # Move to the node information offset
    reader.seek(header["node_information_offset"])
    node_information = []

    # Read the root Node: 32 bytes
    rote_node = {
        "zeroes": reader.read(16),
        "neg_one": int.from_bytes(reader.read(4), byteorder="little"),
        "one": int.from_bytes(reader.read(4), byteorder="little"),
        "node_information_count": int.from_bytes(reader.read(4), byteorder="little"),
        "zero": int.from_bytes(reader.read(4), byteorder="little"),
    }

    # Read the node information
    for _ in range(rote_node["node_information_count"]):
        node = {
            "magic": int.from_bytes(reader.read(4), byteorder="little", signed=True),
            "identifier": int.from_bytes(reader.read(4), byteorder="little"),
            "offset": int.from_bytes(reader.read(4), byteorder="little"),
            "node_size": int.from_bytes(reader.read(4), byteorder="little"),
            "spacer": reader.read(16),
        }

        node_information.append(node)

    # Move to the node hierarchy offset
    reader.seek(header["node_hierarchy_offset"])
    node_hierarchy = []

    # Read the root Node: 21 bytes
    root_node = {
        "identifier": int.from_bytes(reader.read(4), byteorder="little"),
        "unknown": int.from_bytes(reader.read(4), byteorder="little"),
        "length": int.from_bytes(reader.read(4), byteorder="little"),
    }

    # Read the name of the root node as a string
    root_node["name"] = reader.read(root_node["length"]).decode("utf-8")
    node_hierarchy.append(root_node)

    # Read the node hierarchy
    for _ in range(header["node_count"] - 1):
        node = {
            "info_index": int.from_bytes(reader.read(4), byteorder="little"),
            "length": int.from_bytes(reader.read(4), byteorder="little"),
        }

        # Read the name of the node as a string
        node["name"] = reader.read(node["length"]).decode("utf-8")

        # Read the Spacer 0
        node["spacer"] = reader.read(4)

        node_hierarchy.append(node)

    cdrw_locator = None
    # Find the offset and size of the CDRW Locator by checking the node info and node hierarchy. Node hierarchy has the name and info index, while node info has the offset and size.
    for node in node_hierarchy:
        if node["name"] == "CDrwLocatorList":
            # get the node by accessing the array at index -1
            cdrw_locator_info = node_information[node["info_index"] - 1]
            if cdrw_locator_info is not None:
                # Read the CDRW Locator
                reader.seek(cdrw_locator_info["offset"])
                try:
                    cdrw_locator = read_cdrw_locator(reader)

                    if cdrw_locator is not None:
                        for locator in cdrw_locator["slocators"]:
                            if locator["file_name"] != "":
                                print(
                                    f"{reader.name} -> locator file name: {locator['file_name']} -> class id: {locator['class_id']} -> sub id: {locator['sub_id']}"
                                )
                except Exception as e:
                    print(f"Error reading CDRW Locator in file: {reader.name}")

    # Return the DRS file
    return {
        "node_information": node_information,
        "node_hierarchy": node_hierarchy,
        "cdrw_locator": cdrw_locator,
    }


def compare_node_infos(original: dict, modified: dict):
    if len(original["node_information"]) != len(modified["node_information"]):
        print(
            f"[ERROR] The number of node information is different: {len(original['node_information'])} != {len(modified['node_information'])}"
        )
        return False

    for i in range(len(original["node_information"])):
        node_info = original["node_information"][i]
        # as we changed order in the modified file, we need to find the corresponding node info by magic
        modified_node_info = next(
            (
                x
                for x in modified["node_information"]
                if x["magic"] == node_info["magic"]
            ),
            None,
        )

        if modified_node_info is None:
            print(
                f"[ERROR] The node information with magic {node_info['magic']} was not found in the modified file."
            )
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
            print(
                f"[ERROR] The node size of the node information with magic {node_info['magic']} is different: {node_info['node_size']} != {modified_node_info['node_size']}"
            )

    if len(original["node_hierarchy"]) != len(modified["node_hierarchy"]):
        print(
            f"[ERROR] The number of node hierarchy is different: {len(original['node_hierarchy'])} != {len(modified['node_hierarchy'])}"
        )


def compare_nodes(original: dict, modified: dict):
    if len(original["node_hierarchy"]) != len(modified["node_hierarchy"]):
        print(
            f"[ERROR] The number of nodes is different: {len(original['node_hierarchy'])} != {len(modified['node_hierarchy'])}"
        )
        return False

    for i in range(len(original["node_hierarchy"])):
        node = original["node_hierarchy"][i]
        # as we changed order in the modified file, we need to find the corresponding node by name
        modified_node = next(
            (x for x in modified["node_hierarchy"] if x["name"] == node["name"]), None
        )

        if modified_node is None:
            print(
                f"[ERROR] The node with info index {node['info_index']} was not found in the modified file."
            )
            # Show the nodes
            print(f"Original: {node}")
            print(f"Modified: {modified['node_hierarchy']}")
            return False

        if node["info_index"] != modified_node["info_index"]:
            # print(f"[ERROR] The info index of the node with info index {node['info_index']} is different: {node['info_index']} != {modified_node['info_index']}")
            pass

        if node["spacer"] != modified_node["spacer"]:
            print(
                f"[ERROR] The spacer of the node with info index {node['info_index']} is different: {node['spacer']} != {modified_node['spacer']}"
            )


def compare_data(
    original: dict,
    modified: dict,
    _original_reader: BufferedReader,
    _modified_reader: BufferedReader,
):
    for i in range(len(original["node_information"])):
        node_info = original["node_information"][i]
        # as we changed order in the modified file, we need to find the corresponding node info by magic
        modified_node_info = next(
            (
                x
                for x in modified["node_information"]
                if x["magic"] == node_info["magic"]
            ),
            None,
        )

        # Original Data
        _original_reader.seek(node_info["offset"])
        original_data = _original_reader.read(node_info["node_size"])

        # Modified Data
        _modified_reader.seek(modified_node_info["offset"])
        modified_data = _modified_reader.read(modified_node_info["node_size"])

        if original_data != modified_data:
            print(
                f"[ERROR] The data of the node information with magic {node_info['magic']} is different."
            )
            # Show the data
            print(f"Original: {original_data}")
            print(f"Modified: {modified_data}")
            return False

        # byte by byte comparison
        for j in range(len(original_data)):
            if original_data[j] != modified_data[j]:
                print(
                    f"[ERROR] The data of the node information with magic {node_info['magic']} is different at byte {j}."
                )
                # Show the data
                print(f"Original: {original_data}")
                print(f"Modified: {modified_data}")
                return False


def compare_files():
    files_to_compare = [
        "D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx\\units\\skel_dragon\\unit_skyfire_drake.drs",  # Original
        "D:\\Games\\Skylords Reborn\\bf1\\gfx\\units\\skel_dragon\\unit_skyfire_drake.drs",  # Modified
    ]

    # We will compare the two files Datablock by Datablock. First we would need to parse the DRS files though.
    original_reader: BufferedReader = open(files_to_compare[0], "rb")
    modified_reader: BufferedReader = open(files_to_compare[1], "rb")

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
        if part in [
            "buildings",
            "editor",
            "effects",
            "fortification",
            "generator",
            "monument",
            "movies",
            "objects",
            "terrain",
            "ui",
            "units",
            "vis",
        ]:
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
    node_combination_stats = dict(
        sorted(node_combination_stats.items(), key=lambda item: item[0][0])
    )

    # Print statistics about node combinations
    for combination, count in node_combination_stats.items():
        print(f"{combination}, Count: {count}")


def create_locator_stats(drs_data_list: list):
    class_locator_stats = {}

    for drs_data in drs_data_list:
        cdrw_locator = drs_data["cdrw_locator"]
        if cdrw_locator is not None:
            for locator in cdrw_locator["slocators"]:
                # Create or reuse the index for the class id. If new create a new dictionary base dof the sub id
                if not locator["class_id"] in class_locator_stats:
                    class_locator_stats[locator["class_id"]] = {}

                if not locator["sub_id"] in class_locator_stats[locator["class_id"]]:
                    # create a new sub id array
                    class_locator_stats[locator["class_id"]][locator["sub_id"]] = []

                # Write the locator to the list
                fileName = drs_data["file_path"]
                fileName = fileName.split("\\")[-1]
                class_locator_stats[locator["class_id"]][locator["sub_id"]].append(
                    {
                        "drs file name": fileName,
                        "locator file name": locator["file_name"],
                    }
                )

    # Print statistics about locators
    # Write to file
    # Sort the lists by class id
    class_locator_stats = dict(
        sorted(class_locator_stats.items(), key=lambda item: item[0])
    )

    # Purge duplicates
    with open("locator_stats.txt", "w") as file:
        seen = set()  # Set to store unique entries
        for class_id, sub_ids in class_locator_stats.items():
            # Sort the lists by sub id
            sub_ids = dict(sorted(sub_ids.items(), key=lambda item: item[0]))
            for sub_id, file_names in sub_ids.items():
                for data in file_names:
                    drs_file_name = data["drs file name"]
                    locator_file_name = data["locator file name"]
                    if sub_id == 1000:
                        sub_id = -1

                    # Create a unique identifier for each entry
                    entry = (class_id, sub_id, drs_file_name, locator_file_name)

                    # Only write if the entry is unique
                    if entry not in seen:
                        seen.add(entry)
                        file.write(
                            f"Class ID: {class_id}, Sub ID: {sub_id}, DRS File Name: {drs_file_name}, Locator File Name: {locator_file_name}\n"
                        )
                    else:
                        print(f"Duplicate entry found: {entry}")

    # No need to explicitly close the file; 'with' handles it


def read_and_analyze_drs_files(root_folder: str):
    drs_files = get_all_drs_files(root_folder)
    drs_data_list = []

    for file_path in drs_files:
        with open(file_path, "rb") as reader:
            header = read_drs_header(reader)
            drs_data = read_drs_file(reader, header)
            drs_data["file_path"] = file_path
            drs_data_list.append(drs_data)

    # Create statistics about the order of nodes
    # create_statistics(drs_data_list)
    create_locator_stats(drs_data_list)


if __name__ == "__main__":
    # compare_files()
    # root_folder = "D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx"
    # read_and_analyze_drs_files(root_folder)
    pass
