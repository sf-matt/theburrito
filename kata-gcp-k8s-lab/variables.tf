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
  default     = "us-central1-a"
}

variable "machine_type" {
  description = "GCE machine type."
  type        = string
  default     = "n2-standard-4"
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
  description = "CIDR blocks allowed to SSH to the instance. Defaults to Google's IAP TCP forwarding range."
  type        = list(string)
  default     = ["35.235.240.0/20"]

  validation {
    condition     = !contains(var.ssh_source_ranges, "0.0.0.0/0")
    error_message = "Do not expose SSH to the entire internet. Use the IAP range or a trusted /32 address."
  }
}

variable "enable_oslogin" {
  description = "Whether to enable OS Login metadata."
  type        = bool
  default     = true
}
