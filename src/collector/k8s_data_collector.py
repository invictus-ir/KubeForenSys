from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pathlib import Path
import os
import subprocess
from datetime import datetime
import tempfile 

class KubeLogFetcher:
    def __init__(self, user_settings):
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
        self.chunk_size = user_settings.get("chunk_size", 500)
        self.since_seconds = user_settings.get("since_seconds", 86400)
        self.namespaces_to_skip = ["kube-system", "azure-arc", "gatekeeper-system"]
        self.pods = self.get_all_pods()
        self.rbac_v1 = client.RbacAuthorizationV1Api()
        self.batch_v1 = client.BatchV1Api()
        self.networking_v1 = client.NetworkingV1Api()
    
    def get_all_pods(self):
        # Exclude pods which are succeeded (e.g. as created by a cronjob), otherwise retrieving will fail
        return [pod for pod in self.v1.list_pod_for_all_namespaces(watch=False).items
            if pod.status.phase != "Succeeded"
            and pod.metadata.namespace not in self.namespaces_to_skip
        ]
    
    def get_all_logs(self):
        logs = []
        for pod in self.pods:
            self.retrieve_logs_from_pod(pod, logs)
        return logs
    
    def get_command_history(self):
        collected_commands = []
        for pod in self.pods:
            self.retrieve_history_from_pod(pod, collected_commands)
        return collected_commands
    
    def retrieve_logs_from_pod(self, pod, logs):
        try:
            if not pod.status.container_statuses:
                print("No container status")
                return

            for container_status in pod.status.container_statuses:
                container_name = container_status.name

                # Determine if we should collect previous logs based on whether the container restarted
                log_modes = [("current", False)]
                if container_status.restart_count > 0:
                    print("Running with Previous true")
                    log_modes.insert(0, ("previous", True))

                for label, is_previous in log_modes:
                    print(f"\nFetching {label} logs for container: {container_name}")

                    try:
                        log_response = self.v1.read_namespaced_pod_log(
                            name=pod.metadata.name,
                            namespace=pod.metadata.namespace,
                            container=container_name,
                            timestamps=True,
                            previous=is_previous,
                            since_seconds=self.since_seconds,
                            _preload_content=False
                        )

                        if not log_response:
                            continue  # skip empty logs

                        for line in log_response.readlines():
                            line = line.decode('utf-8')
                            timestamp, message = line.split(" ", maxsplit=1)
                            logs.append({
                                "TimeGenerated": timestamp,
                                "message": message,
                                "container_name": container_name,
                                "namespace": pod.metadata.namespace,
                                "pod_name": pod.metadata.name,
                                "images": [c.image for c in pod.spec.containers],
                                "labels": pod.metadata.labels,
                                "annotations": pod.metadata.annotations,
                            })

                    except ApiException as e:
                        print(f"Could not get {label} logs for {container_name}: {e}")

        except ApiException as e:
            print(f"Error accessing pod '{pod.metadata.name}': {e}")

        return
    
    def format_timestamp(self, timestamp):
        # Format from datetime object to plain string, since a datetime is not serializable
        return str(timestamp) if timestamp else ""

    def retrieve_events(self):
        print(f"\nFetching events for all namespaces")
        data = self.v1.list_event_for_all_namespaces().items
        parsed_events = []
        for event in data:
            parsed_events.append({
                "TimeGenerated": self.format_timestamp(event.metadata.creation_timestamp),
                "first_timestamp": self.format_timestamp(event.first_timestamp),
                "last_timestamp": self.format_timestamp(event.last_timestamp) if event.last_timestamp else "",
                "action": event.action,
                "reason": event.reason,
                "message": event.message,
                "involved_object_uid": event.involved_object.uid,
                "involved_object_name": event.involved_object.name,
                "reporting_component": event.reporting_instance
            })
        return parsed_events
    
    def retrieve_history_from_pod(self, pod, collected_entries):
        HISTORY_PATHS = [
        "/root/.ash_history",
        "/root/.bash_history"
        ]

        with tempfile.TemporaryDirectory() as temp_dir:

            for container in pod.spec.containers:
                for history_path in HISTORY_PATHS:
                    dest_file = os.path.join(temp_dir, f"{container.name}_{os.path.basename(history_path)}")
                    print(f"Attempting to copy {history_path} from {pod.metadata.name}/{container.name}")
                    
                    try:
                        subprocess.run([
                            "kubectl", "cp",
                            f"{pod.metadata.namespace}/{pod.metadata.name}:{history_path}",
                            dest_file,
                            "-c", container.name
                        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                        with open(dest_file, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    collected_entries.append({
                                        "TimeGenerated": datetime.utcnow().isoformat(),
                                        "namespace": pod.metadata.namespace,
                                        "pod_name": pod.metadata.name,
                                        "container_name": container.name,
                                        "command": line
                                    })

                    except subprocess.CalledProcessError:
                        print(f"Failed to copy {history_path} from {pod.metadata.name}/{container.name}")
                    except FileNotFoundError:
                        continue

            return collected_entries
    
    def get_service_accounts(self):
        print("\nRetrieving service accounts")
        service_accounts = []
        for ns in self.v1.list_namespace().items:
            namespace = ns.metadata.name
            for sa in self.v1.list_namespaced_service_account(namespace).items:
                creation_timestamp = self.format_timestamp(sa.metadata.creation_timestamp)
                service_accounts.append({
                    "TimeGenerated": creation_timestamp,
                    "namespace": namespace,
                    "name": sa.metadata.name,
                    "automount_service_account_token": sa.automount_service_account_token,
                    "image_pull_secrets": sa.image_pull_secrets
                })
        return service_accounts
    
    def get_suspicious_pods(self):
        suspicious_entries = []

        for pod in self.pods:

            creation_timestamp = self.format_timestamp(pod.metadata.creation_timestamp)

            name = pod.metadata.name
            ns = pod.metadata.namespace
            spec = pod.spec

            if spec.host_network:
                suspicious_entries.append({
                    "TimeGenerated": creation_timestamp,
                    "pod_name": name,
                    "namespace": ns,
                    "issue_type": "hostNetwork",
                    "details": "hostNetwork=true"
                })

            for container in spec.containers:
                security = container.security_context
                if security and security.privileged:
                    suspicious_entries.append({
                        "TimeGenerated": creation_timestamp,
                        "name": name,
                        "namespace": ns,
                        "issue_type": "privileged",
                        "details": f"{container.name}: privileged=true"
                    })

            for volume in spec.volumes or []:
                if volume.host_path:
                    vol_type = volume.host_path.type or ""
                    if vol_type in ["DirectoryOrCreate", "FileOrCreate"]:
                        issue = "hostPath (creation-capable)"
                    else:
                        issue = "hostPath"
                    suspicious_entries.append({
                        "TimeGenerated": creation_timestamp,
                        "name": name,
                        "namespace": ns,
                        "issue_type": issue,
                        "details": f"hostPath: {volume.host_path.path}, type: {vol_type}"
                    })

        return suspicious_entries

    def get_rbac_bindings(self):
        flattened_bindings = []


        for binding in self.rbac_v1.list_role_binding_for_all_namespaces().items:
            creation_timestamp = self.format_timestamp(binding.metadata.creation_timestamp)
            binding_name = binding.metadata.name
            namespace = binding.metadata.namespace
            role_ref_kind = binding.role_ref.kind
            role_ref_name = binding.role_ref.name

            for subject in binding.subjects or []:
                flattened_bindings.append({
                    "TimeGenerated": creation_timestamp,
                    "binding_type": "RoleBinding",
                    "binding_name": binding_name,
                    "namespace": namespace,
                    "subject_kind": subject.kind,
                    "subject_name": subject.name,
                    "subject_namespace": getattr(subject, "namespace", namespace),
                    "role_ref_kind": role_ref_kind,
                    "role_ref_name": role_ref_name
                })
        
        for binding in self.rbac_v1.list_cluster_role_binding().items:
            creation_timestamp = self.format_timestamp(binding.metadata.creation_timestamp)
            binding_name = binding.metadata.name
            namespace = binding.metadata.namespace
            role_ref_kind = binding.role_ref.kind
            role_ref_name = binding.role_ref.name

            for subject in binding.subjects or []:
                flattened_bindings.append({
                    "TimeGenerated": creation_timestamp,
                    "binding_type": "RoleBinding",
                    "binding_name": binding_name,
                    "namespace": namespace,
                    "subject_kind": subject.kind,
                    "subject_name": subject.name,
                    "subject_namespace": getattr(subject, "namespace", namespace),
                    "role_ref_kind": role_ref_kind,
                    "role_ref_name": role_ref_name
                })

        return flattened_bindings
    
    def get_cronjob_containers_info(self):
        print("\nExtracting CronJob container info...")
        container_data = []
        for cj in self.batch_v1.list_cron_job_for_all_namespaces().items:
            creation_timestamp = self.format_timestamp(cj.metadata.creation_timestamp)
            cj_name = cj.metadata.name
            namespace = cj.metadata.namespace
            containers = cj.spec.job_template.spec.template.spec.containers

            for c in containers:
                command_str = " ".join(c.command) if c.command else ""
                container_data.append({
                    "TimeGenerated": creation_timestamp,
                    "cronjob_name": cj_name,
                    "namespace": namespace,
                    "container_name": c.name,
                    "image": c.image,
                    "command": command_str,
                    "schedule": cj.spec.schedule
                })

        return container_data
    

    def get_network_policies(self):
        print("\nRetrieving Network Policies:")
        network_policies = []
        for np in self.networking_v1.list_network_policy_for_all_namespaces().items:
            creation_timestamp = self.format_timestamp(np.metadata.creation_timestamp)
            network_policies.append({
                "TimeGenerated": creation_timestamp,
                "namespace": np.metadata.namespace,
                "name": np.metadata.name
            })
        return network_policies