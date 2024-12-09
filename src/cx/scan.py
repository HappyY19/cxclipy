from time import sleep
from datetime import datetime, time, timedelta
from src.log import logger
from typing import List
from CheckmarxPythonSDK.CxOne import (
    create_a_pre_signed_url_to_upload_files,
    upload_zip_content_for_scanning,
    create_scan,
    get_a_scan_by_id,
    get_summary_for_many_scans,
)
from CheckmarxPythonSDK.CxOne.dto import (
    ScanInput,
    Upload,
    Project,
    ScanConfig,
    ScansCollection,
)
from os.path import exists

time_stamp_format = "%Y-%m-%dT%H:%M:%S.%fZ"


def should_create_new_scan(
        zip_file_path: str,
        scan_collection: ScansCollection,
        sha_256_hash: str,
        scan_commit_number: int,
        git_commit_history: List[dict],
        parallel_scan_cancel: bool,
) -> bool:
    result = True
    file_hash_list_from_tags = [scan.tags.get("SHA256") for scan in scan_collection.scans]
    scan_status_list = [scan.status.lower() for scan in scan_collection.scans]
    if not exists(zip_file_path):
        logger.error("[ERROR]: zip file not found. Abort scan.")
        result = False
    elif file_hash_list_from_tags and sha_256_hash in file_hash_list_from_tags:
        logger.info(f"identical code detected with SHA256 file hash: {sha_256_hash}, Cancel this scan request")
        result = False
    elif scan_collection.scans and scan_commit_number > 1 and git_commit_history:
        last_scan_tags = scan_collection.scans[0].tags
        commit_id = last_scan_tags.get("commit_id")
        commit_time = last_scan_tags.get("commit_time")
        if commit_id and commit_time:
            index_of_last_scan_commit_id_in_history = next((index for (index, d) in enumerate(git_commit_history)
                                                            if d["commit_id"] == commit_id), None)
            if index_of_last_scan_commit_id_in_history + 1 <= scan_commit_number:
                current_commit_id = git_commit_history[0].get("commit_id")
                logger.info(f"initiate scan by every {scan_commit_number} commits, "
                            f"last scan commit id: {commit_id}, "
                            f"current commit id: {current_commit_id}, "
                            f"make {scan_commit_number - index_of_last_scan_commit_id_in_history} "
                            f"more commit to initiate scan, Cancel this scan request")
                result = False
    elif parallel_scan_cancel and "running" in scan_status_list:
        logger.info("There are running scans.")
        logger.info("Parallel run controlled, Cancel this scan request")
        result = False
    return result


def create_scan_tags(
        sha_256_hash: str,
        sast_incremental: bool,
        preset: str,
        branch: str,
        sca_exploitable_path: bool,
        sca_last_sast_scan_time: int,
        git_commit_history: List[dict],
        scan_tag_key: List[str],
        scan_tag_value: List[str],
) -> dict:
    scan_tags = {
        "SHA256": sha_256_hash,
        "sast_incremental": str(sast_incremental),
        "preset": preset,
        "branch": branch,
        "sca_exploitable_path": str(sca_exploitable_path),
        "sca_last_sast_scan_time": str(sca_last_sast_scan_time),
    }
    if git_commit_history:
        scan_tags.update(
            {
                "commit_id": git_commit_history[0].get("commit_id"),
                "commit_time": git_commit_history[0].get("commit_time"),
                "committer": git_commit_history[0].get("committer"),
            }
        )
    if scan_tag_key:
        for index, key in enumerate(scan_tag_key):
            try:
                value = scan_tag_value[index]
            except IndexError:
                value = None
            scan_tags.update({key: value})
    logger.info(f"scan tags: {scan_tags}")
    return scan_tags


def create_scan_configs(
        scanners: List[str],
        sast_incremental: bool,
        preset: str,
        sca_exploitable_path: bool,
        sca_last_sast_scan_time: int
) -> List[ScanConfig]:
    scan_configs: List[ScanConfig] = []
    for scanner in scanners:
        if scanner == "sast":
            scan_configs.append(
                ScanConfig(
                    scan_type="sast", value={
                        "incremental": "true" if sast_incremental else "false",
                        "presetName": preset
                    }
                )
            )
        elif scanner == "sca":
            scan_configs.append(
                ScanConfig(
                    scan_type="sca", value={
                        "exploitablePath": "true" if sca_exploitable_path else "false",
                        "lastSastScanTime": f"{sca_last_sast_scan_time}",
                    }
                )
            )
        elif scanner == "microengines":
            scan_configs.append(
                ScanConfig(
                    scan_type="microengines", value={
                        "scorecard": "true",
                        "2ms": "true",
                    }
                )
            )
        else:
            scan_configs.append(ScanConfig(scan_type=scanner, value={}))
    logger.info(f"scan_configs: {[scan_config.as_dict() for scan_config in scan_configs]}")
    return scan_configs


def show_scan_statistics(scanners: List[str], scan_id: str):
    def show_scanner_statistics(scanner: str, statistics: dict):
        critical_list = [item for item in statistics if item.get("severity") == "CRITICAL"]
        high_list = [item for item in statistics if item.get("severity") == "HIGH"]
        medium_list = [item for item in statistics if item.get("severity") == "MEDIUM"]
        low_list = [item for item in statistics if item.get("severity") == "LOW"]
        scanner_result = {
            "Critical": critical_list[0].get("counter") if critical_list else 0,
            "High": high_list[0].get("counter") if high_list else 0,
            "Medium": medium_list[0].get("counter") if medium_list else 0,
            "Low": low_list[0].get("counter") if low_list else 0,
        }
        logger.info(f"{scanner} scan statistics: {scanner_result}")

    logger.info("get scan statistics results by scan id")
    result = get_summary_for_many_scans(scan_ids=[scan_id])
    scan_summaries = result.get("scansSummaries")
    if not scan_summaries:
        return
    results_summary = scan_summaries[0]
    if "sast" in scanners:
        sast_statistics = results_summary.sastCounters.get('severityStatusCounters')
        show_scanner_statistics(scanner="sast", statistics=sast_statistics)
    if "sca" in scanners:
        sca_statistics = results_summary.scaCounters.get('severityStatusCounters')
        show_scanner_statistics(scanner="sca", statistics=sca_statistics)
    if "apisec" in scanners:
        api_sec_statistics = results_summary.apiSecCounters.get('severityStatusCounters')
        show_scanner_statistics(scanner="apisec", statistics=api_sec_statistics)
    if "kics" in scanners:
        kics_statistics = results_summary.kicsCounters.get('severityStatusCounters')
        show_scanner_statistics(scanner="kics", statistics=kics_statistics)
    if "containers" in scanners:
        container_statistics = results_summary.scaContainersCounters.get('severityStatusCounters')
        show_scanner_statistics(scanner="containers", statistics=container_statistics)


def check_sast_scan_type(
        scan_collection: ScansCollection,
        full_scan_cycle: int,
        sast_incremental: bool,
) -> bool:
    """
        if sast_incremental is True, return True, check if the number of scans reach a full cycle
    Args:
        scan_collection (ScansCollection):
        full_scan_cycle (int):
        sast_incremental (bool):

    Returns:

    """
    incremental = False
    if sast_incremental:
        number_of_scans = scan_collection.filteredTotalCount
        remainder = number_of_scans % full_scan_cycle
        if remainder == 0:
            logger.info(f"Now this scan has reached a full scan cycle: {full_scan_cycle}, "
                        f"it is required to initiate a Full scan")
            incremental = False
    return incremental


def check_scanners(
        scanners: List[str],
        scan_collection: ScansCollection,
        sca_last_sast_scan_time: int,
) -> List[str]:
    """
        when there is sca scanner but no sast scanner, check whether the last number of days exist a sast scan, if not
        add the sast scanner
    Args:
        scanners (list of str):
        scan_collection (ScansCollection):
        sca_last_sast_scan_time (int):

    Returns:

    """
    days = sca_last_sast_scan_time - 1
    yesterday_midnight = datetime.combine(datetime.today(), time.min) - timedelta(days=days)
    all_scans_from_last_n_days = list(filter(
        lambda r: datetime.strptime(r.createdAt, time_stamp_format) > yesterday_midnight,
        scan_collection.scans
    ))
    sast_scans_from_last_n_days = list(filter(
        lambda r: "sast" in [status_detail.name for status_detail in r.statusDetails],
        all_scans_from_last_n_days
    ))
    if "sca" in scanners and "sast" not in scanners and not sast_scans_from_last_n_days:
        logger.info(f"There are no sast scan from the last {sca_last_sast_scan_time} days, add sast scanner")
        scanners.append("sast")
    return scanners


def upload_zip_file(zip_file_path: str) -> str:
    logger.info("create a pre signed url to upload zip file")
    upload_url = create_a_pre_signed_url_to_upload_files()
    logger.debug(f"upload url created: {upload_url}")
    logger.info("begin to upload zip file")

    upload_source_code_successful = upload_zip_content_for_scanning(
        upload_link=upload_url,
        zip_file_path=zip_file_path,
    )
    if not upload_source_code_successful:
        logger.error("[ERROR]: Failed to upload zip file. Abort scan.")
        exit(1)
    logger.info("finish upload zip file")
    return upload_url


def cx_scan_from_local_zip_file(
        preset: str,
        project_id: str,
        branch: str,
        sha_256_hash: str,
        upload_url: str,
        sast_incremental: bool = False,
        scanners: List[str] = None,
        sca_exploitable_path: bool = False,
        sca_last_sast_scan_time: int = 2,
        git_commit_history: List[dict] = None,
        scan_tag_key: List[str] = None,
        scan_tag_value: List[str] = None,
) -> str:
    """

    Args:
        preset (str):
        project_id (str):
        branch (str):
        sha_256_hash (str):
        upload_url (str):
        sast_incremental (bool):
        scanners (list of str):
        sca_exploitable_path (bool):
        sca_last_sast_scan_time (int):
        git_commit_history (list of dict):
        scan_tag_key (list of str):
        scan_tag_value (list of str):

    Returns:
        return scan id if scan finished, otherwise return None
    """
    scan_configs = create_scan_configs(
        scanners=scanners,
        sast_incremental=sast_incremental,
        preset=preset,
        sca_exploitable_path=sca_exploitable_path,
        sca_last_sast_scan_time=sca_last_sast_scan_time,
    )
    scan_tags = create_scan_tags(
        sha_256_hash=sha_256_hash,
        sast_incremental=sast_incremental,
        preset=preset,
        branch=branch,
        sca_exploitable_path=sca_exploitable_path,
        sca_last_sast_scan_time=sca_last_sast_scan_time,
        git_commit_history=git_commit_history,
        scan_tag_key=scan_tag_key,
        scan_tag_value=scan_tag_value
    )
    scan_input = ScanInput(
        scan_type="upload",
        handler=Upload(upload_url=upload_url, branch=branch),
        project=Project(project_id=project_id),
        configs=scan_configs,
        tags=scan_tags,
    )
    logger.info("start create new scan")
    scan = create_scan(scan_input=scan_input)
    scan_id = scan.id
    logger.info("new scan created, scan_id : {}".format(scan_id))

    logger.info("get scan details by scan id, report scan status")
    while True:
        scan = get_a_scan_by_id(scan_id=scan_id)
        scan_status = scan.status
        logger.info("scan_status: {}".format(scan_status))
        if scan_status in ["Completed", "Partial"]:
            break
        elif scan_status in ["Failed", "Canceled"]:
            return scan_id
        sleep(60)
    return scan_id
