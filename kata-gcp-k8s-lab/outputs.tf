output "instance_name" {
  description = "Name of the GCE instance."
  value       = google_compute_instance.kata_node.name
}

output "instance_zone" {
  description = "Zone of the GCE instance."
  value       = google_compute_instance.kata_node.zone
}

output "public_ip" {
  description = "Public IP address of the instance."
  value       = google_compute_instance.kata_node.network_interface[0].access_config[0].nat_ip
}

output "ssh_command" {
  description = "IAP-backed gcloud command for connecting to the instance."
  value       = "gcloud compute ssh ${google_compute_instance.kata_node.name} --project ${var.project_id} --zone ${google_compute_instance.kata_node.zone} --tunnel-through-iap"
}

output "startup_log_command" {
  description = "Command to inspect the bootstrap log after connecting."
  value       = "sudo journalctl -u google-startup-scripts.service --no-pager"
}
