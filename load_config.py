import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="A tool to collect Kubernetes data and push it to a Log Analytics workspace in Azure")
    parser.add_argument("--since_seconds", type=int, help="Fetch logs since these many seconds ago (default: 86400)")
    parser.add_argument("--workspace_name", type=str, help="Name of the Log Analytics workspace (default: 'Kube-LAW')")
    parser.add_argument("--dce_name", type=str, help="Name of the Data Collection Endpoint (default: 'Kube-DCE')")
    parser.add_argument("--location", type=str, help="Azure region (default: 'west-europe')")

    args = parser.parse_args()

    return {k: v for k, v in vars(args).items() if v is not None}