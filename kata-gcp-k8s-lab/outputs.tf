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
  description = "SSH command for the instance."
  value       = "ssh ${var.username}@${google_compute_instance.kata_node.network_interface[0].access_config[0].nat_ip}"
}
