# CxCliPy

## how to run it
./CxOneCli scan --cxone_access_control_url https://eu.iam.checkmarx.net --cxone_server https://eu.ast.checkmarx.net --cxone_tenant_name asean_2021_08 --cxone_grant_type refresh_token --cxone_refresh_token "***" --preset "ASA Premium"  --incremental false --location_path /home/happy/Documents/SourceCode/github/java/JavaVulnerableLab --project_name happy-test-2022-04-20 --branch master --exclude_folders "test,integrationtest" --exclude_files "*min.js" --report_csv cx-report.csv --full_scan_cycle 10 --cxone_proxy http://127.0.0.1:1081 --scan_tag_key branch,date --scan_tag_value master,2024-10-23 --scan_commit_number 2 

