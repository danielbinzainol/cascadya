variable "instance_type" {
  description = "Type de l'instance Scaleway ( DEV1-S)"
  type        = string
  default     = "DEV1-S"
}

variable "zone" {
  description = "Zone Scaleway (ex: nl-ams-1)"
  type        = string
  default     = "nl-ams-1"
}

variable "private_network_id" {
  description = "ID du réseau privé pour ThingsBoard"
  type        = string
}

variable "security_group_id" {
  description = "ID du Security Group utilisé par ThingsBoard"
  type        = string
}
variable "user_data" {
  description = "Configuration cloud-init personnalisée"
  type        = any
  default     = null
}
