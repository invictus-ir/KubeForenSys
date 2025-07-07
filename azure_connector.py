from azure.identity import DefaultAzureCredential
from azure.monitor.ingestion import LogsIngestionClient
from azure.core.exceptions import HttpResponseError

import math

class AzureConnector:
    def __init__(self, endpoint_uri):
        self.setup_envs(endpoint_uri=endpoint_uri)
        self.authenticate()
        self.MAX_UPLOAD_BATCH = 500
    
    def setup_envs(self, endpoint_uri):
        self.endpoint_uri = endpoint_uri
        if not self.endpoint_uri:
            raise EnvironmentError(f"Required values not set: endpoint_uri: {self.endpoint_uri}")

    def authenticate(self):
        credential = DefaultAzureCredential()
        self.client = LogsIngestionClient(endpoint=self.endpoint_uri, credential=credential, logging_enabled=True)

    def upload_in_batches(self, body, stream_name, dcr_stream_id):
        print(f"Total log chunks to upload: {len(body)}")
        for i in range(0, len(body), self.MAX_UPLOAD_BATCH):
            batch = body[i:i + self.MAX_UPLOAD_BATCH]
            try:
                self.client.upload(
                    rule_id=dcr_stream_id,
                    stream_name=stream_name,
                    logs=batch
                )
                print(f"Uploaded batch {i // self.MAX_UPLOAD_BATCH + 1} of {math.ceil(len(body)/self.MAX_UPLOAD_BATCH)}")
            except HttpResponseError as e:
                print(f"Upload failed on batch {i // self.MAX_UPLOAD_BATCH + 1}: {e}")
