import requests
import json
import time

from azure.identity import DefaultAzureCredential
from azure.mgmt.loganalytics import LogAnalyticsManagementClient

class AzureLogPipelineProvisioner:
    TABLE_API_VERSION = "2025-02-01"
    DCR_API_VERSION = "2023-03-11"
    DCE_API_VERSION = "2023-03-11"

    def __init__(self, subscription_id, resource_group, location, workspace_name, dce_name):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.location = location
        self.workspace_name = workspace_name
        self.dce_name = dce_name

        self.credential = DefaultAzureCredential()
        self.token = self.credential.get_token("https://management.azure.com/.default").token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        self.log_analytics_client = LogAnalyticsManagementClient(self.credential, self.subscription_id)


    def create_workspace(self):
        print("Creating Log Analytics workspace...")
        workspace_async = self.log_analytics_client.workspaces.begin_create_or_update(
            self.resource_group,
            self.workspace_name,
            {
                "location": self.location,
                "sku": {"name": "PerGB2018"},
                "retention_in_days": 30
            }
        )
        workspace = workspace_async.result()
        self.workspace_id = workspace.customer_id
        self.workspace_resource_id = workspace.id
        print(f"Workspace ID: {self.workspace_id}")
        print(f"Workspace Resource ID: {self.workspace_resource_id}")

    def create_custom_table(self, table_name, table_columns):
        print(f"Creating custom table '{table_name}'...")
        url = f"https://management.azure.com{self.workspace_resource_id}/tables/{table_name}?api-version={self.TABLE_API_VERSION}"

        payload = {
            "properties": {
                "schema": {
                    "name": table_name,
                    "columns": table_columns
                },
                "retentionInDays": 30
            }
        }

        resp = requests.put(url, headers=self.headers, data=json.dumps(payload))
        resp.raise_for_status()
        print("[+] Custom table created successfully.")

    def create_dce(self):
        print("Creating DCE...")
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/providers/Microsoft.Insights/dataCollectionEndpoints/{self.dce_name}?api-version={self.DCE_API_VERSION}"
        payload = {
            "location": self.location,
            "properties": {
                "networkAcls": {
                    "publicNetworkAccess": "Enabled"
                }
            }
        }
        resp = requests.put(url, headers=self.headers, data=json.dumps(payload))
        resp.raise_for_status()
        self.dce_id = resp.json()["id"]
        self.dce_endpoint = resp.json()["properties"]["logsIngestion"]["endpoint"]
        print(f"DCE ID: {self.dce_id}")

    def create_dcr(self, table):
        print("Creating DCR...")
        dcr_name = f"{table["name"]}-dcr"
        custom_stream_name = f"Custom-{table["name"]}"
        dcr_url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/providers/Microsoft.Insights/dataCollectionRules/{dcr_name}?api-version={self.DCR_API_VERSION}"
        dcr_payload = {
            "location": self.location,
            "kind": "Linux",
            "properties": {
                "dataCollectionEndpointId": self.dce_id,
                "streamDeclarations": {
                    custom_stream_name: {
                        "columns": [{"name": col["name"], "type": col["type"].lower()} for col in table["columns"]]
                    }
                },
                "dataSources": {
                    "logFiles": [
                        {
                            "streams": [custom_stream_name],
                            "filePatterns": ["/var/log/my-app/*.log"],
                            "format": "text",
                            "name": "myAppLogsSource"
                        }
                    ]
                },
                "destinations": {
                    "logAnalytics": [
                        {
                            "name": "logAnalyticsWorkspace",
                            "workspaceResourceId": self.workspace_resource_id
                        }
                    ]
                },
                "dataFlows": [
                    {
                        "streams": [custom_stream_name],
                        "destinations": ["logAnalyticsWorkspace"]
                    }
                ]
            }
        }


        dcr_resp = requests.put(dcr_url, headers=self.headers, data=json.dumps(dcr_payload))
        dcr_resp.raise_for_status()
        immutable_dcr_id = dcr_resp.json()["properties"]["immutableId"]
        return immutable_dcr_id

    def run(self):

        self.create_workspace()
        print("Provisioning LAW for 30s")
        time.sleep(30)
        self.create_dce()

        result = {
            "dce_endpoint": self.dce_endpoint,
            "dcr_mappings": {}
        }

        tables = [{
            "name": "kubelogs_CL",
            "columns" : [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "message", "type": "String"},
                {"name": "container_name", "type": "String"},
                {"name": "namespace", "type": "String"},
                {"name": "pod_name", "type": "String"},
                {"name": "containerimages", "type": "String"},
                {"name": "labels", "type": "String"},
                {"name": "annotations", "type": "String"},
            ]
            },
        {
            "name": "kubeevents_CL",
            "columns": [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "action", "type": "String"},
                {"name": "first_timestamp", "type": "DateTime"},
                {"name": "involved_object_name", "type": "String"},
                {"name": "involved_object_uid", "type": "String"},
                {"name": "last_timestamp", "type": "DateTime"},
                {"name": "message", "type": "String"},
                {"name": "reason", "type": "String"},
                {"name": "reporting_component", "type": "String"}
            ]
        },
        {
            "name": "commandhistory_CL",
            "columns": [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "namespace", "type": "String"},
                {"name": "pod_name", "type": "String"},
                {"name": "container_name", "type": "String"},
                {"name": "command", "type": "String"}
            ]
        },
        {
            "name": "serviceaccounts_CL",
            "columns": [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "namespace", "type": "String"},
                {"name": "name", "type": "String"},
                {"name": "automount_service_account_token", "type": "String"},
                {"name": "image_pull_secrets", "type": "String"}
            ]
        },
        {
            "name": "suspiciouspods_CL",
            "columns": [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "namespace", "type": "String"},
                {"name": "pod_name", "type": "String"},
                {"name": "issue_type", "type": "String"},
                {"name": "details", "type": "String"}
            ]
        },
        {
            "name": "rbacbindings_CL",
            "columns": [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "binding_type", "type": "String"},
                {"name": "binding_name", "type": "String"},
                {"name": "namespace", "type": "String"},
                {"name": "subject_kind", "type": "String"},
                {"name": "subject_name", "type": "String"},
                {"name": "subject_namespace", "type": "String"},
                {"name": "role_ref_kind", "type": "String"},
                {"name": "role_ref_name", "type": "String"}
            ]
        },
        {
            "name": "cronjobs_CL",
            "columns": [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "cronjob_name", "type": "String"},
                {"name": "namespace", "type": "String"},
                {"name": "container_name", "type": "String"},
                {"name": "image", "type": "String"},
                {"name": "command", "type": "String"},
                {"name": "schedule", "type": "String"}
            ]
        },
        {
            "name": "networkpolicies_CL",
            "columns": [
                {"name": "TimeGenerated", "type": "DateTime"},
                {"name": "namespace", "type": "String"},
                {"name": "name", "type": "String"}
            ]
        }]

        # First create all tables, then a DCR for each table
        for table in tables:

            table_name = table["name"]

            # Create new custom table
            self.create_custom_table(table_name=table["name"], table_columns=table["columns"])
        
        # Give Azure a moment to fully create the new table, will otherwise error out when creating the DCR
        print("Creating tables, give it a moment... (30s)")
        time.sleep(30)

        # Create DCRs
        for table in tables:

            table_name = table["name"]
            dcr_id = self.create_dcr(table)

            # Create related mapping to DCR
            result["dcr_mappings"][table_name] = {
                "dcr_id": dcr_id,
                "dcr_stream_name": f"Custom-{table_name}"
            }

        print("\n[+] All resources created successfully.")
        return result
    