==============
How it works
==============

The features of KubeForenSys can be divided in three different parts, which are:

* Data collection
* Infrastructure creation
* Upload of collected data

Collection
=============

The `Kubernetes API <https://kubernetes.io/docs/concepts/overview/kubernetes-api/>`_ is used to fetch the current state of the cluster. The Kubernetes Python library is
leveraged to fetch this information. To complement this, platform-specific data is retrieved, such as what addons are currently installed. 

The following data is currently retrieved from the Kubernetes cluster:

===================================== =========================================================================================================================================================================== 
Source                                Description                                                                                                                                                                
===================================== =========================================================================================================================================================================== 
Container logs                        Logs which are produced by containers.
Cluster events                        Kubernetes events log whenever the state of the cluster changes, such as a new pod being created/destroyed.          
Container command history             Commands which are logged in /root/.ash_history or /root/.bash_history.                        
Service Accounts                      Service accounts which live in a certain namespace in the cluster.                                                                                       
Suspicious Pods                       Pods which may be seen as suspicious, either through having joined the host network, being privileged or having mounted a writable volume from the host.                                                                                   
RBAC bindings                         Role Based Access Control bindings show which users can do what through a role.              
Cronjobs                              Get the currently active cronjobs existing in the cluster.                                                                                        
Network Policies                      Get Network Policies active in the cluster.                                                                                                                                                                                                       
===================================== =========================================================================================================================================================================== 


Infrastructure creation
==========================

Azure
-----------

To achieve infrastructure creation in Azure from within the script, the `Logs Ingestion API <https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-ingestion-api-overview>`_ is used.
In order to push custom data to the Log Analytics workspace, custom tables are to be created. This way, we can control what data is stored. The tables are exposed through a DCE, which is the actual endpoint where
we are sending data to. At last, Data Collection Rules exist which are able to transform data from being ingested at the endpoint to being actually stored. Thus, data sent to the endpoint does not necessarly have to comply to data expected within the tables, the transformer can format this appropriatly.

Infrastructure is created in the following order:

1. Creation of the Log Analytics workspace
2. Creation of the DCE
3. Create a custom table for each data source as defined. 
4. Create a DCR for each table which is created

Upload data
=============

Azure
-----------

To upload data to the DCE, the LogsIngestionClient is used. If no transformer is specified within the DCR, the data sent has to match the format expected by the custom tables.
The DCR will also include an endpoint, which data can be sent too if the "kind": "Direct" property is set within the DCR creation. However, as a DCE is also required when using a private link, we opted to also create a DCE.