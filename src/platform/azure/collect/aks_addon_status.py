from azure.identity import DefaultAzureCredential
from azure.mgmt.containerservice import ContainerServiceClient

class AksAddonLister:
    def __init__(self, subscription_id, resource_group):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.authenticate()

    def authenticate(self):
        credential = DefaultAzureCredential()
        self.client = ContainerServiceClient(credential, self.subscription_id)

    def get_addons_for_cluster(self, cluster_name):
        cluster = self.client.managed_clusters.get(self.resource_group, cluster_name)
        return cluster.addon_profiles
    
    def get_enabled_addon_for_cluster(self, cluster_name,  addon_name_to_test):
        addons = self.get_addons_for_cluster(cluster_name)
        if not(addons):
            return False
        for addon_name, addon_profile in addons.items():
            if addon_name == addon_name_to_test and addon_profile.enabled == True:
                return True
        return False
            