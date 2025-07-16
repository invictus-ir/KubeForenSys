Welcome to the documentation of KubeForenSys, created by Invictus Incident Response. This tool is created to battle the issue of the dispersion of
data sources in Kubernetes in cloud environments. It leverages the Kubernetes API, as exposed by the API server in the control plane, to fetch logs and the current state of the cluster.
It also is able to create the infrastructure needed for the ingestion of the logs, e.g. in Azure, the Data Collection Endpoints and Data Collection Rules.

See KubeForenSys in action:

.. image:: /Images/Resource-creation.png
  :width: 80%
  :alt: Fetching data

.. image:: /Images/Getting-data.png
  :width: 50%
  :alt: Resources created

Fetched data
--------------

Currently, the following data is supported:

===================================== =========================================================================================================================================================================== 
  Source                                Description                                                                                                                                                                
===================================== =========================================================================================================================================================================== 
Container logs                        Logs which are produced by containers.
Cluster events                        Kubernetes events log whenever the state of the cluster changes, such as a new pod being created/destroyed.          
Container command history             Commands which are logged in /root/.ash_history or /root/.bash_history.                        
Service Accounts                      Service accounts which live in a certain namespace in the cluster                                                                                       
Suspicious Pods                       Pods which may be seen as suspicious, either through having joined the host network, being privileged or having mounted a writable volume from the host.                                                                                   
RBAC bindings                         Role Based Access Control bindings show which users can do what through a role.              
Cronjobs                              Get the currently active cronjobs existing in the cluster.                                                                                        
Network Policies                      Get Network Policies active in the cluster.                                                                                                                                                                                                       
===================================== =========================================================================================================================================================================== 


This data is then pushed to a Log Analytics workspace, where KQL can be used to search the data and gain insight into the compromise. KubeForenSys is meant as a supplicant and operates on a best-effort basis.
It can only capture data that is still present, e.g. if a container is stopped and destroyed and logs are not timely captured, this data is lost. Ideally, tools such as Container Insights in AKS
provide more insight and help continously capture logs. KubeForenSys is then able to add upon this by supplying data such as active cronjobs.