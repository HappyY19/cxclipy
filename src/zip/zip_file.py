import os
import hashlib
import pathlib
from zipfile import ZipFile, ZIP_DEFLATED
from src.log import logger


def group_str_by_wildcard_character(exclusions):
    """

    Args:
        exclusions (str): commaseparated string
        for example, "*.min.js,readme,*.txt,test*,*doc*"

    Returns:
        dict
        {
         "prefix_list": ["test"], # wildcard (*) at end, but not start
         "suffix_list": [".min.js", ".txt"],  # wildcard (*) at start, but not end
         "inner_List": ["doc"],   # wildcard (*) at both end and start
         "word_list": ["readme"]  # no wildcard
        }
    """
    result = {
        "prefix_list": [],
        "suffix_list": [],
        "inner_List": [],
        "word_list": [],
    }
    if not exclusions:
        return result
    string_list = exclusions.lower().split(',')
    string_set = set(string_list)
    for string in string_set:
        new_string = string.strip()
        # ignore any string that with slash or backward slash
        if '/' in new_string or "\\" in new_string:
            continue
        if new_string.endswith("*") and not new_string.startswith("*"):
            result["prefix_list"].append(new_string.rstrip("*"))
        elif new_string.startswith("*") and not new_string.endswith("*"):
            result["suffix_list"].append(new_string.lstrip("*"))
        elif new_string.endswith("*") and new_string.startswith("*"):
            result["inner_List"].append(new_string.strip("*"))
        else:
            result["word_list"].append(new_string)
    return result


def should_be_excluded(exclusions, target):
    """

    Args:
        exclusions (str):
        target (str):

    Returns:

    """
    result = False
    target = target.lower()
    groups_of_exclusions = group_str_by_wildcard_character(exclusions)
    if target.startswith(tuple(groups_of_exclusions["prefix_list"])):
        result = True
    if target.endswith(tuple(groups_of_exclusions["suffix_list"])):
        result = True
    if any([True if inner_text in target else False for inner_text in groups_of_exclusions["inner_List"]]):
        result = True
    if target in groups_of_exclusions["word_list"]:
        result = True
    return result


def add_java_file(location_path):
    file_name = location_path + "/HelloWorld.java"
    with open(file=file_name, mode="w") as file:
        file.write(
            """class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello World!");
    }
}
            """
        )


def create_zip_file_from_location_path(
        location_path_str: str,
        project_id: str,
        exclude_folders_str: bool = None,
        exclude_files_str: bool = None
) -> tuple:
    """

    Args:
        location_path_str (str):
        project_id (str):
        exclude_folders_str (str): comma separated string
        exclude_files_str (str): comma separated string

    Returns:
        str (ZIP file path)
    """
    logger.info(f"creating zip file by zip the source code folder: {location_path_str}")
    exclude_folders = ".*,bin,target,images,Lib,node_modules"
    exclude_files = "*.min.js"
    if exclude_folders_str is not None:
        exclude_folders += ","
        exclude_folders += exclude_folders_str
    if exclude_files_str is not None:
        exclude_files += ","
        exclude_files += exclude_files_str

    from pathlib import Path
    import tempfile
    temp_dir = tempfile.gettempdir()
    path = Path(location_path_str)
    if not path.exists():
        raise FileExistsError(f"{location_path_str} does not exist, abort scan")
    absolute_path_str = str(os.path.normpath(path.absolute()))
    add_java_file(absolute_path_str)
    file_path = f"{temp_dir}/{project_id}.zip"
    with ZipFile(file_path, "w", ZIP_DEFLATED) as zip_file:
        root_len = len(absolute_path_str) + 1
        for base, dirs, files in os.walk(absolute_path_str):
            path_folders = base.split(os.sep)
            if any([should_be_excluded(exclude_folders, folder) for folder in path_folders]):
                continue
            for file in files:
                file_lower_case = file.lower()
                if should_be_excluded(exclude_files, file_lower_case):
                    continue
                fn = os.path.join(base, file)
                zip_file.write(fn, fn[root_len:])
    logger.info(f"ZIP file created: {file_path}")
    sha_256_hash = calculate_sha_256_hash(file_path)
    return file_path, sha_256_hash


def calculate_sha_256_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    value = sha256_hash.hexdigest()
    logger.info(f"the zip file {file_path} SHA256 value: {value}")
    return value


def delete_zip_file(zip_file_path: str):
    logger.info(f"start deleting zip file: {zip_file_path}")
    pathlib.Path(zip_file_path).unlink()
    logger.info(f"Finish deleting zip file: {zip_file_path}")
