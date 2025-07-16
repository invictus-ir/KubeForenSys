Installation
=============

KubeForenSys needs a few prerequisites in order to function properly. Due to dependencies, the minimum supported version of Python is 3.8.
KubeForenSys uses the Kubernetes client, which is initialized through:

 .. code-block:: python
   :linenos:
   :emphasize-lines: 3

    class KubeLogFetcher:
        def __init__(self, user_settings):
            config.load_kube_config()
            self.v1 = client.CoreV1Api()
            self.rbac_v1 = client.RbacAuthorizationV1Api()
            self.batch_v1 = client.BatchV1Api()
            self.networking_v1 = client.NetworkingV1Api()

Dependant on the platform you are running it on, it loads a `kubeconfig <https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/>`_ file.
This file can be generated dependant on which cloud provider the cluster lives:

Using the Azure CLI:

.. code-block:: bash

  az login
  az aks get-credentials -g $RESOURCE_GROUP_NAME -n $AKS_NAME

Using Azure Powershell:

.. code-block:: bash

  Connect-AzAccount
  Import-AzAksCredential -ResourceGroupName $RESOURCE_GROUP_NAME -Name $AKS_NAME

Furthermore, appropriate permissions are required, see :doc:`Permissions`.

Now, setup a virtual environment (not mandatory but recommended) and clone the Git repository:

.. code-block:: bash
   
   git clone git@github.com:invictus-ir/KubeForenSys.git && cd KubeForenSys

Install the required dependencies:

.. code-block:: bash
  
  pip install -r requirements.txt

Set up environment variables:

Create a .env file in the project root:

.. code-block:: text
   
   SUBSCRIPTION_ID="your-azure-subscription-id"
   CLUSTER_NAME="your-aks-cluster-name"
   RESOUCE_GROUP_NAME="your-resource-group-name"

Or set them as environment variables:

.. code-block:: bash

  export SUBSCRIPTION_ID="your-azure-subscription-id"
  export CLUSTER_NAME="your-aks-cluster-name"
  export RESOUCE_GROUP_NAME="your-resource-group-name"

And you're good to go!

.. code-block:: bash
  
  python3 kubeforensys.py