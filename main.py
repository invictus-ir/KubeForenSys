from kube_logs import KubeLogFetcher
from azure_connector import AzureConnector
from aks_addon_status import AksAddonLister
from dotenv import load_dotenv
from create_env import AzureLogPipelineProvisioner
from load_config import parse_args
import os

def main():

    load_dotenv()

    required_env_vars = ["SUBSCRIPTION_ID", "RESOUCE_GROUP_NAME", "CLUSTER_NAME"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")

    subscription_id = os.getenv("SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOUCE_GROUP_NAME")
    cluster_name = os.getenv("CLUSTER_NAME")

    user_settings = parse_args()

    provisioner = AzureLogPipelineProvisioner(
        subscription_id=subscription_id,
        resource_group=resource_group,
        location=user_settings.get("location", "westeurope"),
        workspace_name=user_settings.get("workspace_name", "RP2-LAW"),
        dce_name=user_settings.get("dce_name", "Kube-DCE"),
    )

    # Setup Azure environment
    result = provisioner.run()

    connector = AzureConnector(endpoint_uri=result["dce_endpoint"])

    aks_addon_lister = AksAddonLister(subscription_id, resource_group)

    # Check whether the monitoring addon is installed and enabled. If so, no need to manually collect as this is already done
    monitoring_enabled = aks_addon_lister.get_enabled_addon_for_cluster(cluster_name, "omsagent")

    dcr_mappings = result["dcr_mappings"]

    fetcher = KubeLogFetcher(user_settings)

    data_sources = {
        "kubelogs_CL": fetcher.get_all_logs,
        "kubeevents_CL": fetcher.retrieve_events,
        "commandhistory_CL": fetcher.get_command_history,
        "serviceaccounts_CL": fetcher.get_service_accounts,
        "suspiciouspods_CL": fetcher.get_suspicious_pods,
        "rbacbindings_CL": fetcher.get_rbac_bindings,
        "cronjobs_CL": fetcher.get_cronjob_containers_info,
        "networkpolicies_CL": fetcher.get_network_policies
    }

    for table_name, fetch_function in data_sources.items():
        if monitoring_enabled and table_name in ["kubelogs_CL", "kubeevents_CL"]:
            continue  # Skip if monitoring is enabled
 
        connector.upload_in_batches(
            body=fetch_function(),
            stream_name=f"Custom-{table_name}",
            dcr_stream_id=dcr_mappings[table_name]["dcr_id"]
        )


if __name__ == "__main__":
    main()