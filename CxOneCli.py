"""
This a CLI script. It can be converted to binary file by using pyinstaller

pyinstaller -y -F --clean CxOneCli.py

Sample usage
/home/happy/Documents/CxCliPy/dist/CxCliPy scan --cxsast_base_url http://192.168.3.84 --cxsast_username Admin \
--cxsast_password *** --preset "ASA Premium" --incremental False --location_type Folder \
--location_path /home/happy/Documents/JavaVulnerableLab \
--project_name /CxServer/happy-2022-11-21 --exclude_folders "test,integrationtest" --exclude_files "*min.js" \
--report_csv cx-report.csv \
--full_scan_cycle 10



scan --cxone_access_control_url https://eu.iam.checkmarx.net --cxone_server https://eu.ast.checkmarx.net --cxone_tenant_name asean_2021_08 --cxone_grant_type refresh_token --cxone_refresh_token "****" --preset "ASA Premium"  --incremental false --location_path /home/happy/Documents/SourceCode/github/java/JavaVulnerableLab --project_name happy-test-2022-04-20 --branch master --exclude_folders "test,integrationtest" --exclude_files "*min.js" --report_csv cx-report.csv --full_scan_cycle 10 --cxone_proxy http://127.0.0.1:1081

"""
import pathlib
import time
import os
from os.path import exists
from zipfile import ZipFile, ZIP_DEFLATED
import logging
import csv
from urllib.parse import urlencode
from CheckmarxPythonSDK.CxOne.AccessControlAPI import (
    get_group_by_name
)
from CheckmarxPythonSDK.CxOne.KeycloakAPI import (
    create_group,
    create_subgroup,
)

# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


def get_cx_supported_file_extensions():
    return [
        '.apex', '.apexp', '.asax', '.ascx', '.asp', '.aspx', '.bas', '.bdy', '.c', '.c++', '.cc', '.cgi', '.cls',
        '.component', '.conf', '.config', '.cpp', '.cs', '.cshtml', '.csproj', '.ctl', '.ctp', '.cxx', '.dsr', '.ec',
        '.erb', '.fnc', '.frm', '.go', '.gradle', '.groovy', '.gsh', '.gsp', '.gtl', '.gvy', '.gy', '.h', '.h++',
        '.handlebars', '.hbs', '.hh', '.hpp', '.htm', '.html', '.hxx', '.inc', '.jade', '.java', '.javasln', '.js',
        '.jsf', '.json', '.jsp', '.jspf', '.lock', '.m', '.master', '.-meta.xml', '.mf', '.object', '.page', '.pc',
        '.pck', '.php', '.php3', '.php4', '.php5', '.phtm', '.phtml', '.pkb', '.pkh', '.pks', '.pl', '.plist', '.pls',
        '.plx', '.pm', '.prc', '.project', '.properties', '.psgi', '.py', '.rb', '.report', '.rhtml', '.rjs', '.rxml',
        '.scala', '.sln', '.spc', '.sqb', '.sqf', '.sqh', '.sql', '.sqp', '.sqt',
        '.sqtb', '.sqth', '.sqv', '.swift', '.tag', '.tgr', '.tld', '.tpb', '.tpl', '.tps', '.trg', '.trigger', '.ts',
        '.tsx', '.twig', '.vb', '.vbp', '.vbs', '.wod', '.workflow', '.xaml', '.xhtml', '.xib', '.xml', '.xsaccess',
        '.xsapp', '.xsjs', '.xsjslib', '-meta.xml', '.rpgle', '.pug', '.vue', '.mustache', '.cbl', '.jsx', '.apxc',
        '.cpy', '.kt', '.rpg38', '.pro', '.csv', '.ftl', '.evt', '.sqlrpg', '.eco', '.cmp', '.txt', '.pco', '.ac',
        '.cob', '.rpg', '.cmake', '.sqlrpgle', '.tex', '.vm', '.kts', '.latex', '.am', '.app', ".yml", ".yaml", ".rs",
        ".dart", ".dspf", ".vbproj", ".toml", ".cfg", ".sbt", ".private", ".resolved", ".mod", ".sum", ".snapshot"
    ]


def get_command_line_arguments():
    """

    Returns:
        Namespace
    """
    import argparse
    description = 'A simple command-line interface for CxSAST in Python.'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('scan')
    parser.add_argument('--cxone_access_control_url', required=True, help="CxOne iam url")
    parser.add_argument('--cxone_server', required=True, help="CxOne server url")
    parser.add_argument('--cxone_tenant_name', required=True, help="CxOne tenant name")
    parser.add_argument('--cxone_grant_type', required=True, help="CxOne grant type, refresh_token")
    parser.add_argument('--cxone_refresh_token', required=True, help="CxOne API Key")
    parser.add_argument('--preset', required=True, help="The preset (rule set) name")
    parser.add_argument('--incremental', default=False, help="Set it True for incremental scan")
    parser.add_argument('--location_path', required=True, help="Source code folder absolute path")
    parser.add_argument('--project_name', required=True, help="Checkmarx project name")
    parser.add_argument('--branch', required=True, help="git repo branch to scan")
    parser.add_argument('--scanners', default="sast,sca,kics,apisec,containers",
                        help="scanners: sast,sca,kics,apisec,containers")
    parser.add_argument('--exclude_folders', help="exclude folders")
    parser.add_argument('--exclude_files', help='exclude files')
    parser.add_argument('--report_csv', default=None, help="csv report file path")
    parser.add_argument('--full_scan_cycle', default=10,
                        help="Defines the number of incremental scans to be performed, before performing a periodic "
                             "full scan")
    parser.add_argument('--cxone_proxy', help="proxy URL")
    return parser.parse_known_args()


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


def create_zip_file_from_location_path(location_path_str: str, project_name: str,
                                       exclude_folders_str=None, exclude_files_str=None):
    """

    Args:
        location_path_str (str):
        project_name (str):
        exclude_folders_str (str): comma separated string
        exclude_files_str (str): comma separated string

    Returns:
        str (ZIP file path)
    """
    exclude_folders = ".*,bin,target,images,Lib,node_modules"
    exclude_files = ".*,*.min.js"
    if exclude_folders_str is not None:
        exclude_folders += ","
        exclude_folders += exclude_folders_str
    if exclude_files_str is not None:
        exclude_files += ","
        exclude_files += exclude_files_str

    from pathlib import Path
    import tempfile
    temp_dir = tempfile.gettempdir()
    extensions = get_cx_supported_file_extensions()
    path = Path(location_path_str)
    if not path.exists():
        raise FileExistsError(f"{location_path_str} does not exist, abort scan")
    absolute_path_str = str(os.path.normpath(path.absolute()))
    file_path = f"{temp_dir}/cx_{project_name}.zip"
    with ZipFile(file_path, "w", ZIP_DEFLATED) as zip_file:
        root_len = len(absolute_path_str) + 1
        for base, dirs, files in os.walk(absolute_path_str):
            path_folders = base.split(os.sep)
            if any([should_be_excluded(exclude_folders, folder) for folder in path_folders]):
                continue
            for file in files:
                file_lower_case = file.lower()
                if file_lower_case not in ["dockerfile", "cartfile", "podfile", "gemfile", "cpanfile"]:
                    if not file_lower_case.endswith(tuple(extensions)):
                        continue
                    if should_be_excluded(exclude_files, file_lower_case):
                        continue
                fn = os.path.join(base, file)
                zip_file.write(fn, fn[root_len:])
    return file_path


def cx_scan_from_local_zip_file(preset_name: str,
                                project_name: str,
                                branch: str,
                                zip_file_path: str,
                                incremental: bool = False,
                                full_scan_cycle=10,
                                group_ids=None,
                                scanners=None):
    """

    Args:
        preset_name (str):
        project_name (str):
        branch (str):
        zip_file_path (str):
        incremental (bool):
        full_scan_cycle (int):
        group_ids (list of str):
        scanners (list of str):

    Returns:
        return scan id if scan finished, otherwise return None
    """
    from CheckmarxPythonSDK.CxOne import (
        get_a_list_of_projects,
        create_a_project,
        create_a_pre_signed_url_to_upload_files,
        upload_zip_content_for_scanning,
        create_scan,
        get_a_list_of_scans,
        get_a_scan_by_id,
        get_summary_for_many_scans,
    )
    from CheckmarxPythonSDK.CxOne.dto import (
        ProjectInput,
        ScanInput,
        Upload,
        Project,
        ScanConfig,
    )

    if not exists(zip_file_path):
        logger.error("[ERROR]: zip file not found. Abort scan.")
        exit(1)

    project_collection = get_a_list_of_projects(name=project_name)

    if not project_collection.projects:
        logger.info("project does not exist. create project")
        project = create_a_project(
            project_input=ProjectInput(
                name=project_name,
                groups=group_ids
            )
        )
        project_id = project.id
        logger.info(f"new project name {project_name} with project_id: {project_id} created.")
    else:
        project_id = project_collection.projects[0].id
    logger.info(f"project id: {project_id}")
    scans_from_this_project_and_branch = get_a_list_of_scans(project_id=project_id, branch=branch)
    number_of_scans = scans_from_this_project_and_branch.filteredTotalCount
    remainder = number_of_scans % full_scan_cycle
    if remainder == 0:
        incremental = False
    logger.info("create new scan")
    logger.info(f"The sast scan type will be: {'incremental' if incremental else 'full'} ")
    logger.info("create a pre signed url to upload zip file")
    url = create_a_pre_signed_url_to_upload_files()
    logger.info(f"upload url created: {url}")
    logger.info("begin to upload zip file")
    upload_source_code_successful = upload_zip_content_for_scanning(
        upload_link=url,
        zip_file_path=zip_file_path,
    )
    if not upload_source_code_successful:
        logger.error("[ERROR]: Failed to upload zip file. Abort scan.")
        exit(1)
    logger.info("finish upload zip file")
    scan_configs = []
    for scanner in scanners:
        if scanner == "sast":
            scan_configs.append(
                ScanConfig("sast",
                           {
                               "incremental": "true" if incremental else "false",
                               "presetName": preset_name
                           }
                           )
            )
        else:
            scan_configs.append(ScanConfig(scanner))
    scan_input = ScanInput(
        scan_type="upload",
        handler=Upload(upload_url=url, branch=branch),
        project=Project(project_id=project_id),
        configs=scan_configs,
    )
    scan = create_scan(scan_input=scan_input)
    scan_id = scan.id
    logger.info("scan_id : {}".format(scan_id))

    logger.info("get scan details by scan id, report scan status")
    while True:
        scan = get_a_scan_by_id(scan_id=scan_id)
        scan_status = scan.status
        logger.info("scan_status: {}".format(scan_status))
        if scan_status in ["Completed", "Partial"]:
            break
        elif scan_status in ["Failed", "Canceled"]:
            return None
        time.sleep(10)

    logger.info("get statistics results by scan id")
    statistics = get_summary_for_many_scans(scan_ids=[scan_id])
    statistics = statistics.get("scansSummaries")[0].sastCounters.get('severityStatusCounters')
    high_list = [item for item in statistics if item.get("severity") == "HIGH"]
    medium_list = [item for item in statistics if item.get("severity") == "MEDIUM"]
    low_list = [item for item in statistics if item.get("severity") == "LOW"]
    statistics_updated = {
        "High": high_list[0].get("counter") if high_list else 0,
        "Medium": medium_list[0].get("counter") if medium_list else 0,
        "Low": low_list[0].get("counter") if low_list else 0,
    }
    logger.info(f"statistics: {statistics_updated}")
    return project_id, scan_id


def generate_report(cxone_server, project_id, scan_id: str, report_file_path: str):
    """

    Args:
        cxone_server (str):
        project_id (str):
        scan_id (str):
        report_file_path (str):

    Returns:

    """
    logger.info("start report generation")
    from CheckmarxPythonSDK.CxOne import get_sast_results_by_scan_id
    offset = 0
    limit = 500
    sast_results_collection = get_sast_results_by_scan_id(scan_id=scan_id, offset=offset, limit=limit)
    total_count = int(sast_results_collection.get("totalCount"))
    sast_results = sast_results_collection.get("results")
    if total_count > limit:
        number_of_whole_request = (total_count // limit) - 1
        while number_of_whole_request > 0:
            offset += 1
            sast_results_collection = get_sast_results_by_scan_id(scan_id=scan_id, offset=offset, limit=limit)
            sast_results.extend(sast_results_collection.get("results"))
            number_of_whole_request -= 1
        remainder = total_count % limit
        if remainder > 0:
            offset += 1
            sast_results_collection = get_sast_results_by_scan_id(scan_id=scan_id, offset=offset, limit=limit)
            sast_results.extend(sast_results_collection.get("results"))

    report_content = []
    for result in sast_results:
        link = f"{cxone_server}/results/{project_id}/{scan_id}/sast"
        report_content.append(
            {
                "QueryID": result.query_id,
                "QueryIDStr": result.query_id_str,
                "LanguageName": result.language_name,
                "QueryGroup": result.query_group,
                "CweID": result.cwe_id,
                "ConfidenceLevel": result.confidence_level,
                "Compliances": result.compliances,
                "FirstScanID": result.first_scan_id,
                "FirstFoundAt": result.first_found_at,
                "Status": result.status,
                "Query": result.query_name,
                "SrcFileName": result.nodes[0].fileName,
                "Line": result.nodes[0].line,
                "Column": result.nodes[0].column,
                "NodeId": result.nodes[0].nodeHash,
                "Name": result.nodes[0].fullName,
                "DestFileName": result.nodes[-1].fileName,
                "DestLine": result.nodes[-1].line,
                "DestColumn": result.nodes[-1].column,
                "DestNodeId": result.nodes[-1].nodeHash,
                "DestName": result.nodes[-1].fullName,
                "Result State": result.state,
                "Result Severity": result.severity,
                "Assigned To": "",
                "Comment": "",
                "Link": link,
                "Result Status": result.status,
                "Detection Date": result.found_at,
                "SimilarityID": result.similarity_id
            }
        )
    with open(report_file_path, 'w', newline='') as csvfile:
        fieldnames = ["QueryID", "QueryIDStr", "LanguageName", "QueryGroup", "CweID", "ConfidenceLevel", "Compliances",
                      "FirstScanID", "FirstFoundAt", "Status",
                      "Query", "SrcFileName", "Line", "Column", "NodeId", "Name", "DestFileName", "DestLine",
                      "DestColumn", "DestNodeId", "DestName", "Result State", "Result Severity", "Assigned To",
                      "Comment", "Link", "Result Status", "Detection Date", "SimilarityID"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in report_content:
            writer.writerow(result)
    logger.info("report generated successfully")


def run_scan_and_generate_reports(arguments):
    cxone_access_control_url = arguments.cxone_access_control_url
    cxone_server = arguments.cxone_server
    cxone_tenant_name = arguments.cxone_tenant_name
    cxone_grant_type = arguments.cxone_grant_type
    cxone_proxy = arguments.cxone_proxy
    preset = arguments.preset
    incremental = False if arguments.incremental.lower() == "false" else True
    location_path = arguments.location_path
    branch = arguments.branch
    exclude_folders = arguments.exclude_folders
    exclude_files = arguments.exclude_files
    report_csv = arguments.report_csv
    full_scan_cycle = int(arguments.full_scan_cycle)
    scanners = [scanner for scanner in arguments.scanners.split(",")]

    project_path_list = arguments.project_name.split("/")
    project_name = project_path_list[-1]
    group_full_name = "/".join(project_path_list[0: len(project_path_list) - 1])

    logger.info(
        f"cxone_access_control_url: {cxone_access_control_url}\n"
        f"cxone_server: {cxone_server}\n"
        f"cxone_tenant_name: {cxone_tenant_name}\n"
        f"cxone_grant_type: {cxone_grant_type}\n"
        f"cxone_proxy: {cxone_proxy}\n"
        f"preset: {preset}\n"
        f"incremental: {incremental}\n"
        f"location_path: {location_path}\n"
        f"project_name: {project_name}\n"
        f"branch: {branch}\n"
        f"exclude_folders: {exclude_folders}\n"
        f"exclude_files: {exclude_files}\n"
        f"report_csv: {report_csv}\n"
        f"full_scan_cycle: {full_scan_cycle}\n"
        f"group_full_name: {group_full_name}\n"
        f"scanners: {scanners}\n"
    )

    group_names = [item for item in group_full_name.split("/")]
    group = get_group_by_name(realm=cxone_tenant_name, group_name=group_full_name)
    if not group:
        for index, gr in enumerate(group_names):
            if index == 0:
                group = get_group_by_name(realm=cxone_tenant_name, group_name=gr)
                if not group:
                    logger.info(f"root group {gr} not exist.")
                    logger.info(f"start creating root group: {gr}")
                    create_group(realm=cxone_tenant_name, group_name=gr)
                    logger.info(f"finish creating root group: {gr}")
            else:
                parent_group_path = "/".join(group_names[0: index])
                logger.info(f"parent group path: {parent_group_path}")
                group_path = "/".join(group_names[0: index + 1])
                logger.info(f"current group path: {group_path}")
                group = get_group_by_name(realm=cxone_tenant_name, group_name=group_path)
                if not group:
                    logger.info(f"current group {group_path} not exist.")
                    logger.info(f"start creating sub group: {group_path}, parent group name: {parent_group_path}")
                    parent_group = get_group_by_name(realm=cxone_tenant_name, group_name=parent_group_path)
                    create_subgroup(realm=cxone_tenant_name, group_id=parent_group.id, subgroup_name=gr)
                    logger.info(f"finish creating sub group: {group_path}, parent group name: {parent_group_path}")
    group = get_group_by_name(realm=cxone_tenant_name, group_name=group_full_name)
    group_id = group.id
    group_ids = [group_id]

    logger.info(f"creating zip file by zip the source code folder: {location_path}")
    zip_file_path = create_zip_file_from_location_path(location_path, project_name, exclude_folders_str=exclude_folders,
                                                       exclude_files_str=exclude_files)
    logger.info(f"ZIP file created: {zip_file_path}")
    project_id, scan_id = cx_scan_from_local_zip_file(preset_name=preset, project_name=project_name,
                                          branch="master",
                                          zip_file_path=zip_file_path, incremental=incremental,
                                          full_scan_cycle=full_scan_cycle, group_ids=group_ids,
                                          scanners=scanners)

    if scan_id is None:
        logger.info("Scan did not finish successfully, exit!")
        return

    logger.info(f"deleting zip file: {zip_file_path}")
    pathlib.Path(zip_file_path).unlink()

    generate_report(cxone_server=cxone_server, project_id=project_id, scan_id=scan_id, report_file_path=report_csv)


if __name__ == '__main__':
    # get command line arguments
    cli_arguments = get_command_line_arguments()
    cli_arguments = cli_arguments[0]
    run_scan_and_generate_reports(cli_arguments)
