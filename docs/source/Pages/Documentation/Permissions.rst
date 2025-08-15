Permissions
=============

The following permissions are required for KubeForenSys to work fully within Azure:

.. literalinclude:: /../../resources/azure/custom_role.json
   :language: json

Above JSON can be used to create a custom role on Resource Group level. The Security Principal automatically inherits the role to resources created within this Resource Group.
The custom role can be created and assigned using the `Azure CLI <https://learn.microsoft.com/en-us/azure/role-based-access-control/tutorial-custom-role-cli>`_ or through using `Azure Powershell <https://learn.microsoft.com/en-us/azure/role-based-access-control/tutorial-custom-role-powershell>`_
It is however also possible to achieve above authorizations through default roles provided by Azure. It is however recommended to create a custom-role to adhere to the least privilege principle.
The following roles would need to be assigned:

- Log Analytics Contributor: For Log Analytics workspace/table writes and access to sharedKeys
- Monitoring Contributor: For creation of DCRs, DCEs and writing telemetry
- Reader or Kubernetes Service RBAC Viewer: To allow AKS cluster read (Microsoft.ContainerService/managedClusters/read)

For more information, see the `Azure documentation <https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal>`_.