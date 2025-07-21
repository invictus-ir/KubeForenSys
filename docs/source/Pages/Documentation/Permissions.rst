Permissions
=============

The following permissions are required for KubeForenSys to work fully within Azure:

.. literalinclude:: /../../custom_role.json
   :language: json

Above JSON can be used to create a custom role on Resource Group level. The Security Principal automatically inherits the role to resources created within this Resource Group.
The custom role can be created and assigned using the `Azure CLI <https://learn.microsoft.com/en-us/azure/role-based-access-control/tutorial-custom-role-cli>`_ or through using `Azure Powershell <https://learn.microsoft.com/en-us/azure/role-based-access-control/tutorial-custom-role-powershell>`_