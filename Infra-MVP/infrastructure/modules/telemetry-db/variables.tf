variable "region" {
  description = "Scaleway region"
  type        = string
}

variable "private_network_id" {
  description = "ID of the private network (subnet data)"
  type        = string
}

variable "db_user" {
  description = "Database admin user"
  type        = string
  default     = "telemetry_admin"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "Name of the telemetry database"
  type        = string
  default     = "cascadya_telemetry"
}

variable "node_type" {
  description = "Instance type for the database"
  type        = string
  default     = "DB-DEV-S"
}