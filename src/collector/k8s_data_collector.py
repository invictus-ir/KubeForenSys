from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pathlib import Path
import os
import subprocess
from datetime import datetime
import tempfile 

import logging

class KubeLogFetcher:
    def __init__(self, user_settings):
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
        self.since_seconds = user_settings.get("since_seconds", 86400)
        self.namespaces_to_skip = ["kube-system", "azure-arc", "gatekeeper-system"]
        self.pod_batch_size = 500
        self.rbac_v1 = client.RbacAuthorizationV1Api()
        self.batch_v1 = client.BatchV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.logger = logging.getLogger("appLogger")
    
    def is_pod_valid(self, pod):
        return pod.status.phase != "Succeeded" and pod.metadata.namespace not in self.namespaces_to_skip
    
    def get_pods_stream(self):
        try:
            pods = self.v1.list_pod_for_all_namespaces(limit=self.pod_batch_size)
            while True:
                for pod in pods.items:
                    if self.is_pod_valid(pod):
                        yield pod
                if pods.metadata._continue:
                    pods = self.v1.list_pod_for_all_namespaces(limit=self.pod_batch_size, _continue=pods.metadata._continue)
                else:
                    break
        except ApiException as e:
            self(f"Error fetching pods: {e}")

    def retrieve_logs_from_pods(self):
        for pod in self.get_pods_stream():
            try:
                if not pod.status.container_statuses:
                    self.logger.info("No container status")
                    continue

                for container_status in pod.status.container_statuses:
                    container_name = container_status.name

                    # Determine if we should collect previous logs based on whether the container restarted
                    log_modes = [("current", False)]
                    if container_status.restart_count > 0:
                        self.logger.info("Running with Previous true")
                        log_modes.insert(0, ("previous", True))

                    for label, is_previous in log_modes:
                        self.logger.info(f"Fetching {label} logs for container: {container_name}")

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

                            for raw_line in log_response:
                                line = raw_line.decode("utf-8")
                                timestamp, message = line.split(" ", maxsplit=1)
                                yield {
                                    "TimeGenerated": timestamp,
                                    "message": message,
                                    "container_name": container_name,
                                    "namespace": pod.metadata.namespace,
                                    "pod_name": pod.metadata.name,
                                    "images": [c.image for c in pod.spec.containers],
                                    "labels": pod.metadata.labels,
                                    "annotations": pod.metadata.annotations,
                                }

                        except ApiException as e:
                            self.logger.error(f"Could not get {label} logs for {container_name}: {e}")

            except ApiException as e:
                self.logger.error(f"Error accessing pod '{pod.metadata.name}': {e}")
    
    def format_timestamp(self, timestamp):
        # Format from datetime object to plain string, since a datetime is not serializable
        return str(timestamp) if timestamp else ""

    def retrieve_events(self):
        self.logger.info("Fetching events for all namespaces")
        data = self.v1.list_event_for_all_namespaces().items
        for event in data:
            yield {
                "TimeGenerated": self.format_timestamp(event.metadata.creation_timestamp),
                "first_timestamp": self.format_timestamp(event.first_timestamp),
                "last_timestamp": self.format_timestamp(event.last_timestamp) if event.last_timestamp else "",
                "action": event.action,
                "reason": event.reason,
                "message": event.message,
                "involved_object_uid": event.involved_object.uid,
                "involved_object_name": event.involved_object.name,
                "reporting_component": event.reporting_instance
            }
    
    def retrieve_command_history(self):
        
        HISTORY_PATHS = [
        "/root/.ash_history",
        "/root/.bash_history"
        ]
        self.logger.info("Retrieving command history")
        for pod in self.get_pods_stream():

            with tempfile.TemporaryDirectory() as temp_dir:
                for container in pod.spec.containers:
                    for history_path in HISTORY_PATHS:
                        dest_file = os.path.join(temp_dir, f"{container.name}_{os.path.basename(history_path)}")
                        self.logger.info(f"Attempting to copy {history_path} from {pod.metadata.name}/{container.name}")
                        
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
                                        yield {
                                            "TimeGenerated": datetime.utcnow().isoformat(),
                                            "namespace": pod.metadata.namespace,
                                            "pod_name": pod.metadata.name,
                                            "container_name": container.name,
                                            "command": line
                                        }

                        except subprocess.CalledProcessError:
                            self.logger.error(f"Failed to copy {history_path} from {pod.metadata.name}/{container.name}")
                        except FileNotFoundError:
                            continue
    
    def get_service_accounts(self):
        self.logger.info("Retrieving service accounts")
        for ns in self.v1.list_namespace().items:
            namespace = ns.metadata.name
            for sa in self.v1.list_namespaced_service_account(namespace).items:
                creation_timestamp = self.format_timestamp(sa.metadata.creation_timestamp)
                yield {
                    "TimeGenerated": creation_timestamp,
                    "namespace": namespace,
                    "name": sa.metadata.name,
                    "automount_service_account_token": sa.automount_service_account_token,
                    "image_pull_secrets": sa.image_pull_secrets
                }
    
    def get_suspicious_pods(self):
        self.logger.info("Retrieving possibly suspicious pods")
        for pod in self.get_pods_stream():

            creation_timestamp = self.format_timestamp(pod.metadata.creation_timestamp)

            name = pod.metadata.name
            ns = pod.metadata.namespace
            spec = pod.spec

            if spec.host_network:
                yield {
                    "TimeGenerated": creation_timestamp,
                    "pod_name": name,
                    "namespace": ns,
                    "issue_type": "hostNetwork",
                    "details": "hostNetwork=true"
                }

            for container in spec.containers:
                security = container.security_context
                if security and security.privileged:
                    yield {
                        "TimeGenerated": creation_timestamp,
                        "name": name,
                        "namespace": ns,
                        "issue_type": "privileged",
                        "details": f"{container.name}: privileged=true"
                    }

            for volume in spec.volumes or []:
                if volume.host_path:
                    vol_type = volume.host_path.type or ""
                    if vol_type in ["DirectoryOrCreate", "FileOrCreate"]:
                        issue = "hostPath (creation-capable)"
                    else:
                        issue = "hostPath"
                    yield {
                        "TimeGenerated": creation_timestamp,
                        "name": name,
                        "namespace": ns,
                        "issue_type": issue,
                        "details": f"hostPath: {volume.host_path.path}, type: {vol_type}"
                    }

    def get_rbac_bindings(self):
        self.logger.info("Retrieving RBAC bindings")
        for binding in self.rbac_v1.list_role_binding_for_all_namespaces().items:
            creation_timestamp = self.format_timestamp(binding.metadata.creation_timestamp)
            binding_name = binding.metadata.name
            namespace = binding.metadata.namespace
            role_ref_kind = binding.role_ref.kind
            role_ref_name = binding.role_ref.name

            for subject in binding.subjects or []:
                yield {
                    "TimeGenerated": creation_timestamp,
                    "binding_type": "RoleBinding",
                    "binding_name": binding_name,
                    "namespace": namespace,
                    "subject_kind": subject.kind,
                    "subject_name": subject.name,
                    "subject_namespace": getattr(subject, "namespace", namespace),
                    "role_ref_kind": role_ref_kind,
                    "role_ref_name": role_ref_name
                }
        
        for binding in self.rbac_v1.list_cluster_role_binding().items:
            creation_timestamp = self.format_timestamp(binding.metadata.creation_timestamp)
            binding_name = binding.metadata.name
            namespace = binding.metadata.namespace
            role_ref_kind = binding.role_ref.kind
            role_ref_name = binding.role_ref.name

            for subject in binding.subjects or []:
                yield {
                    "TimeGenerated": creation_timestamp,
                    "binding_type": "RoleBinding",
                    "binding_name": binding_name,
                    "namespace": namespace,
                    "subject_kind": subject.kind,
                    "subject_name": subject.name,
                    "subject_namespace": getattr(subject, "namespace", namespace),
                    "role_ref_kind": role_ref_kind,
                    "role_ref_name": role_ref_name
                }
    
    def get_cronjob_containers_info(self):
        self.logger.info("Extracting CronJob container info")
        for cj in self.batch_v1.list_cron_job_for_all_namespaces().items:
            creation_timestamp = self.format_timestamp(cj.metadata.creation_timestamp)
            cj_name = cj.metadata.name
            namespace = cj.metadata.namespace
            containers = cj.spec.job_template.spec.template.spec.containers

            for c in containers:
                command_str = " ".join(c.command) if c.command else ""
                yield {
                    "TimeGenerated": creation_timestamp,
                    "cronjob_name": cj_name,
                    "namespace": namespace,
                    "container_name": c.name,
                    "image": c.image,
                    "command": command_str,
                    "schedule": cj.spec.schedule
                }

    def get_network_policies(self):
        self.logger.info("Retrieving Network Policies")
        for np in self.networking_v1.list_network_policy_for_all_namespaces().items:
            creation_timestamp = self.format_timestamp(np.metadata.creation_timestamp)
            yield {
                "TimeGenerated": creation_timestamp,
                "namespace": np.metadata.namespace,
                "name": np.metadata.name
            }