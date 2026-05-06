"""FilestoreCache — NFS-backed shared model cache."""

from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from config import ENVIRONMENT, FILESTORE_CAPACITY_GB, FILESTORE_TIER, ZONE


class FilestoreCache(pulumi.ComponentResource):
    """
    Creates a GCP Filestore instance attached to the cluster VPC.
    Exports the NFS IP and share name for PersistentVolume definitions.
    """

    def __init__(
        self,
        name: str,
        network_name: pulumi.Input[str],
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__("mmp:infra:FilestoreCache", name, {}, opts)

        self.instance = gcp.filestore.Instance(
            f"{name}-instance",
            name=f"mmp-model-cache-{ENVIRONMENT}",
            tier=FILESTORE_TIER,
            location=ZONE,
            file_shares=gcp.filestore.InstanceFileSharesArgs(
                name="comfyui_models",
                capacity_gb=FILESTORE_CAPACITY_GB,
                nfs_export_options=[
                    gcp.filestore.InstanceFileSharesNfsExportOptionArgs(
                        ip_ranges=["10.0.0.0/8"],
                        access_mode="READ_WRITE",
                        squash_mode="NO_ROOT_SQUASH",
                    )
                ],
            ),
            networks=[
                gcp.filestore.InstanceNetworkArgs(
                    network=network_name,
                    modes=["MODE_IPV4"],
                    connect_mode="DIRECT_PEERING",
                )
            ],
            labels={
                "environment": ENVIRONMENT,
                "managed_by": "pulumi",
                "purpose": "comfyui-model-cache",
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Export outputs using apply to handle preview phase
        # The Filestore instance must be created before we can get its IP
        self.ip_address = self.instance.id.apply(
            lambda _: self.instance.networks[0].ip_addresses[0] if self.instance.networks else ""
        )
        self.share_name = "/comfyui_models"

        self.register_outputs({
            "ipAddress": self.ip_address,
            "shareName": self.share_name,
        })
