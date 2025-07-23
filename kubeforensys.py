from src.collector.k8s_data_collector import KubeLogFetcher
from src.platform.azure.upload.azure_connector import AzureConnector
from src.platform.azure.collect.aks_addon_status import AksAddonLister
from src.platform.azure.create.create_env import AzureLogPipelineProvisioner
from src.utils.load_config import parse_args

from dotenv import load_dotenv
import os
import logging
import logging.config

def main():

    user_settings = parse_args()

    load_dotenv()

    logging.config.fileConfig('logger.conf', disable_existing_loggers=False)
    logger = logging.getLogger("appLogger")
    logging.getLogger("azure").setLevel(logging.WARNING)

    required_env_vars = ["SUBSCRIPTION_ID", "RESOURCE_GROUP_NAME", "CLUSTER_NAME"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        msg = f"Missing required environment variables: {missing_vars}"
        logger.error(msg)
        raise ValueError(msg)

    subscription_id = os.getenv("SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOURCE_GROUP_NAME")
    cluster_name = os.getenv("CLUSTER_NAME")

    provisioner = AzureLogPipelineProvisioner(
        subscription_id=subscription_id,
        resource_group=resource_group,
        location=user_settings.get("location", "westeurope"),
        workspace_name=user_settings.get("workspace_name", "KubeForenSys-LAW"),
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
        "kubelogs_CL": fetcher.retrieve_logs_from_pods,
        "kubeevents_CL": fetcher.retrieve_events,
        "commandhistory_CL": fetcher.retrieve_command_history,
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
            generator_function=fetch_function,
            stream_name=f"Custom-{table_name}",
            dcr_stream_id=dcr_mappings[table_name]["dcr_id"]
        )

if __name__ == "__main__":
    main()