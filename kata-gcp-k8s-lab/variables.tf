variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "name" {
  description = "Name for the lab instance."
  type        = string
  default     = "kata-k8s-node"
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone."
  type        = string
  default     = "us-central1-f"
}

variable "machine_type" {
  description = "GCE machine type."
  type        = string
  default     = "n2-standard-4"
}

variable "min_cpu_platform" {
  description = "Minimum CPU platform required for nested virtualization."
  type        = string
  default     = "Intel Cascade Lake"
}

variable "image" {
  description = "Boot disk image."
  type        = string
  default     = "ubuntu-os-cloud/ubuntu-2204-lts"
}

variable "boot_disk_size_gb" {
  description = "Boot disk size in GB."
  type        = number
  default     = 50
}

variable "boot_disk_type" {
  description = "Boot disk type."
  type        = string
  default     = "pd-balanced"
}

variable "network" {
  description = "VPC network name."
  type        = string
  default     = "default"
}

variable "ssh_source_ranges" {
  description = "CIDR blocks allowed to SSH to the instance."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_oslogin" {
  description = "Whether to enable OS Login metadata."
  type        = bool
  default     = false
}

variable "username" {
  description = "Linux username that should receive kubeconfig."
  type        = string
  default     = "ubuntu"
}
